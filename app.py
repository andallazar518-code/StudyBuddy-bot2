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

user_sessions = {} # temp lang to, ok lang burahin

MAIN_SHOPEE_STORE = "https://s.shopee.ph/qhsFU3xcr?smtt=0.0.9"
PRODUCT_MAP = {
    "calculator": {"name": "Casio fx-991EX Scientific Calculator", "shopee": "https://s.shopee.ph/903Zywb2BV?smtt=0.0.9", "hook": "Struggling with complex math? 📐", "benefit": "Approved for board exams. 552 functions"},
    "notebook": {"name": "National Notebook 80 Leaves", "shopee": "https://s.shopee.ph/BSBSox6US?smtt=0.0.9", "hook": "Ink keeps bleeding through? 📓", "benefit": "Thick 70gsm paper"},
}

# = DB FUNCTIONS = BAGO TO
def get_user(sender_id):
    data = supabase.table('users').select("*").eq("sender_id", sender_id).execute()
    if data.data:
        return data.data[0]
    else:
        # Create new user
        new_user = {
            "sender_id": sender_id,
            "name": None,
            "chat_count": 0,
            "rejected_affiliate": False,
            "reject_time": None,
            "auto_sent": False
        }
        supabase.table('users').insert(new_user).execute()
        return new_user

def update_user(sender_id, updates):
    supabase.table('users').update(updates).eq("sender_id", sender_id).execute()

def send_message(sender_id, text, quick_replies=None):
    text = text[:2000]
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "message": {"text": text}}
    if quick_replies: payload["message"]["quick_replies"] = quick_replies
    requests.post(url, json=payload, timeout=10)

def send_typing(sender_id, action="typing_on"):
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    requests.post(url, json={"recipient": {"id": sender_id}, "sender_action": action}, timeout=5)

def detect_language(text):
    text_lower = text.lower()
    if "unsa" in text_lower: return "Bisaya"
    if "ng" in text_lower: return "Tagalog"
    return "English"

def check_affiliate_intent(msg):
    msg = msg.lower()
    product_words = list(PRODUCT_MAP.keys())
    buy_words = ["buy", "shop", "shopee", "price", "link"]
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
            text = f"💡 **{p['name']}**\n\n{p['hook']}\n\n✅ **Why students like it:** {p['benefit']}\n\n*Disclosure: Affiliate link*"
            return {"text": text, "quick_replies": qr}
    if any(k in msg for k in ["buy", "shop", "shopee"]):
        qr = [{"content_type":"text", "title":"🛒 Open Store", "payload":"shop"}]
        text = f"🛒 **Student Essentials Store**\n\n{MAIN_SHOPEE_STORE}\n\n*Disclosure: Affiliate link*"
        return {"text": text, "quick_replies": qr}
    return None

def handle_commands(user_message, sender_id):
    msg = user_message.lower().strip()
    user = get_user(sender_id) # KUHA SA DB

    # AUTO RESET AFTER 24 HOURS
    if user['reject_time']:
        if time.time() - user['reject_time'] > 86400:
            update_user(sender_id, {"rejected_affiliate": False, "auto_sent": False, "reject_time": None})

    # CHAT COUNT + 1
    new_count = user['chat_count'] + 1
    update_user(sender_id, {"chat_count": new_count, "auto_sent": False})

    if msg.startswith("shopee_"):
        product = msg.replace("shopee_", "")
        if product in PRODUCT_MAP:
            p = PRODUCT_MAP[product]
            return f"👉 **{p['name']}**\n{p['shopee']}\n\n*Disclosure: Affiliate link*"

    if any(w in msg for w in ["no", "no need", "hindi"]):
        update_user(sender_id, {"rejected_affiliate": True, "reject_time": time.time()})
        return "Got it! 😊 No worries. I'll ask again tomorrow. Support bot: https://bit.ly/ryzoxau"

    if "name is" in msg or "ako si" in msg:
        name = msg.replace("my name is", "").replace("name is", "").replace("ako si", "").strip().title()
        update_user(sender_id, {"name": name})
        return f"👋 Welcome {name}! Nice to meet you 😊"

    if msg in ["hi", "hello", "hey"]:
        name = user['name'] or 'Boss'
        return f"**StudyBuddy v14.16 DB** 🤖\nHi {name}!\n\nAsk me anything 😊"

    # = BAGONG RULE: EVERY 8 MESSAGES LANG = NAKA DB NA
    if new_count % 8 == 0 and not user['rejected_affiliate'] and not user['auto_sent']:
        update_user(sender_id, {"auto_sent": True})
        qr = [{"content_type":"text", "title":"🛒 View Deals", "payload":"shop"}, {"content_type":"text", "title":"No thanks", "payload":"no"}]
        name = user['name'] or 'Boss'
        return {"text": f"Quick tip {name} 😊\n\nNeed school supplies? I have a curated Shopee list with student vouchers.\n\nWant to see?", "quick_replies": qr}

    if msg == "shop":
        qr = [{"content_type":"text", "title":"🛒 Open Store", "payload":"shop"}]
        return {"text": f"🛒 **Here's my student essentials store:**\n\n{MAIN_SHOPEE_STORE}\n\n*Disclosure: Affiliate link*", "quick_replies": qr}

    if not user['rejected_affiliate']:
        if check_affiliate_intent(msg):
            affiliate_reply = get_affiliate_reply(msg)
            if affiliate_reply: return affiliate_reply

    return None

def ask_groq(user_message):
    language = detect_language(user_message)
    try:
        prompt = f"You are StudyBuddy PH v14.16. Reply in {language}. Max 10 sentences.\nUser: {user_message}"
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        data = {"model": "llama-3.1-70b-versatile", "messages": [{"role": "user", "content": prompt}]}
        r = requests.post(url, headers=headers, json=data, timeout=20)
        return r.json()['choices'][0]['message']['content']
    except:
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
                    send_typing(sender_id)
                    time.sleep(0.3)
                    try:
                        if 'message' in event and 'text' in event['message']:
                            user_message = event['message']['text']
                            cmd = handle_commands(user_message, sender_id)
                            if isinstance(cmd, dict): send_message(sender_id, cmd["text"], cmd.get("quick_replies"))
                            elif cmd: send_message(sender_id, cmd)
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
    return "StudyBuddy v14.16 DB", 200
