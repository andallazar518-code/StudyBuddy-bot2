from flask import Flask, request
import google.generativeai as genai
import requests
import os
import time
import random

app = Flask(__name__)

# = SET MO TO SA RENDER ENV VARS
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = "TUBO2026"

GENERIC_LINK_SHOPEE = "https://s.shopee.ph/qhsFU3xcr?smtt=0.0.9"

# = 20 ITEMS = SHOPEE ONLY
PRODUCT_MAP = {
    "calculator": {"name": "Casio fx-991EX", "shopee": "https://s.shopee.ph/903Zywb2BV"},
    "notebook": {"name": "National Notebook 80s", "shopee": "https://s.shopee.ph/BSBSox6US"},
    "bag": {"name": "JanSport Backpack", "shopee": "https://s.shopee.ph/5AqrQ58Yd1"},
    "pen": {"name": "Pilot G2 0.5 Gel Pen", "shopee": "https://s.shopee.ph/AAFXNKQ3JD"},
    "lamp": {"name": "LED Study Lamp", "shopee": "https://s.shopee.ph/2Vq6FK56cb"},
    "highlighter": {"name": "Zebra Mildliner", "shopee": "https://s.shopee.ph/7KvM0GTd26"},
    "earphones": {"name": "TWS i12 Earphones", "shopee": "https://s.shopee.ph/3qLTptaf8f"},
    "headset": {"name": "JBL Headset", "shopee": "https://s.shopee.ph/8V7JOZxv8i"},
    "mouse": {"name": "Logitech M221", "shopee": "https://s.shopee.ph/3LPDF9KEgu"},
    "keyboard": {"name": "Mechanical Keyboard 60%", "shopee": "https://s.shopee.ph/2LWg3OZZ8m"},
    "laptop": {"name": "Lenovo Ideapad", "shopee": "https://s.shopee.ph/9AN0C8jKBb"},
    "phone": {"name": "Tecno", "shopee": "https://s.shopee.ph/30mMqwHnbk"},
    "tablet": {"name": "Xiaomi Pad 8", "shopee": "https://s.shopee.ph/9zw7BuiTnq"},
    "powerbank": {"name": "Orashare", "shopee": "https://s.shopee.ph/8pk9nssxgj"},
    "chair": {"name": "Study Chair", "shopee": "https://s.shopee.ph/3B5n3bxDay"},
    "table": {"name": "Foldable Study Table", "shopee": "https://s.shopee.ph/9KgQP0uXPG"},
    "ringlight": {"name": "10inch Ring Light", "shopee": "https://s.shopee.ph/1BKig5InOJ"},
    "fan": {"name": "USB Mini Fan", "shopee": "https://s.shopee.ph/7KvM1WX2k9"},
    "organizer": {"name": "Desk Organizer", "shopee": "https://s.shopee.ph/6AjOdQwGtB"},
    "glasses": {"name": "Anti-Radiation Glasses", "shopee": "https://s.shopee.ph/3B5n3yEf2m"},
}

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash-latest') # = PINAYAT NA MODEL

chat_sessions = {} # = pinasimple
rate_limit = {}
link_sent = {}
link_request_count = {}

GREETINGS = [
    "Uy! Ako si Study Buddy AI 🤖\n\nType ka lang ng question mo. Math, Science, English = Kaya ko yan.",
    "Yo! Kamusta? 🤓\nAno pag-aaralan natin today?"
]
ERROR_REPLIES = ["Ay sorry, nag-lag ako saglit 😅 Try mo ulit send."]
SOFT_SELL_LINES = ["\nNeed mo ba ng study gamit? Check mo dito: {s}"]

def is_rate_limited(user_id, limit=10, window=60):
    now = time.time()
    if user_id not in rate_limit: rate_limit[user_id] = []
    rate_limit[user_id] = [t for t in rate_limit[user_id] if now - t < window]
    if len(rate_limit[user_id]) >= limit: return True
    rate_limit[user_id].append(now)
    return False

def send_message(sender_id, text):
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "message": {"text": text[:2000]}}
    try:
        requests.post(url, json=payload, timeout=5)
        time.sleep(0.5) # = safe kay Meta
    except Exception as e:
        print(f"Error sending: {e}")

def check_product(user_message):
    user_message = user_message.lower()
    for product, p in PRODUCT_MAP.items():
        if product in user_message:
            return f"\n\n💡 {p['name']}\nShopee: {p['shopee']}"
    return ""

def get_ai_response(user_id, user_message):
    if user_id not in chat_sessions: chat_sessions[user_id] = []
    chat_sessions[user_id].append({"role": "user", "parts": [user_message]})
    chat_sessions[user_id] = chat_sessions[user_id][-6:] # = max 6 turns lang

    prompt = "Ikaw si Study Buddy AI. Sumagot ng TAGALOG. Max 4 sentences. Friendly ka.\n\n"
    for msg in chat_sessions[user_id]:
        prompt += f"{msg['role']}: {msg['parts'][0]}\n"

    try:
        response = model.generate_content(prompt)
        ai_text = response.text
        chat_sessions[user_id].append({"role": "model", "parts": [ai_text]})
        return ai_text
    except Exception as e:
        print(f"AI Error: {e}")
        return random.choice(ERROR_REPLIES)

def is_link_ok(text):
    text = text.lower()
    return "link" in text or "shopee" in text or "bili" in text or "saan" in text

# = WEBHOOK
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

                    if is_rate_limited(sender_id):
                        send_message(sender_id, "Ang bilis mo boss 😅 Wait 1 min")
                        continue

                    if 'message' in event and 'text' in event['message']:
                        user_message = event['message']['text']

                        # = PRODUCT DETECT
                        product_reply = check_product(user_message)

                        # = PAG NAG-REQUEST NG LINK
                        if is_link_ok(user_message) and not link_sent.get(sender_id, False):
                            if link_request_count.get(sender_id, 0) <= 2:
                                product_reply = f"Shopee: {GENERIC_LINK_SHOPEE}"
                                link_sent[sender_id] = True
                                link_request_count[sender_id] = link_request_count.get(sender_id, 0) + 1

                        ai_text = get_ai_response(sender_id, user_message)

                        # = SOFT SELL 30% CHANCE
                        if not product_reply and random.random() < 0.3:
                            product_reply = random.choice(SOFT_SELL_LINES).format(s=GENERIC_LINK_SHOPEE)

                        final_reply = ai_text + product_reply
                        send_message(sender_id, final_reply)
        return "ok", 200

@app.route('/', methods=['GET'])
def home():
    return "StudyBuddy Bot is Live", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
