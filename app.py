import gradio as gr
import os
import requests
import re


GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL_NAME = "llama-3.1-8b-instant"

SYSTEM_PROMPT = """You are 'ScriptForge AI', a professional YouTube Script Writer.
Your goal is to write highly engaging scripts in the 2nd person (using 'You', 'Your').

FORMATTING RULES (STRICT):
1. Use ONLY these two tags: [VISUAL] for scenes, and [AUDIO] for spoken words.
2. [VISUAL]: Describe the visuals, camera shots, or on-screen text.
3. [AUDIO]: Write ONLY the spoken words. No actor directions, no "Host:", no markdown headers.
4. Do not output any intro text. Start directly with a [VISUAL] or [AUDIO] tag.
5. Example:
   [VISUAL]
   Wide shot of a clear blue sky.
   [AUDIO]
   Today is going to be amazing.
"""

def parse_script(full_text):
   
    full_text = re.sub(r'\[?(?:SCENE DESCRIPTION|SCENE|VISUALS)\]?:?', '[VISUAL]', full_text, flags=re.IGNORECASE)
    full_text = re.sub(r'\[?(?:SCRIPT|NARRATION|AUDIO)\]?:?', '[AUDIO]', full_text, flags=re.IGNORECASE)
    

    parts = re.split(r'(\[(?:VISUAL|AUDIO)\])', full_text, flags=re.IGNORECASE)
    
    clean_audio = []
    clean_visuals = []
    
    current_tag = None
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
            
        if part.upper() == "[AUDIO]":
            current_tag = "AUDIO"
        elif part.upper() == "[VISUAL]":
            current_tag = "VISUAL"
        elif current_tag == "AUDIO":
           
            content = re.sub(r'\(.*?\)', '', part, flags=re.DOTALL)
          
            content = re.sub(r'^#+.*$', '', content, flags=re.MULTILINE)
           
            content = re.sub(r'^\w+:\s*', '', content, flags=re.MULTILINE)
         
            content = content.replace("**", "").replace("*", "")
            
            if content.strip():
                clean_audio.append(content.strip())
                
        elif current_tag == "VISUAL":
            clean_visuals.append(part.strip())
            
   
    if not clean_audio and not clean_visuals:
        lines = full_text.split('\n')
        for line in lines:
            line = line.strip()
            if not line: continue
            if line.startswith('(') or line.startswith('[') or "EXT." in line or "INT." in line:
                clean_visuals.append(line)
            else:
                clean_audio.append(line)

    return "\n\n".join(clean_audio), "\n\n".join(clean_visuals)

def save_to_file(script_text):
    if not script_text:
        return None
    file_path = "youtube_script.txt"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(script_text)
    return file_path

def query_groq(topic, tone, duration, hook_strength, chat_history):
    if not GROQ_API_KEY:
        return "Error: GROQ_API_KEY not found in environment secrets. Please add it in Settings > Secrets.", "", ""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    user_input = f"Topic: {topic}\nTone: {tone}\nTarget Duration: {duration}\nAction: Write a full YouTube script."
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
   
    messages.extend(chat_history[-6:])
    
    messages.append({"role": "user", "content": user_input})
    
    try:
        response = requests.post(GROQ_API_URL, headers=headers, json={
            "model": MODEL_NAME,
            "messages": messages,
            "temperature": hook_strength
        }, timeout=30)
        
        if response.status_code == 200:
            full_reply = response.json()["choices"][0]["message"]["content"]
            tts_script, scenes = parse_script(full_reply)
            return full_reply, tts_script, scenes
        else:
            return f"Error {response.status_code}: {response.text}", "", ""
    except Exception as e:
        return f"Request failed: {str(e)}", "", ""


css = """
footer {visibility: hidden}
"""

with gr.Blocks() as demo:
    gr.Markdown("# 🎬 ScriptForge AI: YouTube Script Master")
    gr.Markdown("Transform your video ideas into high-retention, audience-first scripts. *Powered by GROQ*")
    
    with gr.Row():
        with gr.Column(scale=1):
            topic = gr.Textbox(label="Video Topic/Description", placeholder="E.g., How to build a PC in 2025", lines=3)
            tone = gr.Dropdown(
                choices=["High Energy", "Storytelling", "Educational", "Minimalist", "Aggressive/Hype"], 
                label="Video Tone", 
                value="High Energy"
            )
            duration = gr.Dropdown(
                choices=["Shorts (<60s)", "Standard (5-10 mins)", "Deep Dive (15+ mins)"], 
                label="Target Duration", 
                value="Standard (5-10 mins)"
            )
            hook_strength = gr.Slider(minimum=0.1, maximum=1.5, value=0.7, step=0.1, label="Hook Strength (Creativity)")
            generate_btn = gr.Button("🚀 Generate Script", variant="primary")
            clear = gr.Button("Clear")

        with gr.Column(scale=2):
            with gr.Tabs():
                with gr.TabItem("Combined View"):
                    chatbot = gr.Chatbot(
                        value=[{"role": "assistant", "content": "Hi, my name is Script Forge: your YouTube script writer. Give me a topic so I can show my creativity."}],
                        height=500
                    )
                
                with gr.TabItem("TTS Only (Dialogue)"):
                    tts_output = gr.Textbox(label="Copy this for Text-to-Speech", lines=20)
                    download_btn = gr.Button("💾 Download Script (.txt)")
                    download_file = gr.File(label="Download prepared file")
                
                with gr.TabItem("Visuals Only (Shot List)"):
                    scenes_output = gr.Textbox(label="Video Scene Descriptions", lines=20)

  
    state = gr.State([{"role": "assistant", "content": "Hi, my name is Script Forge: your YouTube script writer. Give me a topic so I can show my creativity."}])

    def respond_wrapper(topic, tone, duration, hook_strength, chat_history):
        full_reply, tts_script, scenes = query_groq(topic, tone, duration, hook_strength, chat_history)
        chat_history.append({"role": "user", "content": topic})
        chat_history.append({"role": "assistant", "content": full_reply})
        return chat_history, tts_script, scenes

    generate_btn.click(
        respond_wrapper, 
        [topic, tone, duration, hook_strength, state], 
        [chatbot, tts_output, scenes_output]
    )
    
    download_btn.click(
        save_to_file,
        [tts_output],
        [download_file]
    )
    
    clear.click(
        lambda: (None, [{"role": "assistant", "content": "Hi, my name is Script Forge: your YouTube script writer. Give me a topic so I can show my creativity."}], "", "", None), 
        None, 
        [topic, chatbot, tts_output, scenes_output, download_file]
    )

if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft(), css=css)
