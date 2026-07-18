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

# = 1. BUONG AFFILIATE - 8 PRODUCTS BUO PA RIN
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
    text = text[:2000]
    # = BUG FIX 1: AUTO CLOSE CODE
    if text.count("```") % 2!= 0: text += "\n```"
    has_code = any(kw in text for kw in ["def ", "class ", "import ", "print(", "self.", "="])
    if has_code and "```" not in text: text = f"```\n{text}\n```"
    url = f"https://facebook.com{PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "message": {"text": text}}
    if quick_replies: payload["message"]["quick_replies"] = quick_replies
    try: 
        r = requests.post(url, json=payload, timeout=10)
        # Detailed logging to find out exactly why Facebook didn't send the reply
        if r.status_code != 200:
            print(f"FB Error Code {r.status_code}: {r.text}")
    except Exception as e: 
        print(f"Send network error: {e}")

def send_typing(sender_id, action="typing_on"):
    url = f"https://facebook.com{PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "sender_action": action}
    try: requests.post(url, json=payload, timeout=5)
    except: pass

def cleanup_memory():
    if len(user_memory) > 50:
        oldest = list(user_memory.keys())[0]
        del user_memory[oldest]

def detect_language(text):
    bisaya = ["unsa", "ngano", "asa"]
    tagalog = ["ng", "ang", "paano", "ano"]
    if any(w in text.lower().split() for w in bisaya): return "Bisaya"
    if any(w in text.lower().split() for w in tagalog): return "Tagalog"
    return "English"

def handle_commands(user_message, sender_id):
    cleanup_memory()
    if sender_id not in user_memory: user_memory[sender_id] = {'name': 'Boss', 'notes': [], 'tasks': []}
    msg = user_message.lower().strip()

    # 2. NAME
    if "name is" in msg or "ako si" in msg:
        name = msg.replace("my name is", "").replace("name is", "").replace("ako si", "").strip()
        user_memory[sender_id]['name'] = name.title()
        return f"👋 Welcome {name.title()}! GOD MODE ON"

    # 3. GREETING
    if msg in ["hi", "hello", "hey", "kamusta"]:
        name = user_memory.get(sender_id, {}).get('name', 'Boss')
        qr = [
            {"content_type":"text", "title":"🚀 Ask AI", "payload":"ask_ai"},
            {"content_type":"text", "title":"💻 Code", "payload":"code"},
            {"content_type":"text", "title":"📸 Vision", "payload":"vision"},
            {"content_type":"text", "title":"🛒 Gear", "payload":"gear"}
        ]
        send_message(sender_id, f"**Assistant Pro v14.1** 🤖\(\nHi {name}!\\)n\nSend: Text, Image, PDF, Voice\nCommands: `quiz me`, `save note:`, `add task:`", qr)
        return "HANDLED"

    # 4. AFFILIATE - BUO PA RIN
    for product, p in PRODUCT_MAP.items():
        if re.search(r'\b' + re.escape(product) + r'\b', msg):
            return f"💡 **{p['name']}**\nRecommended 👌\n\n**Shop:**\n{p['shopee']}"
    if any(k in msg for k in ["buy", "shop", "shopee", "gear"]):
        return f"🛒 **School Gear Store**\nAll needs:\n{MAIN_SHOPEE_STORE}"

    # 5. TODO - HINDI TINANGGAL
    if "add task" in msg:
        task = msg.replace("add task:", "").strip()
        user_memory[sender_id]['tasks'].append(task)
        return f"✅ Task Added: `{task}`"
    if "my tasks" in msg:
        tasks = user_memory[sender_id]['tasks'] if sender_id in user_memory else []
        if not tasks: return "Wala ka pang tasks 📝"
        return "📝 **Your Tasks:**\n" + "\n".join([f"{i+1}. `{t}`" for i,t in enumerate(tasks)])

    # 6. NOTES - BAGO
    if "save note:" in msg:
        note = msg.replace("save note:", "").strip()
        user_memory[sender_id]['notes'].append(note)
        return f"✅ Note Saved: `{note}`"
    if "my notes" in msg:
        notes = user_memory[sender_id]['notes'] if sender_id in user_memory else []
        if not notes: return "Wala ka pang notes 📝"
        return "📝 **Your Notes:**\n" + "\n".join([f"{i+1}. `{n}`" for i,n in enumerate(notes)])

    # 7. QUIZ - BAGO
    if "quiz me" in msg:
        subject = msg.replace("quiz me", "").strip()
        return f"📝 **Quiz: {subject.title()}**\nQ1: Explain {subject} in 1 sentence. Go! 💪"

    # 8. POMODORO - HINDI TINANGGAL
    if "pomodoro" in msg:
        try:
            minutes = int(''.join(filter(str.isdigit, msg)))
            return f"⏰ Timer set for {minutes} minutes! Focus! 💪"
        except: return "⏰ Type `pomodoro 25`"

    # 9. MOOD
    if any(w in msg for w in ["pagod", "stress", "hirap"]):
        return random.choice(["Laban lang! 5 min break ☕", "Kaya mo yan! One step at a time 😊"])

    return None

def ask_groq_text(user_message):
    if any(word in user_message.lower() for word in ["lyrics", "poem"]):
        return "Can't share that due to copyright 😅"
    language = detect_language(user_message)
    models = ["llama-3.3-70b-versatile", "llama3-8b-8192"]
    for model in models:
        try:
            prompt = f"You are an advanced, versatile AI Assistant. Answer all questions directly and intelligently. Reply in {language}. Enclose code within ```."
            url = "https://groq.com"
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
            data = {"model": model, "messages": [{"role": "user", "content": prompt + f"\n\nUser: {user_message}"}]}
            r = requests.post(url, headers=headers, json=data, timeout=20)
            return r.json()['choices'][0]['message']['content']
        except: continue
    return "AI busy 😅"

def ask_groq_vision(image_url, caption):
    language = detect_language(caption)
    try:
        prompt = f"You are an advanced AI Assistant with vision. Analyze this image thoroughly and fulfill this prompt completely: {caption or 'Analyze image'}. Reply in {language}."
        url = "https://groq.com"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        data = {"model": "llama-3.2-11b-vision-preview", "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": image_url}}]}]}
        r = requests.post(url, headers=headers, json=data, timeout=30)
        return r.json()['choices'][0]['message']['content']
    except: return "Can't read image 😅"

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge"), 200
        return "Error", 403

    if request.method == 'POST':
        data = request.get_json()
        if data.get('object') == 'page':
            for entry in data.get('entry', []):
                for event in entry.get('messaging', []):
                    sender_id = event['sender']['id']
                    if sender_id in user_sessions and time.time() - user_sessions[sender_id] < 1.2:
                        continue
                    
                    user_sessions[sender_id] = time.time()
                    send_typing(sender_id, "typing_on")

                    # Handle Images
                    if 'message' in event and 'attachments' in event['message']:
                        for attach in event['message']['attachments']:
                            if attach.get('type') == 'image':
                                reply = ask_groq_vision(attach['payload']['url'], event['message'].get('text', ''))
                                send_message(sender_id, reply)
                        send_typing(sender_id, "typing_off")
                        continue

                    # Handle Text
                    if 'message' in event and 'text' in event['message']:
                        user_text = event['message']['text']
                        command_reply = handle_commands(user_text, sender_id)
                        
                        if command_reply == "HANDLED":
                            send_typing(sender_id, "typing_off")
                            continue
                        elif command_reply:
                            send_message(sender_id, command_reply)
                        else:
                            send_message(sender_id, ask_groq_text(user_text))

                    send_typing(sender_id, "typing_off")
        return "EVENT_RECEIVED", 200
