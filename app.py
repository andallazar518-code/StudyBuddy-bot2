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

if not PAGE_ACCESS_TOKEN or not GROQ_API_KEY:
    print("CRITICAL ERROR: Missing ENV Variables")

user_memory = {}
user_sessions = {}

# = BUONG AFFILIATE SYSTEM - HINDI TINANGGAL
MAIN_SHOPEE_STORE = "https://s.shopee.ph/qhsFU3xcr?smtt=0.0.9"
PRODUCT_MAP = {
    "calculator": {"name": "Casio fx-991EX", "shopee": "https://s.shopee.ph/903Zywb2BV?smtt=0.0.9"},
    "notebook": {"name": "National Notebook 80s", "shopee": "https://s.shopee.ph/BSBSox6US?smtt=0.0.9"},
    "laptop": {"name": "Lenovo Ideapad", "shopee": "https://s.shopee.ph/9AN0C8jKBb?smtt=0.0.9"},
    "mouse": {"name": "Wireless Mouse", "shopee": "https://s.shopee.ph/30mMqwHnbk?smtt=0.0.9"},
    "keyboard": {"name": "Mechanical Keyboard", "shopee": "https://s.shopee.ph/30mMqwHnbk?smtt=0.0.9"},
    "headset": {"name": "Gaming Headset", "shopee": "https://s.shopee.ph/30mMqwHnbk?smtt=0.0.9"},
    "bag": {"name": "JanSport Backpack", "shopee": "https://s.shopee.ph/5AqrQ58Yd1?smtt=0.0.9"},
    "lamp": {"name": "LED Study Lamp", "shopee": "https://s.shopee.ph/2Vq6FK56cb?smtt=0.0.9"},
}

def send_message(sender_id, text, quick_replies=None):
    text = text[:2000]
    # = BUG FIX: AUTO CLOSE CODE BLOCKS
    if text.count("```") % 2!= 0:
        text += "\n```"
    has_code = any(kw in text for kw in ["def ", "class ", "import ", "print(", "self.", "="])
    if has_code and "```" not in text:
        text = f"```\n{text}\n```"

    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "message": {"text": text}}
    if quick_replies: payload["message"]["quick_replies"] = quick_replies
    try: requests.post(url, json=payload, timeout=10)
    except: print("Send error")

def send_typing(sender_id, action="typing_on"):
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "sender_action": action}
    try: requests.post(url, json=payload, timeout=5)
    except: pass

def cleanup_memory():
    if len(user_memory) > 50:
        oldest = list(user_memory.keys())[0]
        del user_memory[oldest]

def handle_commands(user_message, sender_id):
    cleanup_memory()
    msg = user_message.lower().strip()

    # 1. NAME
    if "name is" in msg or "ako si" in msg:
        name = msg.replace("my name is", "").replace("name is", "").replace("ako si", "").strip()
        user_memory[sender_id] = {'name': name.title()}
        return f"👋 Welcome {name.title()}! All-Subject Tutor Mode ON"

    # 2. GREETING + BUTTONS
    if msg in ["hi", "hello", "hey", "kamusta"]:
        name = user_memory.get(sender_id, {}).get('name', 'Boss')
        qr = [
            {"content_type":"text", "title":"📚 Study Help", "payload":"study"},
            {"content_type":"text", "title":"💻 Code Help", "payload":"code"},
            {"content_type":"text", "title":"🛒 School Gear", "payload":"gear"}
        ]
        send_message(sender_id, f"**StudyBuddy PH v13.0** 🤖\nHi {name}!\n\nAsk me anything: Math, Science, English, History, Coding\n**Commands:**\n`explain:` `solve:` `gawa mo code:` `add task:`", qr)
        return "HANDLED"

    # 3. AFFILIATE CHECK
    for product, p in PRODUCT_MAP.items():
        if re.search(r'\b' + re.escape(product) + r'\b', msg):
            return f"💡 **{p['name']}**\nRecommended for students 👌\n\n**Shop:**\n{p['shopee']}"
    if any(k in msg for k in ["buy", "shop", "shopee", "gear"]):
        return f"🛒 **School Gear Store**\nAll your needs here:\n{MAIN_SHOPEE_STORE}"

    # 4. TODO SYSTEM
    if "add task" in msg:
        task = msg.replace("add task:", "").strip()
        if sender_id not in user_memory: user_memory[sender_id] = {}
        if 'tasks' not in user_memory[sender_id]: user_memory[sender_id]['tasks'] = []
        user_memory[sender_id]['tasks'].append(task)
        return f"✅ Task Added: `{task}`"
    if "my tasks" in msg:
        tasks = user_memory.get(sender_id, {}).get('tasks', [])
        if not tasks: return "Wala ka pang tasks 📝"
        return "📝 **Your Tasks:**\n" + "\n".join([f"{i+1}. `{t}`" for i,t in enumerate(tasks)])

    # 5. POMODORO
    if "pomodoro" in msg or "timer" in msg:
        try:
            minutes = int(''.join(filter(str.isdigit, msg)))
            return f"⏰ Timer set for {minutes} minutes! Focus mode ON. Kaya mo yan! 💪"
        except: return "⏰ Type `pomodoro 25`"

    return None

def ask_groq_all_subject(user_message):
    # = ANTI-COPYRIGHT
    if any(word in user_message.lower() for word in ["lyrics", "poem", "book chapter"]):
        return "Can't share that due to copyright 😅 Pero sa studies 100% kita"

    language = "Tagalog" if any(w in user_message.lower().split() for w in ["ng", "ang", "paano", "ano"]) else "English"
    models = ["llama-3.1-70b-versatile", "llama-3.1-8b-instant"]

    for model in models:
        try:
            prompt = f"""You are StudyBuddy PH AI. Expert tutor for ALL subjects: Math, Science, English, History, Filipino, BSIT, Coding.
            GOAL: Be a friendly teacher. Explain simply.
            CRITICAL RULES:
            1. Reply in {language}. Max 5 sentences. Use 1 emoji max.
            2. If MATH/SCIENCE: Show step by step solution.
            3. If CODING: Give FULL working code in ```language\ncode\n```. NEVER break f-strings. ALWAYS close ```.
            4. If ESSAY/ENGLISH/HISTORY: Give summary + key points.
            5. If "explain": Simple + 1 example.
            6. Never give lyrics, poems, or book passages.
            7. End with 1 question to help student learn more.

            Student: {user_message}
            Answer:"""
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
            data = {"model": model, "messages": [{"role": "user", "content": prompt}]}
            r = requests.post(url, headers=headers, json=data, timeout=20)
            r.raise_for_status()
            return r.json()['choices'][0]['message']['content']
        except: continue
    return "AI is busy 😅 Try again in 10s"

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
                    # = ANTI-SPAM
                    if sender_id in user_sessions and time.time() - user_sessions[sender_id] < 1:
                        continue
                    user_sessions[sender_id] = time.time()

                    if 'message' in event and 'text' in event['message']:
                        user_message = event['message']['text']
                        send_typing(sender_id, "typing_on")
                        time.sleep(0.4)
                        try:
                            cmd_reply = handle_commands(user_message, sender_id)
                            if cmd_reply == "HANDLED": pass
                            elif cmd_reply: send_message(sender_id, cmd_reply)
                            else:
                                ai_reply = ask_groq_all_subject(user_message)
                                send_message(sender_id, ai_reply)
                        except Exception as e:
                            print("MAIN ERROR:", e)
                            send_message(sender_id, "Ay sorry error 😅 Try mo ulit")
                        finally:
                            send_typing(sender_id, "typing_off")
        return "ok", 200

@app.route('/', methods=['GET'])
def home():
    return "StudyBuddy PH v13.0 ALL SUBJECT", 200
