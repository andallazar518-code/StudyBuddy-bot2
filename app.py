from flask import Flask, request
import requests
import os
import time
import re

app = Flask(__name__)
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
VERIFY_TOKEN = "TUBO2026"

user_sessions = {}

# = YOUR AFFILIATE LINK HERE - ALREADY PASTED =
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

def send_message(sender_id, text):
    text = text[:2000]
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "message": {"text": text}}
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Send error:", e)

def send_typing(sender_id, action="typing_on"):
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "sender_action": action}
    try:
        requests.post(url, json=payload, timeout=5)
    except:
        pass

def detect_language(text):
    text_lower = text.lower()
    if any(w in text_lower.split() for w in ["unsa", "ngano", "asa"]):
        return "Bisaya"
    if any(w in text_lower.split() for w in ["ng", "ang", "paano", "ano", "bakit"]):
        return "Tagalog"
    return "English"

def check_affiliate_intent(msg):
    msg = msg.lower()
    buy_words = ["buy", "shop", "shopee", "price", "link", "where to buy", "recommend", "gear"]
    return any(w in msg for w in buy_words)

def get_affiliate_reply(msg):
    msg = msg.lower()
    for product, p in PRODUCT_MAP.items():
        if re.search(r'\b' + re.escape(product) + r'\b', msg):
            return f"💡 **{p['name']}**\nRecommended 👌\n\n{p['shopee']}\n\n*Affiliate link*"
    if any(k in msg for k in ["buy", "shop", "shopee", "gear", "link"]):
        return f"🛒 **My Recommended Store** 👇\n\n{MAIN_SHOPEE_STORE}\n\n*Affiliate link*"
    return None

def ask_groq(user_message):
    language = detect_language(user_message)
    try:
        prompt = f"""You are StudyBuddy PH v16.0 - A Friendly AI Assistant.

PERSONALITY: Helpful, kind, conversational. Like talking to a smart friend.
LANGUAGE: Reply in {language}.

RULES:
1. Answer EVERY question the user asks.
2. Be natural, not robotic. Max 6 sentences.
3. If you don't know, say so and suggest how to find out.

User: {user_message}"""
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        data = {"model": "llama-3.1-70b-versatile", "messages": [{"role": "user", "content": prompt}]}
        r = requests.post(url, headers=headers, json=data, timeout=20)
        return r.json()['choices'][0]['message']['content']
    except Exception as e:
        print("Groq error:", e)
        return "Sorry, I'm busy right now 😅 Try again in a bit"

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
                        if 'message' in event and 'attachments' in event['message']:
                            send_message(sender_id, "I can't see images or files here yet 😅\n\nJust type your question and I'll answer it!")
                            continue

                        if 'message' in event and 'text' in event['message']:
                            user_message = event['message']['text']

                            if check_affiliate_intent(user_message):
                                affiliate_reply = get_affiliate_reply(user_message)
                                if affiliate_reply:
                                    send_message(sender_id, affiliate_reply)
                                    continue

                            ai = ask_groq(user_message)
                            send_message(sender_id, ai)
                    except Exception as e:
                        print("ERROR:", e)
                        send_message(sender_id, "Something went wrong 😅")
                    finally:
                        send_typing(sender_id, "typing_off")
        return "ok", 200

@app.route('/', methods=['GET'])
def home():
    return "StudyBuddy AI v16.0", 200
