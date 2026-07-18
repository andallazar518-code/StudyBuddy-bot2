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

# = 1. AFFILIATE - MAS APPEALING NA =
MAIN_SHOPEE_STORE = "https://s.shopee.ph/qhsFU3xcr?smtt=0.0.9"
PRODUCT_MAP = {
    "calculator": {"name": "Casio fx-991EX Scientific", "shopee": "https://s.shopee.ph/903Zywb2BV?smtt=0.0.9", "hook": "Perfect for STEM students 📐"},
    "notebook": {"name": "National Notebook 80s", "shopee": "https://s.shopee.ph/BSBSox6US?smtt=0.0.9", "hook": "Best for notes and reviewers 📓"},
    "laptop": {"name": "Lenovo Ideapad Laptop", "shopee": "https://s.shopee.ph/9AN0C8jKBb?smtt=0.0.9", "hook": "For school, work, and gaming 💻"},
    "mouse": {"name": "Wireless Mouse", "shopee": "https://s.shopee.ph/30mMqwHnbk?smtt=0.0.9", "hook": "Smooth and ergonomic 🖱️"},
    "keyboard": {"name": "Mechanical Keyboard RGB", "shopee": "https://s.shopee.ph/30mMqwHnbk?smtt=0.0.9", "hook": "Level up your typing and gaming ⌨️"},
    "headset": {"name": "Gaming Headset with Mic", "shopee": "https://s.shopee.ph/30mMqwHnbk?smtt=0.0.9", "hook": "Clear sound for class and games 🎧"},
    "bag": {"name": "JanSport Backpack", "shopee": "https://s.shopee.ph/5AqrQ58Yd1?smtt=0.0.9", "hook": "Durable for daily school use 🎒"},
    "lamp": {"name": "LED Study Lamp", "shopee": "https://s.shopee.ph/2Vq6FK56cb?smtt=0.0.9", "hook": "Protect your eyes while studying 💡"},
}

def send_message(sender_id, text):
    text = text[:2000]
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "message": {"text": text}}
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        print("Send error")

def send_typing(sender_id, action="typing_on"):
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "sender_action": action}
    try:
        requests.post(url, json=payload, timeout=5)
    except:
        pass

def cleanup_memory():
    if len(user_memory) > 50:
        oldest = list(user_memory.keys())[0]
        del user_memory[oldest]

def detect_language(text):
    bisaya = ["unsa", "ngano", "asa"]
    tagalog = ["ng", "ang", "paano", "ano"]
    if any(w in text.lower().split() for w in bisaya):
        return "Bisaya"
    if any(w in text.lower().split() for w in tagalog):
        return "Tagalog"
    return "English"

def handle_commands(user_message, sender_id):
    cleanup_memory()
    msg = user_message.lower().strip()

    # 1. NAME
    if "name is" in msg or "ako si" in msg:
        name = msg.replace("my name is", "").replace("name is", "").replace("ako si", "").strip()
        if sender_id not in user_memory: user_memory[sender_id] = {}
        user_memory[sender_id]['name'] = name.title()
        return f"👋 Welcome {name.title()}! Nice to meet you 😊"

    # 2. GREETING
    if msg in ["hi", "hello", "hey", "kamusta"]:
        name = user_memory.get(sender_id, {}).get('name', 'Boss')
        send_message(sender_id, f"**StudyBuddy v14.4** 🤖\nHi {name}!\n\nAsk me anything. I'm here to help 😊")
        return "HANDLED"

    # 3. AFFILIATE - MAS APPEALING
    for product, p in PRODUCT_MAP.items():
        if re.search(r'\b' + re.escape(product) + r'\b', msg):
            return f"💡 **I recommend: {p['name']}**\n\n{p['hook']}\n\n🔥 **Check it here:**\n{p['shopee']}\n\n*Affiliate link - helps support this bot*"

    if any(k in msg for k in ["buy", "shop", "shopee", "gear", "recommend", "link"]):
        return f"🛒 **My Top Pick Store for Students**\n\nEverything you need for school in 1 place 👇\n\n{MAIN_SHOPEE_STORE}\n\n*Affiliate link - thanks for supporting!*"

    # 4. MOOD
    if any(w in msg for w in ["pagod", "stress", "hirap", "sad"]):
        return random.choice([
            "Laban lang! Take a 5 min break ☕ You got this!",
            "Kaya mo yan! One step at a time 😊 I'm here for you",
            "Rest muna if needed. Then balik tayo 💪"
        ])

    return None

def ask_groq(user_message): # PURE AI
    if any(word in user_message.lower() for word in ["lyrics", "poem"]):
        return "Can't share that due to copyright 😅 Pero ask me anything else!"

    language = detect_language(user_message)
    models = ["llama-3.1-70b-versatile", "llama-3.1-8b-instant"]
    for model in models:
        try:
            prompt = f"""You are StudyBuddy PH v14.4. A friendly and smart AI Assistant.
Reply in {language}. Be helpful, kind, and conversational. Max 6 sentences.
Answer EVERY question the user asks.
User: {user_message}"""
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
            data = {"model": model, "messages": [{"role": "user", "content": prompt}]}
            r = requests.post(url, headers=headers, json=data, timeout=20)
            if r.status_code == 200:
                return r.json()['choices'][0]['message']['content']
        except:
            continue
    return "AI busy 😅"

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
                    time.sleep(0.3)
                    try:
                        # BLOCK ATTACHMENTS
                        if 'message' in event and 'attachments' in event['message']:
                            send_message(sender_id, "I can only reply to text messages for now 😅")
                            continue

                        if 'message' in event and 'text' in event['message']:
                            user_message = event['message']['text']
                            cmd = handle_commands(user_message, sender_id)
                            if cmd == "HANDLED":
                                pass
                            elif cmd:
                                send_message(sender_id, cmd)
                            else:
                                ai = ask_groq(user_message)
                                send_message(sender_id, ai)
                    except Exception as e:
                        print("ERROR:", e)
                        send_message(sender_id, "Error 😅")
                    finally:
                        send_typing(sender_id, "typing_off")
        return "ok", 200

@app.route('/', methods=['GET'])
def home():
    return "StudyBuddy v14.4 FULL", 200
