import gradio as gr
import os
import requests
import re

# Load GROQ API key from environment
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL_NAME = "llama3-8b-8192"

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
    # Extract [SCRIPT] parts for TTS
    script_parts = re.findall(r'\[SCRIPT\]:(.*?)(?=\[SCENE DESCRIPTION\]|$)', full_text, re.DOTALL | re.IGNORECASE)
    clean_script = "\n".join([p.strip() for p in script_parts])
    
    # Extract [SCENE DESCRIPTION] parts for Visuals
    scene_parts = re.findall(r'\[SCENE DESCRIPTION\]:(.*?)(?=\[SCRIPT\]|$)', full_text, re.DOTALL | re.IGNORECASE)
    clean_scenes = "\n".join([p.strip() for p in scene_parts])
    
    # Calculate stats
    word_count = len(clean_script.split())
    # Est duration: ~150 words per minute
    duration_minutes = word_count / 150
    minutes = int(duration_minutes)
    seconds = int((duration_minutes - minutes) * 60)
    duration_str = f"{minutes}m {seconds}s"
    
    return clean_script, clean_scenes, word_count, duration_str

def query_groq(topic, tone, duration, hook_strength, chat_history):
    if not GROQ_API_KEY:
        return "Error: GROQ_API_KEY not found in environment secrets. Please add it in Settings > Secrets.", "", "", 0, "0m 0s"

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    user_input = f"Topic: {topic}\nTone: {tone}\nTarget Duration: {duration}\nAction: Write a full YouTube script."
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    # Add history for context (optional but helpful)
    for user, bot in chat_history[-3:]: # Keep last 3 exchanges to avoid context bloat
        messages.append({"role": "user", "content": user})
        messages.append({"role": "assistant", "content": bot})
    
    messages.append({"role": "user", "content": user_input})
    
    try:
        response = requests.post(GROQ_API_URL, headers=headers, json={
            "model": MODEL_NAME,
            "messages": messages,
            "temperature": hook_strength
        }, timeout=30)
        
        if response.status_code == 200:
            full_reply = response.json()["choices"][0]["message"]["content"]
            tts_script, scenes, wc, dur = parse_script(full_reply)
            return full_reply, tts_script, scenes, wc, dur
        else:
            return f"Error {response.status_code}: {response.text}", "", "", 0, "0m 0s"
    except Exception as e:
        return f"Request failed: {str(e)}", "", "", 0, "0m 0s"

def respond(topic, tone, duration, hook_strength, chat_history):
    full_reply, tts_script, scenes, wc, dur = query_groq(topic, tone, duration, hook_strength, chat_history)
    chat_history.append((topic, full_reply))
    return chat_history, tts_script, scenes, f"{wc} words", dur

css = """
footer {visibility: hidden}
.stat-box { 
    background-color: #f0f2f6; 
    padding: 10px; 
    border-radius: 10px; 
    text-align: center;
    border: 1px solid #ddd;
}
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
            with gr.Row():
                word_count_display = gr.Textbox(label="Word Count", interactive=False, elem_classes="stat-box")
                duration_display = gr.Textbox(label="Est. Speaking Time", interactive=False, elem_classes="stat-box")
            
            with gr.Tabs():
                with gr.TabItem("Combined View"):
                    chatbot = gr.Chatbot(height=500)
                
                with gr.TabItem("TTS Only (Dialogue)"):
                    tts_output = gr.Textbox(label="Copy this for Text-to-Speech", lines=20)
                
                with gr.TabItem("Visuals Only (Shot List)"):
                    scenes_output = gr.Textbox(label="Video Scene Descriptions", lines=20)

    # State for history
    state = gr.State([])

    generate_btn.click(
        respond, 
        [topic, tone, duration, hook_strength, state], 
        [chatbot, tts_output, scenes_output, word_count_display, duration_display]
    )
    
    clear.click(lambda: (None, "", "", "", "", []), None, [topic, chatbot, tts_output, scenes_output, word_count_display, duration_display])

if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft(), css=css)
