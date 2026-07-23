from flask import Flask, request, abort
import requests, os, time, random, re, json, hashlib, hmac, threading
from supabase import create_client

app = Flask(__name__)

# Startup env check so app fails fast if keys are missing
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if not PAGE_ACCESS_TOKEN or not GROQ_API_KEY:
    raise ValueError("Missing PAGE_ACCESS_TOKEN or GROQ_API_KEY")

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "TUBO2026")
APP_SECRET = os.environ.get("FB_APP_SECRET")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

user_sessions = {}
SESSION_COOLDOWN = 1.2

AFFILIATE_ID = "studybuddy"
MAIN_SHOPEE_STORE = "https://s.shopee.ph/qhsFU3xcr?smtt=0.0.9"

# Cleaned product map
PRODUCT_MAP = {
    "calculator": {
        "name": "Casio fx-991EX Scientific Calculator",
        "shopee": "https://s.shopee.ph/903Zywb2BV?smtt=0.0.9",
        "hook": "Struggling with complex math? 📐",
        "benefit": "Approved for board exams. 552 functions"
    },
    "notebook": {
        "name": "National Notebook 80 Leaves",
        "shopee": "https://s.shopee.ph/BSBSox6US?smtt=0.0.9",
        "hook": "Ink keeps bleeding through? 📓",
        "benefit": "Thick 70gsm paper"
    },
    "laptop": {
        "name": "Lenovo Ideapad 3 Laptop",
        "shopee": "https://s.shopee.ph/9AN0C8jKBb?smtt=0.0.9",
        "hook": "Need a laptop for school & work? 💻",
        "benefit": "Budget-friendly. Intel i3"
    },
    "mouse": {
        "name": "Wireless Silent Mouse",
        "shopee": "https://s.shopee.ph/7pKqL9xAbc?smtt=0.0.9",
        "hook": "Wrist pain from clicking? 🖱️",
        "benefit": "Ergonomic design. Silent click"
    },
    "keyboard": {
        "name": "RGB Mechanical Keyboard",
        "shopee": "https://s.shopee.ph/8rLmN2pQrs?smtt=0.0.9",
        "hook": "Want faster typing? ⌨️",
        "benefit": "Blue switches. Plug and play"
    },
    "headset": {
        "name": "Gaming Headset with Noise Cancelling Mic",
        "shopee": "https://s.shopee.ph/4wZxY6vTuv?smtt=0.0.9",
        "hook": "Can't hear clearly in online class? 🎧",
        "benefit": "Crystal clear mic"
    },
    "bag": {
        "name": "JanSport SuperBreak Backpack",
        "shopee": "https://s.shopee.ph/5AqrQ58Yd1?smtt=0.0.9",
        "hook": "Bag keeps getting wet? 🎒",
        "benefit": "Water resistant. 15L capacity"
    },
    "lamp": {
        "name": "LED Desk Study Lamp with USB",
        "shopee": "https://s.shopee.ph/2Vq6FK56cb?smtt=0.0.9",
        "hook": "Eyes getting tired at night? 💡",
        "benefit": "3 light modes. Eye protection"
    },
}

def get_tracked_link(base_url, sender_id, product="store"):
    """Add tracking payload to Shopee link safely handling existing query parameters"""
    tracker = f"aff_id={AFFILIATE_ID}_{sender_id}_{product}"
    return f"{base_url}&{tracker}" if "?" in base_url else f"{base_url}?{tracker}"

def verify_signature(req):
    if not APP_SECRET:
        return True
    signature = req.headers.get("X-Hub-Signature-256", "")
    if not signature:
        return False
    hash_val = hmac.new(APP_SECRET.encode('utf-8'), req.data, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={hash_val}", signature)

def get_fb_name(sender_id):
    if not PAGE_ACCESS_TOKEN:
        return None
    try:
        url = f"https://graph.facebook.com/v19.0/{sender_id}?fields=first_name&access_token={PAGE_ACCESS_TOKEN}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200:
            return r.json().get("first_name")
    except Exception as e:
        print(f"FB NAME ERROR for {sender_id}:", e)
    return None

def _load_history(raw):
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return []

def _dump_history(hist):
    trimmed = []
    for m in hist[-10:]:
        m_copy = {"role": m.get("role", "user"), "content": str(m.get("content", ""))[:500]}
        trimmed.append(m_copy)
    return json.dumps(trimmed)

def get_user(sender_id):
    default = {
        "sender_id": sender_id,
        "name": None,
        "chat_count": 0,
        "rejected_affiliate": False,
        "reject_time": None,
        "auto_sent": False,
        "last_promo_time": None,
        "waiting_for_name": False,
        "conversation_history": [],
        "last_interest": None,
        "last_bot_action": None
    }
    if not supabase:
        return default
    try:
        data = supabase.table('users').select("*").eq("sender_id", sender_id).execute()
        if data and getattr(data, 'data', None):
            user = data.data[0]
            user['conversation_history'] = _load_history(user.get('conversation_history'))
            if not user.get('name') or user.get('name') == 'Boss':
                fb_name = get_fb_name(sender_id)
                if fb_name:
                    update_user(sender_id, {"name": fb_name})
                    user['name'] = fb_name
            return user
        else:
            fb_name = get_fb_name(sender_id)
            new_user = default.copy()
            new_user.update({"name": fb_name})
            supabase.table('users').upsert({**new_user, "conversation_history": _dump_history([])}, on_conflict="sender_id").execute()
            return new_user
    except Exception as e:
        print(f"DB GET ERROR for {sender_id}:", e)
        return default

def update_user(sender_id, updates):
    if not supabase:
        return
    if "conversation_history" in updates:
        updates["conversation_history"] = _dump_history(updates["conversation_history"])
    try:
        supabase.table('users').update(updates).eq("sender_id", sender_id).execute()
    except Exception as e:
        print(f"DB UPDATE ERROR for {sender_id}:", e)

def send_message(sender_id, text, quick_replies=None):
    if not PAGE_ACCESS_TOKEN:
        return
    text = str(text)[:2000]
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "message": {"text": text}}
    if quick_replies:
        payload["message"]["quick_replies"] = quick_replies
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Send error for {sender_id}:", e)

def send_button_template(sender_id, text, buttons):
    if not PAGE_ACCESS_TOKEN:
        return
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": sender_id},
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "button",
                    "text": text[:640],
                    "buttons": buttons
                }
            }
        }
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Button send error:", e)

def send_product_carousel(sender_id):
    if not PAGE_ACCESS_TOKEN:
        return
    elements = []
    for product, p in list(PRODUCT_MAP.items())[:4]:
        tracked_link = get_tracked_link(p['shopee'], sender_id, product)
        elements.append({
            "title": p['name'][:80],
            "subtitle": p['hook'][:80],
            "buttons": [
                {"type": "web_url", "url": tracked_link, "title": "👉 Buy Now"},
                {"type": "postback", "title": "🔍 Details", "payload": f"details_{product}"[:1000]}
            ]
        })
    if not elements:
        send_message(sender_id, "No products available right now!")
        return

    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": sender_id},
        "message": {
            "attachment": {
                "type": "template",
                "payload": {
                    "template_type": "generic",
                    "elements": elements
                }
            }
        }
    }
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print(f"Carousel send error:", e)

def send_typing(sender_id, action="typing_on"):
    if not PAGE_ACCESS_TOKEN:
        return
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    try:
        requests.post(url, json={"recipient": {"id": sender_id}, "sender_action": action}, timeout=5)
    except Exception:
        pass

def should_save_to_memory(msg):
    skip = ["hi", "hello", "hey", "help", "menu", "shop", "yes", "no", "y", "n", "reset name", "commands"]
    return msg.lower().strip() not in skip

def check_affiliate_intent(msg):
    msg = msg.lower()
    product_words = list(PRODUCT_MAP.keys())
    buy_words = ["buy", "shop", "shopee", "price", "link", "gear", "order", "store"]
    if msg in ["yes", "y", "no", "n"]:
        return False
    return any(w in msg for w in product_words) or any(w in msg for w in buy_words)

def get_affiliate_reply(sender_id, msg):
    msg = msg.lower()
    for product, p in PRODUCT_MAP.items():
        if re.search(r'\b' + re.escape(product) + r'\b', msg):
            tracked_link = get_tracked_link(p['shopee'], sender_id, product)
            text = f"💡 {p['name']}\n\n{p['hook']}\n\n✅ Why students like it: {p['benefit']}\n\n*Disclosure: Affiliate link*"
            buttons = [
                {"type": "web_url", "url": tracked_link, "title": "👉 View on Shopee"},
                {"type": "postback", "title": "🔍 Price Tips", "payload": f"compare_{product}"[:1000]},
                {"type": "postback", "title": "📎 See All", "payload": "shop"}
            ]
            send_button_template(sender_id, text, buttons)
            return True

    if any(k in msg for k in ["buy", "shop", "shopee", "gear", "store"]):
        tracked_link = get_tracked_link(MAIN_SHOPEE_STORE, sender_id, "store")
        text = f"🛒 Student Essentials Store\n\nBrowse all student vouchers here.\n\n*Disclosure: Affiliate link*"
        buttons = [{"type": "web_url", "url": tracked_link, "title": "🛒 Open Store"}]
        send_button_template(sender_id, text, buttons)
        return True

    return False

def call_groq_api(messages):
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 500
    }
    try:
        res = requests.post("https://api.groq.com/openai/v1/chat/completions", json=payload, headers=headers, timeout=12)
        if res.status_code == 200:
            return res.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print("GROQ API ERROR:", e)
    return "I'm having a little trouble thinking right now. Please try again in a moment! 😅"

def handle_commands(user_message, sender_id):
    try:
        msg = user_message.lower().strip()
        raw_msg = user_message
        user = get_user(sender_id)

        now = time.time()
        if user.get('reject_time') and now - user['reject_time'] > 86400:
            update_user(sender_id, {"rejected_affiliate": False, "auto_sent": False, "reject_time": None, "last_promo_time": None})
            user = get_user(sender_id)

        if user.get('last_promo_time') and now - user['last_promo_time'] > 86400:
            update_user(sender_id, {"auto_sent": False})
            user = get_user(sender_id)

        skip_count = ["hi","hello","hey","help","menu","shop","yes","no","y","n","reset name","commands","clear memory"]
        new_count = user.get('chat_count', 0) + 1 if msg not in skip_count else user.get('chat_count', 0)
        update_user(sender_id, {"chat_count": new_count})

        if "@meta ai" in raw_msg.lower() or "open link" in msg:
            if user.get('rejected_affiliate'):
                return "Got it! 😊 I'll stop asking about supplies for 24 hours."
            tracked_link = get_tracked_link(MAIN_SHOPEE_STORE, sender_id, "openlink")
            send_button_template(sender_id, "🛒 Here's my student essentials store:\n\n*Disclosure: Affiliate link*", [{"type": "web_url", "url": tracked_link, "title": "🛒 Open Store"}])
            return None

        if msg in ["clear memory", "reset memory"]:
            update_user(sender_id, {"conversation_history": [], "last_interest": None})
            return "🧠 Memory cleared! Fresh start 😊"

        if user.get('waiting_for_name') and 1 <= len(msg.split()) <= 3 and msg not in skip_count:
            name = user_message.strip().title()
            update_user(sender_id, {"name": name, "waiting_for_name": False})
            return f"👋 Nice to meet you {name}! Got it saved 😊"

        if msg.startswith("shopee_"):
            product = msg.replace("shopee_", "")
            if product in PRODUCT_MAP:
                p = PRODUCT_MAP[product]
                tracked_link = get_tracked_link(p['shopee'], sender_id, product)
                send_button_template(sender_id, f"👉 {p['name']}\n\n*Disclosure: Affiliate link*", [{"type": "web_url", "url": tracked_link, "title": "👉 View on Shopee"}])
                return None

        if msg in ["shop", "store", "essentials"]:
            send_product_carousel(sender_id)
            return None

        if msg in ["hi", "hello", "hey"]:
            user_name = user.get('name')
            greeting = f"Hello {user_name}! 👋" if user_name else "Hello! 👋"
            return f"{greeting} I'm StudyBuddy AI! How can I help you with your studies today?"

        if get_affiliate_reply(sender_id, msg):
            return None

        # Groq Fallback Chat Engine
        history = user.get('conversation_history', [])
        system_prompt = {
            "role": "system",
            "content": f"You are StudyBuddy AI, a friendly and helpful Philippine student assistant. Speak in warm, conversational English with occasional light Taglish. User name: {user.get('name') or 'Friend'}."
        }

        messages = [system_prompt] + history + [{"role": "user", "content": user_message}]
        reply = call_groq_api(messages)

        if should_save_to_memory(user_message):
            updated_hist = history + [{"role": "user", "content": user_message}, {"role": "assistant", "content": reply}]
            update_user(sender_id, {"conversation_history": updated_hist[-10:]})

        return reply

    except Exception as e:
        print("Error in handle_commands:", e)
        return "Oops, something went wrong processing that request!"

@app.route('/', methods=['GET'])
def home():
    return "StudyBuddy Bot is live and running!", 200

@app.route('/webhook', methods=['GET'])
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return challenge, 200
    return "Verification failed", 403

@app.route('/webhook', methods=['POST'])
def webhook():
    if not verify_signature(request):
        abort(403)

    data = request.get_json()

    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event["sender"]["id"]

                # Trigger typing indicator bubble
                send_typing(sender_id, "typing_on")

                # 1. Handle regular text messages
                if "message" in messaging_event and "text" in messaging_event["message"]:
                    user_message = messaging_event["message"]["text"]

                    if user_sessions.get(sender_id):
                        continue
                    user_sessions[sender_id] = True

                    try:
                        reply = handle_commands(user_message, sender_id)
                        if reply:
                            send_message(sender_id, reply)
                    finally:
                        user_sessions.pop(sender_id, None)

                # 2. Handle button postbacks (Price Tips, See All, Details, etc.)
                elif "postback" in messaging_event:
                    payload = messaging_event["postback"].get("payload", "")

                    if payload == "shop":
                        send_product_carousel(sender_id)

                    elif payload.startswith("compare_"):
                        product_key = payload.replace("compare_", "")
                        if product_key in PRODUCT_MAP:
                            prod = PRODUCT_MAP[product_key]
                            tip_msg = (
                                f"💡 *Price Tip for {prod['name']}*:\n\n"
                                f"Check Shopee Mall daily vouchers or monthly mega sales (e.g., 3.3 / 11.11)! "
                                f"Stack shop vouchers with Shopee Pay discount vouchers at checkout for the maximum discount."
                            )
                            send_message(sender_id, tip_msg)

                    elif payload.startswith("details_"):
                        product_key = payload.replace("details_", "")
                        if product_key in PRODUCT_MAP:
                            get_affiliate_reply(sender_id, product_key)

    return "EVENT_RECEIVED", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
