from flask import Flask, request
import requests
import os
import time
import random
import re
from supabase import create_client

app = Flask(__name__)
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
VERIFY_TOKEN = "TUBO2026"

# = DB SETUP =
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
user_sessions = {}

MAIN_SHOPEE_STORE = "https://s.shopee.ph/qhsFU3xcr?smtt=0.0.9"
PRODUCT_MAP = {
    "calculator": {"name": "Casio fx-991EX Scientific Calculator", "shopee": "https://s.shopee.ph/903Zywb2BV?smtt=0.0.9", "hook": "Struggling with complex math? 📐", "benefit": "Approved for board exams. 552 functions"},
    "notebook": {"name": "National Notebook 80 Leaves", "shopee": "https://s.shopee.ph/BSBSox6US?smtt=0.0.9", "hook": "Ink keeps bleeding through? 📓", "benefit": "Thick 70gsm paper"},
    "laptop": {"name": "Lenovo Ideapad 3 Laptop", "shopee": "https://s.shopee.ph/9AN0C8jKBb?smtt=0.0.9", "hook": "Need a laptop for school & work? 💻", "benefit": "Budget-friendly. Intel i3"},
    "mouse": {"name": "Wireless Silent Mouse", "shopee": "https://s.shopee.ph/30mMqwHnbk?smtt=0.0.9", "hook": "Wrist pain from clicking? 🖱️", "benefit": "Ergonomic design. Silent click"},
    "keyboard": {"name": "RGB Mechanical Keyboard", "shopee": "https://s.shopee.ph/30mMqwHnbk?smtt=0.0.9", "hook": "Want faster typing? ⌨️", "benefit": "Blue switches. Plug and play"},
    "headset": {"name": "Gaming Headset with Noise Cancelling Mic", "shopee": "https://s.shopee.ph/30mMqwHnbk?smtt=0.0.9", "hook": "Can't hear clearly in online class? 🎧", "benefit": "Crystal clear mic"},
    "bag": {"name": "JanSport SuperBreak Backpack", "shopee": "https://s.shopee.ph/5AqrQ58Yd1?smtt=0.0.9", "hook": "Bag keeps getting wet? 🎒", "benefit": "Water resistant. 15L capacity"},
    "lamp": {"name": "LED Desk Study Lamp with USB", "shopee": "https://s.shopee.ph/2Vq6FK56cb?smtt=0.0.9", "hook": "Eyes getting tired at night? 💡", "benefit": "3 light modes. Eye protection"},
}

# = DB FUNCTIONS =
def get_user(sender_id):
    data = supabase.table('users').select("*").eq("sender_id", sender_id).execute()
    if data.data: return data.data[0]
    else:
        new_user = {"sender_id": sender_id, "name": None, "chat_count": 0, "rejected_affiliate": False, "reject_time": None, "auto_sent": False}
        supabase.table('users').insert(new_user).execute()
        return new_user

def update_user(sender_id, updates):
    supabase.table('users').update(updates).eq("sender_id", sender_id).execute()

def send_message(sender_id, text, quick_replies=None):
    text = text[:2000]
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "message": {"text": text}}
    if quick_replies: payload["message"]["quick_replies"] = quick_replies
    try: requests.post(url, json=payload, timeout=10)
    except Exception as e: print("Send error:", e)

def send_typing(sender_id, action="typing_on"):
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    requests.post(url, json={"recipient": {"id": sender_id}, "sender_action": action}, timeout=5)

def detect_language(text):
    text_lower = text.lower()
    if "unsa" in text_lower or "ka" in text_lower: return "Bisaya"
    if "ng" in text_lower or "ba" in text_lower: return "Tagalog"
    return "English"

def check_affiliate_intent(msg):
    msg = msg.lower()
    product_words = list(PRODUCT_MAP.keys())
    buy_words = ["buy", "shop", "shopee", "price", "link", "gear", "order", "store"]
    has_product = any(w in msg for w in product_words)
    has_buy_intent = any(w in msg for w in buy_words)
    return has_product or has_buy_intent

def get_affiliate_reply(msg):
    msg = msg.lower()
    for product, p in PRODUCT_MAP.items():
        if re.search(r'\b' + re.escape(product) + r'\b', msg):
            # FIX 1: SAFE BUTTONS PARA DI MA-TRIGGER SI @META AI
            qr = [{"content_type":"text", "title":"👉 View Item", "payload":f"shopee_{product}"}, {"content_type":"text", "title":"📎 See All", "payload":"shop"}]
            text = f"💡 **{p['name']}**\n\n{p['hook']}\n\n✅ **Why students like it:** {p['benefit']}\n\n*Disclosure: Affiliate link*"
            return {"text": text, "quick_replies": qr}
    if any(k in msg for k in ["buy", "shop", "shopee", "gear", "store"]):
        qr = [{"content_type":"text", "title":"🛒 Open Store", "payload":"shop"}]
        text = f"🛒 **Student Essentials Store**\n\n{MAIN_SHOPEE_STORE}\n\n*Disclosure: Affiliate link*"
        return {"text": text, "quick_replies": qr}
    return None

def handle_commands(user_message, sender_id):
    msg = user_message.lower().strip()
    user = get_user(sender_id)

    if user['reject_time']:
        if time.time() - user['reject_time'] > 86400:
            update_user(sender_id, {"rejected_affiliate": False, "auto_sent": False, "reject_time": None})

    new_count = user['chat_count'] + 1
    update_user(sender_id, {"chat_count": new_count, "auto_sent": False})

    if msg.startswith("shopee_"):
        product = msg.replace("shopee_", "")
        if product in PRODUCT_MAP:
            p = PRODUCT_MAP[product]
            return f"👉 **{p['name']}**\n{p['shopee']}\n\n*Disclosure: Affiliate link*"

    # FIX 2: HANDLE "NO" DITO PARA DI MAG ERROR
    if msg in ["no", "no need", "hindi", "ayaw", "later", "not now", "pass"]:
        update_user(sender_id, {"rejected_affiliate": True, "reject_time": time.time()})
        return "Got it! 😊 I'll stop asking about supplies for 24 hours."

    if "name is" in msg or "ako si" in msg:
        name = msg.replace("my name is", "").replace("name is", "").replace("ako si", "").strip().title()
        update_user(sender_id, {"name": name})
        return f"👋 Welcome {name}! Nice to meet you 😊"

    if msg in ["hi", "hello", "hey", "kamusta"]:
        name = user['name'] or 'Boss'
        return f"**StudyBuddy v14.22 DB** 🤖\nHi {name}!\n\nAsk me anything 😊"

    if new_count % 8 == 0 and not user['rejected_affiliate'] and not user['auto_sent']:
        update_user(sender_id, {"auto_sent": True})
        # FIX 3: PALIT BUTTON TEXT PARA SAFE
        qr = [{"content_type":"text", "title":"📎 Open Link", "payload":"shop"}, {"content_type":"text", "title":"❌ Pass", "payload":"no"}]
        name = user['name'] or 'Boss'
        # FIX 4: TINANGGAL "Shopee" SA TEXT PARA DI MA-TRIGGER
        return {"text": f"Quick tip {name} 😊\n\nNeed school supplies? I have a curated list with student vouchers.\n\nWant it?", "quick_replies": qr}

    if msg == "shop":
        qr = [{"content_type":"text", "title":"🛒 Open Store", "payload":"shop"}]
        return {"text": f"🛒 **Here's my student essentials store:**\n\n{MAIN_SHOPEE_STORE}\n\n*Disclosure: Affiliate link*", "quick_replies": qr}

    if not user['rejected_affiliate']:
        if check_affiliate_intent(msg):
            affiliate_reply = get_affiliate_reply(msg)
            if affiliate_reply: return affiliate_reply

    if any(w in msg for w in ["pagod", "stress", "hirap", "sad"]):
        return random.choice(["Laban lang! Take a 5 min break ☕ You got this!", "Kaya mo yan! One step at a time 😊 I'm here for you"])
    return None

# FIX 5: MAY MEMORY NA + ERROR LOGS
def ask_groq(user_message, sender_id):
    user = get_user(sender_id)
    name = user['name'] or "Boss"
    if any(word in user_message.lower() for word in ["lyrics", "poem", "song"]):
        return "I can't share that due to copyright 😅 But you can ask me anything else!"
    language = detect_language(user_message)
    try:
        system_prompt = f"You are StudyBuddy PH v14.22. A friendly and helpful AI Assistant from the Philippines. Reply in {language}. Keep answers under 8 sentences. IMPORTANT: The user's name is {name}. Use their name naturally."
        user_prompt = f"User Question: {user_message}"
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        data = {"model": "llama-3.3-70b-versatile", "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}], "temperature": 0.7, "max_tokens": 300}
        r = requests.post(url, headers=headers, json=data, timeout=30)
        if r.status_code!= 200:
            print("GROQ STATUS:", r.status_code, r.text)
            return f"The AI is resting 😅 Error code: {r.status_code}. Please try again {name}."
        return r.json()['choices'][0]['message']['content']
    except Exception as e:
        print("GROQ EXCEPTION:", e)
        return f"The AI had an error 😅 But I'm still here {name}. Try again."

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == VERIFY_TOKEN: return request.args.get("hub.challenge"), 200
        return "Error", 403
    if request.method == 'POST':
        data = request.get_json()
        if data.get('object') == 'page':
            for entry in data.get('entry', []):
                for event in entry.get('messaging', []):
                    sender_id = event['sender']['id']
                    if sender_id in user_sessions and time.time() - user_sessions[sender_id] < 1.2: continue
                    user_sessions[sender_id] = time.time()
                    send_typing(sender_id)
                    time.sleep(0.3)
                    try:
                        if 'message' in event and 'attachments' in event['message']:
                            send_message(sender_id, "I can only reply to text messages for now 😅")
                            continue
                        if 'message' in event and 'text' in event['message']:
                            user_message = event['message']['text']
                            cmd = handle_commands(user_message, sender_id)
                            if isinstance(cmd, dict): send_message(sender_id, cmd["text"], cmd.get("quick_replies"))
                            elif cmd: send_message(sender_id, cmd)
                            else:
                                ai = ask_groq(user_message, sender_id)
                                send_message(sender_id, ai)
                    except Exception as e:
                        print("ERROR:", e)
                        send_message(sender_id, "Error 😅")
                    finally: send_typing(sender_id, "typing_off")
        return "ok", 200

@app.route('/', methods=['GET'])
def home(): return "StudyBuddy v14.22 DB", 200
