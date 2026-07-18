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
user_rejected_affiliate = {}
user_reject_time = {}
user_auto_sent = {}

# = AFFILIATE - SHOPEE ONLY =
MAIN_SHOPEE_STORE = "https://s.shopee.ph/qhsFU3xcr?smtt=0.0.9"
PRODUCT_MAP = {
    "calculator": {"name": "Casio fx-991EX Scientific Calculator", "shopee": "https://s.shopee.ph/903Zywb2BV?smtt=0.0.9", "hook": "Struggling with complex math? 📐", "benefit": "Approved for board exams. 552 functions. Student favorite"},
    "notebook": {"name": "National Notebook 80 Leaves", "shopee": "https://s.shopee.ph/BSBSox6US?smtt=0.0.9", "hook": "Ink keeps bleeding through? 📓", "benefit": "Thick 70gsm paper. Perfect for notes and reviewers"},
    "laptop": {"name": "Lenovo Ideapad 3 Laptop", "shopee": "https://s.shopee.ph/9AN0C8jKBb?smtt=0.0.9", "hook": "Need a laptop for school & work? 💻", "benefit": "Budget-friendly. Intel i3. Free shipping voucher available"},
    "mouse": {"name": "Wireless Silent Mouse", "shopee": "https://s.shopee.ph/30mMqwHnbk?smtt=0.0.9", "hook": "Wrist pain from clicking? 🖱️", "benefit": "Ergonomic design. Silent click. Up to 12 months battery"},
    "keyboard": {"name": "RGB Mechanical Keyboard", "shopee": "https://s.shopee.ph/30mMqwHnbk?smtt=0.0.9", "hook": "Want faster typing for assignments? ⌨️", "benefit": "Blue switches. Great feedback. Plug and play"},
    "headset": {"name": "Gaming Headset with Noise Cancelling Mic", "shopee": "https://s.shopee.ph/30mMqwHnbk?smtt=0.0.9", "hook": "Can't hear clearly in online class? 🎧", "benefit": "Crystal clear mic. Comfortable for long hours"},
    "bag": {"name": "JanSport SuperBreak Backpack", "shopee": "https://s.shopee.ph/5AqrQ58Yd1?smtt=0.0.9", "hook": "Bag keeps getting wet? 🎒", "benefit": "Water resistant. 15L capacity. Lifetime warranty"},
    "lamp": {"name": "LED Desk Study Lamp with USB", "shopee": "https://s.shopee.ph/2Vq6FK56cb?smtt=0.0.9", "hook": "Eyes getting tired at night? 💡", "benefit": "3 light modes. Eye protection. USB powered"},
}

def send_message(sender_id, text, quick_replies=None):
    text = text[:2000]
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "message": {"text": text}}
    if quick_replies:
        payload["message"]["quick_replies"] = quick_replies
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
    product_words = list(PRODUCT_MAP.keys())
    buy_words = ["buy", "shop", "shopee", "price", "link", "where to buy", "gear", "order", "store"]
    has_product = any(w in msg for w in product_words)
    has_buy_intent = any(w in msg for w in buy_words)
    return has_product or has_buy_intent

def get_affiliate_reply(msg):
    msg = msg.lower()
    for product, p in PRODUCT_MAP.items():
        if re.search(r'\b' + re.escape(product) + r'\b', msg):
            qr = [
                {"content_type":"text", "title":"👉 View on Shopee", "payload":f"shopee_{product}"},
                {"content_type":"text", "title":"🛒 See All Deals", "payload":"shop"}
            ]
            text = f"💡 **{p['name']}**\n\n{p['hook']}\n\n✅ **Why students like it:** {p['benefit']}\n\n*Disclosure: Affiliate link. Helps support StudyBuddy*"
            return {"text": text, "quick_replies": qr}
    if any(k in msg for k in ["buy", "shop", "shopee", "gear", "store"]):
        qr = [{"content_type":"text", "title":"🛒 Open Store", "payload":"shop"}]
        text = f"🛒 **Student Essentials Store**\n\nI curated the best school supplies with vouchers here:\n\n{MAIN_SHOPEE_STORE}\n\nTip: Check vouchers daily to save more!\n\n*Disclosure: Affiliate link*"
        return {"text": text, "quick_replies": qr}
    return None

def handle_commands(user_message, sender_id):
    cleanup_memory()
    msg = user_message.lower().strip()

    # = FIX 1: BETTER BUTTON DETECTION =
    if "view deals" in msg or "open store" in msg or "show deals" in msg or "see all deals" in msg:
        msg = "shop"
    if "no thanks" in msg or "no" == msg:
        msg = "no"

    # AUTO RESET AFTER 24 HOURS
    if sender_id in user_reject_time:
        if time.time() - user_reject_time[sender_id] > 86400:
            user_rejected_affiliate[sender_id] = False
            user_auto_sent[sender_id] = False
            del user_reject_time[sender_id]

    if sender_id not in user_chat_count:
        user_chat_count[sender_id] = 0
    user_chat_count[sender_id] += 1
    user_auto_sent[sender_id] = False # FIX 2: RESET AUTO SENT EVERY NEW MESSAGE

    if msg.startswith("shopee_"):
        product = msg.replace("shopee_", "")
        if product in PRODUCT_MAP:
            p = PRODUCT_MAP[product]
            return f"👉 **{p['name']}**\n{p['shopee']}\n\n*Disclosure: Affiliate link*"

    if any(w in msg for w in ["no", "no need", "don't need", "hindi", "ayaw"]):
        user_rejected_affiliate[sender_id] = True
        user_reject_time[sender_id] = time.time()
        return "Got it! 😊 No worries. I'll ask again tomorrow if you need help with school supplies."

    if "name is" in msg or "ako si" in msg:
        name = msg.replace("my name is", "").replace("name is", "").replace("ako si", "").strip()
        if sender_id not in user_memory: user_memory[sender_id] = {}
        user_memory[sender_id]['name'] = name.title()
        return f"👋 Welcome {name.title()}! Nice to meet you 😊"

    if msg in ["hi", "hello", "hey", "kamusta"]:
        name = user_memory.get(sender_id, {}).get('name', 'Boss')
        return f"**StudyBuddy v14.14** 🤖\nHi {name}!\n\nAsk me anything 😊"

    # AUTO SEND EVERY 5 MESSAGES
    if user_chat_count[sender_id] % 5 == 0 and not user_rejected_affiliate.get(sender_id, False) and not user_auto_sent.get(sender_id, False):
        user_auto_sent[sender_id] = True
        qr = [{"content_type":"text", "title":"🛒 View Deals", "payload":"shop"}, {"content_type":"text", "title":"No thanks", "payload":"no"}]
        return {"text": f"Quick tip {user_memory.get(sender_id, {}).get('name', 'Boss')} 😊\n\nIf you need school supplies, I have a curated Shopee list with student vouchers.\n\nWant to see?", "quick_replies": qr}

    if user_chat_count[sender_id] == 3 and not user_rejected_affiliate.get(sender_id, False):
        qr = [{"content_type":"text", "title":"🛒 Show Deals", "payload":"shop"}]
        return {"text": f"By the way {user_memory.get(sender_id, {}).get('name', 'Boss')} 😊\n\nNeed school supplies? I have a curated list with vouchers.\n\nNo pressure! Just tap below if you want to see.", "quick_replies": qr}

    if msg == "shop":
        qr = [{"content_type":"text", "title":"🛒 Open Store", "payload":"shop"}]
        return {"text": f"🛒 **Here's my student essentials store:**\n\n{MAIN_SHOPEE_STORE}\n\n*Disclosure: Affiliate link*", "quick_replies": qr}

    if not user_rejected_affiliate.get(sender_id, False):
        if check_affiliate_intent(msg):
            affiliate_reply = get_affiliate_reply(msg)
            if affiliate_reply:
                return affiliate_reply

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
            prompt = f"""You are StudyBuddy PH v14.14. A friendly and helpful AI Assistant.
Reply in {language}. Be helpful, kind, and conversational. Max 6 sentences.
Only mention Shopee if the user specifically asks about buying, price, or school products.
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
                            elif isinstance(cmd, dict):
                                send_message(sender_id, cmd["text"], cmd.get("quick_replies"))
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
    return "StudyBuddy v14.14 FULL", 200

@app.route('/ping', methods=['GET'])
def ping():
    return "Bot is awake", 200
