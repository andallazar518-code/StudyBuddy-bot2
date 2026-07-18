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
user_chat_count = {}

# = AFFILIATE - MAS APPEALING PERO SAFE =
# IMPORTANT: Palitan mo ng sarili mong Shopee Affiliate Link
MAIN_SHOPEE_STORE = "https://s.shopee.ph/qhsFU3xcr?smtt=0.0.9"
PRODUCT_MAP = {
    "calculator": {"name": "Casio fx-991EX Scientific Calculator", "shopee": "https://s.shopee.ph/903Zywb2BV?smtt=0.0.9", "hook": "🔥 Student Best Seller. Approved for board exams 📐"},
    "notebook": {"name": "National Notebook 80 Leaves", "shopee": "https://s.shopee.ph/BSBSox6US?smtt=0.0.9", "hook": "📓 Thick paper. No ink bleed - perfect for notes"},
    "laptop": {"name": "Lenovo Ideapad 3 Laptop", "shopee": "https://s.shopee.ph/9AN0C8jKBb?smtt=0.0.9", "hook": "💻 Budget-friendly for school & work. Free shipping voucher"},
    "mouse": {"name": "Wireless Silent Mouse", "shopee": "https://s.shopee.ph/30mMqwHnbk?smtt=0.0.9", "hook": "🖱️ Ergonomic + Long battery life. 1 Year warranty"},
    "keyboard": {"name": "RGB Mechanical Keyboard", "shopee": "https://s.shopee.ph/30mMqwHnbk?smtt=0.0.9", "hook": "⌨️ Blue switches. Great for typing & gaming"},
    "headset": {"name": "Gaming Headset with Noise Cancelling Mic", "shopee": "https://s.shopee.ph/30mMqwHnbk?smtt=0.0.9", "hook": "🎧 Clear audio for online class & meetings"},
    "bag": {"name": "JanSport SuperBreak Backpack", "shopee": "https://s.shopee.ph/5AqrQ58Yd1?smtt=0.0.9", "hook": "🎒 Water resistant. Lifetime warranty included"},
    "lamp": {"name": "LED Desk Study Lamp with USB", "shopee": "https://s.shopee.ph/2Vq6FK56cb?smtt=0.0.9", "hook": "💡 3 Light modes. Protects eyes while studying"},
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

def cleanup_memory():
    if len(user_memory) > 50:
        oldest = list(user_memory.keys())[0]
        del user_memory[oldest]

def detect_language(text):
    text_lower = text.lower()
    bisaya = ["unsa", "ngano", "asa"]
    tagalog = ["ng", "ang", "paano", "ano"]
    if any(w in text_lower.split() for w in bisaya):
        return "Bisaya"
    if any(w in text_lower.split() for w in tagalog):
        return "Tagalog"
    return "English"

def check_affiliate_intent(msg):
    msg = msg.lower()
    # SAFE TRIGGERS - HINDI SPAMMY
    buy_words = ["buy", "shop", "shopee", "price", "link", "where to buy", "gear", "order", "store", "need", "gusto", "hanap"]
    product_words = list(PRODUCT_MAP.keys())
    study_words = ["school", "study", "exam", "review", "assignment", "supplies"]

    has_product = any(w in msg for w in product_words)
    has_buy_intent = any(w in msg for w in buy_words)
    has_study = any(w in msg for w in study_words)

    return has_product or has_buy_intent or has_study

def get_affiliate_reply(msg):
    msg = msg.lower()
    # PRODUCT SPECIFIC - MAS APPEALING COPY
    for product, p in PRODUCT_MAP.items():
        if re.search(r'\b' + re.escape(product) + r'\b', msg):
            return f"💡 **I recommend: {p['name']}**\n\n{p['hook']}\n\n👉 **Check price & reviews:**\n{p['shopee']}\n\n*Disclosure: This is an affiliate link. It helps support StudyBuddy at no extra cost to you.*"

    # GENERAL STORE - SOFT SELL
    if any(k in msg for k in ["buy", "shop", "shopee", "gear", "store", "school", "study", "need", "supplies"]):
        return f"🛒 **Need school supplies?**\n\nI put together my list of trusted student essentials here:\n\n{MAIN_SHOPEE_STORE}\n\n👆 Check for vouchers & free shipping\n*Disclosure: Affiliate link to support this bot*"

    return None

def handle_commands(user_message, sender_id):
    cleanup_memory()
    msg = user_message.lower().strip()

    # TRACK CHAT COUNT
    if sender_id not in user_chat_count:
        user_chat_count[sender_id] = 0
    user_chat_count[sender_id] += 1

    # 1. NAME
    if "name is" in msg or "ako si" in msg:
        name = msg.replace("my name is", "").replace("name is", "").replace("ako si", "").strip()
        if sender_id not in user_memory: user_memory[sender_id] = {}
        user_memory[sender_id]['name'] = name.title()
        return f"👋 Welcome {name.title()}! Nice to meet you 😊"

    # 2. GREETING
    if msg in ["hi", "hello", "hey", "kamusta"]:
        name = user_memory.get(sender_id, {}).get('name', 'Boss')
        return f"**StudyBuddy v14.7** 🤖\nHi {name}!\n\nAsk me anything. I can also help you find school deals 😊"

    # 3. SOFT AUTO-SUGGEST AFTER 3 MESSAGES - SAFE VERSION
    if user_chat_count[sender_id] == 3:
        return f"By the way {user_memory.get(sender_id, {}).get('name', 'Boss')} 😊\n\nIf you ever need school supplies or gadgets, just type `shop` and I'll send you my curated Shopee list with vouchers.\n\nNo pressure though! I'm also here to help with studies 💪"

    # 4. MANUAL SHOP TRIGGER
    if msg == "shop":
        return f"🛒 **Here's my student essentials store:**\n\n{MAIN_SHOPEE_STORE}\n\nTip: Check vouchers daily for extra discounts!\n\n*Disclosure: Affiliate link*"

    # 5. AFFILIATE
    if check_affiliate_intent(msg):
        affiliate_reply = get_affiliate_reply(msg)
        if affiliate_reply:
            return affiliate_reply

    # 6. MOOD
    if any(w in msg for w in ["pagod", "stress", "hirap", "sad"]):
        return random.choice([
            "Laban lang! Take a 5 min break ☕ You got this!",
            "Kaya mo yan! One step at a time 😊 I'm here for you"
        ])

    return None

def ask_groq(user_message):
    if any(word in user_message.lower() for word in ["lyrics", "poem"]):
        return "Can't share that due to copyright 😅 Pero ask me anything else!"

    language = detect_language(user_message)
    models = ["llama-3.1-70b-versatile", "llama-3.1-8b-instant"]
    for model in models:
        try:
            prompt = f"""You are StudyBuddy PH v14.7. A friendly and helpful AI Assistant.
Reply in {language}. Be helpful, kind, and conversational.
If the user asks about school, studying, or products, you can casually mention that deals are often available on Shopee.
Answer EVERY question.
User: {user_message}"""
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
            data = {"model": model, "messages": [{"role": "user", "content": prompt}]}
            r = requests.post(url, headers=headers, json=data, timeout=20)
            if r.status_code == 200:
                return r.json()['choices'][0]['message']['content']
        except:
            continue
    return "AI busy 😅 Try again"

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
    return "StudyBuddy v14.7 FULL", 200
