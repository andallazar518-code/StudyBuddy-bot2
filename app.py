from flask import Flask, request
import requests
import os
import time
import random
import re

app = Flask(__name__)

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
VERIFY_TOKEN = "TUBO2026"

user_memory = {}
user_sessions = {}

# = 1. AFFILIATE LINKS - 100% ALIVE AND INTACT
MAIN_SHOPEE_STORE = "https://shopee.ph"
PRODUCT_MAP = {
    "calculator": {"name": "Casio fx-991EX", "shopee": "https://shopee.ph"},
    "notebook": {"name": "National Notebook 80s", "shopee": "https://shopee.ph"},
    "laptop": {"name": "Lenovo Ideapad", "shopee": "https://shopee.ph"},
    "mouse": {"name": "Wireless Mouse", "shopee": "https://shopee.ph"},
    "keyboard": {"name": "Mechanical Keyboard", "shopee": "https://shopee.ph"},
    "headset": {"name": "Gaming Headset", "shopee": "https://shopee.ph"},
    "bag": {"name": "JanSport Backpack", "shopee": "https://shopee.ph"},
    "lamp": {"name": "LED Study Lamp", "shopee": "https://shopee.ph"},
}

def send_message(sender_id, text, quick_replies=None):
    if not text: return
    text = str(text)[:2000]
    # AUTO CLOSE CODE BLOCKS
    if text.count("```") % 2 != 0: text += "\n```"
    has_code = any(kw in text for kw in ["def ", "class ", "import ", "print(", "self.", "="])
    if has_code and "```" not in text: text = f"```\n{text}\n```"
    
    url = f"https://facebook.com{PAGE_ACCESS_TOKEN or ''}"
    payload = {"recipient": {"id": sender_id}, "message": {"text": text}}
    if quick_replies: payload["message"]["quick_replies"] = quick_replies
    try: 
        requests.post(url, json=payload, timeout=10)
    except Exception as e: 
        print(f"FB Send Message Error: {e}")

def send_typing(sender_id, action="typing_on"):
    url = f"https://facebook.com{PAGE_ACCESS_TOKEN or ''}"
    payload = {"recipient": {"id": sender_id}, "sender_action": action}
    try: requests.post(url, json=payload, timeout=5)
    except: pass

def cleanup_memory():
    if len(user_memory) > 200:
        oldest = list(user_memory.keys())[0]
        del user_memory[oldest]

def detect_language(text):
    bisaya = ["unsa", "ngano", "asa"]
    tagalog = ["ng", "ang", "paano", "ano"]
    if any(w in text.lower().split() for w in bisaya): return "Bisaya"
    if any(w in text.lower().split() for w in tagalog): return "Tagalog"
    return "English"

def init_user_memory(sender_id):
    if sender_id not in user_memory:
        user_memory[sender_id] = {
            'name': 'Boss',
            'notes': [],
            'tasks': []
        }

def handle_commands(user_message, sender_id):
    cleanup_memory()
    init_user_memory(sender_id)
    msg = user_message.lower().strip()

    # NAME COMMANDS
    if "name is" in msg or "ako si" in msg:
        name = msg.replace("my name is", "").replace("name is", "").replace("ako si", "").strip()
        user_memory[sender_id]['name'] = name.title()
        return f"👋 Welcome {name.title()}! GOD MODE ON"

    # GREETINGS
    if msg in ["hi", "hello", "hey", "kamusta"]:
        name = user_memory[sender_id]['name']
        qr = [
            {"content_type":"text", "title":"🚀 Ask AI", "payload":"ask_ai"},
            {"content_type":"text", "title":"💻 Code", "payload":"code"},
            {"content_type":"text", "title":"📸 Vision", "payload":"vision"},
            {"content_type":"text", "title":"🛒 Gear", "payload":"gear"}
        ]
        send_message(sender_id, f"**Assistant Pro v14.1** 🤖\nHi {name}!\n\nI can answer ANY question or task you have.\n\nCommands:\n`save note: [text]` \n`add task: [text]`", qr)
        return "HANDLED"

    # AFFILIATE KEYWORDS
    for product, p in PRODUCT_MAP.items():
        if re.search(r'\b' + re.escape(product) + r'\b', msg):
            return f"💡 **{p['name']}**\nRecommended 👌\n\n**Shop:**\n{p['shopee']}"
    if any(k in msg for k in ["buy", "shop", "shopee", "gear"]):
        return f"🛒 **School Gear Store**\nAll needs:\n{MAIN_SHOPEE_STORE}"

    # TODO TASKS
    if "add task" in msg:
        task = msg.replace("add task:", "").strip()
        user_memory[sender_id]['tasks'].append(task)
        return f"✅ Task Added: `{task}`"
    if "my tasks" in msg:
        tasks = user_memory[sender_id]['tasks']
        if not tasks: return "Wala ka pang tasks 📝"
        return "📝 **Your Tasks:**\n" + "\n".join([f"{i+1}. `{t}`" for i,t in enumerate(tasks)])

    # NOTES
    if "save note:" in msg:
        note = msg.replace("save note:", "").strip()
        user_memory[sender_id]['notes'].append(note)
        return f"✅ Note Saved: `{note}`"
    if "my notes" in msg:
        notes = user_memory[sender_id]['notes']
        if not notes: return "Wala ka pang notes 📝"
        return "📝 **Your Notes:**\n" + "\n".join([f"{i+1}. `{n}`" for i,n in enumerate(notes)])

    # QUIZ
    if "quiz me" in msg:
        subject = msg.replace("quiz me", "").strip()
        return f"📝 **Quiz: {subject.title()}**\nQ1: Explain {subject} in 1 sentence. Go! 💪"

    # POMODORO
    if "pomodoro" in msg:
        try:
            minutes = int(''.join(filter(str.isdigit, msg)))
            return f"⏰ Timer set for {minutes} minutes! Focus! 💪"
        except: return "⏰ Type `pomodoro 25`"

    # MOOD
    if any(w in msg for w in ["pagod", "stress", "hirap"]):
        return random.choice(["Laban lang! 5 min break ☕", "Kaya mo yan! One step at a time 😊"])

    return None

def ask_groq_text(user_message):
    if any(word in user_message.lower() for word in ["lyrics", "poem"]):
        return "Can't share that due to copyright restrictions 😅"
        
    language = detect_language(user_message)
    # Production-ready models
    models = ["llama3-70b-8192", "llama3-8b-8192"]
    
    for model in models:
        try:
            prompt = f"You are an advanced, multi-purpose AI Assistant. Answer all questions or requests directly, comprehensively, and intelligently. Reply in {language}. Enclose all code within ```."
            url = "https://groq.com"
            headers = {
                "Authorization": f"Bearer {GROQ_API_KEY or ''}", 
                "Content-Type": "application/json"
            }
            data = {
                "model": model, 
                "messages": [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_message}
                ]
            }
            r = requests.post(url, headers=headers, json=data, timeout=15)
            res_json = r.json()
            if 'choices' in res_json and len(res_json['choices']) > 0:
                return res_json['choices'][0]['message']['content']
        except Exception as e: 
            print(f"Groq Text Error ({model}): {e}")
            continue
    return "AI is handling too many requests right now. Try again! 😅"

def ask_groq_vision(image_url, caption):
    if not GROQ_API_KEY:
        return "Vision Engine configuration error: Key missing."
    language = detect_language(caption if caption else "")
    try:
        prompt = f"You are an advanced AI Assistant with computer vision. Analyze this image thoroughly and fulfill this prompt completely: {caption or 'Analyze image'}. Reply in {language}."
        url = "https://groq.com"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}", 
            "Content-Type": "application/json"
        }
        data = {
            "model": "llama-3.2-11b-vision-preview", 
            "messages": [{
                "role": "user", 
                "content": [
                    {"type": "text", "text": prompt}, 
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }]
        }
        r = requests.post(url, headers=headers, json=data, timeout=20)
        res_json = r.json()
        if 'choices' in res_json and len(res_json['choices']) > 0:
            return res_json['choices'][0]['message']['content']
    except Exception as e: 
        print(f"Groq Vision Error: {e}")
    return "Could not process the image layout successfully 😅"

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200
        return "Error Verification Failed", 403

    if request.method == 'POST':
        try:
            data = request.get_json() or {}
            if data.get('object') == 'page':
                for entry in data.get('entry', []):
                    for event in entry.get('messaging', []):
                        sender_id = event.get('sender', {}).get('id')
                        if not sender_id: continue
                        
                        # Anti-spam logic
                        if sender_id in user_sessions and time.time() - user_sessions[sender_id] < 1.2:
                            continue
                        user_sessions[sender_id] = time.time()

                        send_typing(sender_id, "typing_on")

                        # Handle Images/Media
                        if 'message' in event and 'attachments' in event['message']:
                            for attach in event['message']['attachments']:
                                if attach.get('type') == 'image':
                                    img_url = attach.get('payload', {}).get('url')
                                    caption = event['message'].get('text', '')
                                    if img_url:
                                        reply = ask_groq_vision(img_url, caption)
