import gradio as gr
import os
import requests
import re

# Load GROQ API key from environment
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL_NAME = "llama-3.1-8b-instant"

SYSTEM_PROMPT = """You are 'ScriptForge AI', a professional YouTube Script Writer.
Your goal is to write highly engaging, audience-first scripts in the 2nd person (using 'You', 'Your').
Talk directly to the viewer as if you are the creator speaking to the camera.

FORMATTING RULES:
1. Every script must alternate between [SCENE DESCRIPTION] and [SCRIPT].
2. [SCENE DESCRIPTION] should describe the visuals, camera angles, or B-roll.
3. [SCRIPT] should be the actual spoken words.
4. Structure the script with a Hook, Intro, Main Points, and a Call to Action (CTA).
5. Maintain the requested Tone and Duration.

Example:
[SCENE DESCRIPTION]: Close-up of the product.
[SCRIPT]: You need to see this to believe it.
"""

def parse_script(full_text):
    # Improved regex: Handles optional colons, bolding (**), and case variations
    # Extract [SCRIPT] parts
    script_parts = re.findall(r'\[?SCRIPT\]?:?\s*(.*?)(?=\[?SCENE DESCRIPTION\]?|$)', full_text, re.DOTALL | re.IGNORECASE)
    clean_script = "\n".join([p.strip().replace("**", "") for p in script_parts if p.strip()])
    
    # Extract [SCENE DESCRIPTION] parts
    scene_parts = re.findall(r'\[?SCENE DESCRIPTION\]?:?\s*(.*?)(?=\[?SCRIPT\]?|$)', full_text, re.DOTALL | re.IGNORECASE)
    clean_scenes = "\n".join([p.strip().replace("**", "") for p in scene_parts if p.strip()])
    
    # Fallback: If parsing fails but we have text, assume the whole thing is the script
    if not clean_script and full_text:
        clean_script = full_text
        
    return clean_script, clean_scenes

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
    # Add history for context (keep last 6 messages / 3 turns)
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

    # State for history (initially contains the welcome message)
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
