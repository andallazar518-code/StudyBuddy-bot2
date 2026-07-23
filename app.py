from flask import Flask, request, abort
import requests, os, time, random, re, json, hashlib, hmac
from supabase import create_client

app = Flask(__name__)

# FIX: Startup env check so it doesn't die silently
PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not PAGE_ACCESS_TOKEN or not GROQ_API_KEY:
    raise ValueError("Missing PAGE_ACCESS_TOKEN or GROQ_API_KEY")

VERIFY_TOKEN = "TUBO2026"
APP_SECRET = os.environ.get("FB_APP_SECRET")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None
user_sessions = {}
SESSION_COOLDOWN = 1.2
AFFILIATE_ID = "studybuddy"
MAIN_SHOPEE_STORE = "https://s.shopee.ph/qhsFU3xcr?smtt=0.0.9"

PRODUCT_MAP = {
    "calculator": {"name": "Casio fx-991EX Scientific Calculator", "shopee": "https://s.shopee.ph/903Zywb2BV?smtt=0.0.9", "hook": "Struggling with complex math? 📐", "benefit": "Approved for board exams. 552 functions"},
    "notebook": {"name": "National Notebook 80 Leaves", "shopee": "https://s.shopee.ph/BSBSox6US?smtt=0.0.9", "hook": "Ink keeps bleeding through? 📓", "benefit": "Thick 70gsm paper"},
    "laptop": {"name": "Lenovo Ideapad 3 Laptop", "shopee": "https://s.shopee.ph/9AN0C8jKBb?smtt=0.0.9", "hook": "Need a laptop for school & work? 💻", "benefit": "Budget-friendly. Intel i3"},
    "mouse": {"name": "Wireless Silent Mouse", "shopee": "https://s.shopee.ph/7pKqL9xAbc?smtt=0.0.9", "hook": "Wrist pain from clicking? 🖱️", "benefit": "Ergonomic design. Silent click"},
    "keyboard": {"name": "RGB Mechanical Keyboard", "shopee": "https://s.shopee.ph/8rLmN2pQrs?smtt=0.0.9", "hook": "Want faster typing? ⌨️", "benefit": "Blue switches. Plug and play"},
    "headset": {"name": "Gaming Headset with Noise Cancelling Mic", "shopee": "https://s.shopee.ph/4wZxY6vTuv?smtt=0.0.9", "hook": "Can't hear clearly in online class? 🎧", "benefit": "Crystal clear mic"},
    "bag": {"name": "JanSport SuperBreak Backpack", "shopee": "https://s.shopee.ph/5AqrQ58Yd1?smtt=0.0.9", "hook": "Bag keeps getting wet? 🎒", "benefit": "Water resistant. 15L capacity"},
    "lamp": {"name": "LED Desk Study Lamp with USB", "shopee": "https://s.shopee.ph/2Vq6FK56cb?smtt=0.0.9", "hook": "Eyes getting tired at night? 💡", "benefit": "3 light modes. Eye protection"},
}

def get_tracked_link(base_url, sender_id, product="store"):
    """Add tracking payload to shopee link"""
    tracker = f"aff_id={AFFILIATE_ID}_{sender_id}_{product}"
    if "?" in base_url: return f"{base_url}&{tracker}"
    else: return f"{base_url}?{tracker}"

def verify_signature(req):
    if not APP_SECRET: return True
    signature = req.headers.get("X-Hub-Signature-256", "")
    if not signature: return False
    hash = hmac.new(APP_SECRET.encode(), req.data, hashlib.sha256).hexdigest()
    return hmac.compare_digest(f"sha256={hash}", signature)

def get_fb_name(sender_id):
    if not PAGE_ACCESS_TOKEN: return None
    try:
        url = f"https://graph.facebook.com/v19.0/{sender_id}?fields=first_name&access_token={PAGE_ACCESS_TOKEN}"
        r = requests.get(url, timeout=5)
        if r.status_code == 200: return r.json().get("first_name")
    except Exception as e: print(f"FB NAME ERROR for {sender_id}:", e)
    return None

def _load_history(raw):
    if not raw: return []
    if isinstance(raw, list): return raw
    try: return json.loads(raw)
    except: return []

def _dump_history(hist):
    trimmed = []
    for m in hist[-10:]:
        m_copy = m.copy()
        m_copy['content'] = m_copy['content'][:500]
        trimmed.append(m_copy)
    return json.dumps(trimmed)

def get_user(sender_id):
    default = {"sender_id": sender_id, "name": None, "chat_count": 0, "rejected_affiliate": False, "reject_time": None, "auto_sent": False, "last_promo_time": None, "waiting_for_name": False, "conversation_history": [], "last_interest": None, "last_bot_action": None}
    if not supabase: return default
    try:
        data = supabase.table('users').select("*").eq("sender_id", sender_id).execute()
        if data.data:
            user = data.data[0]
            user['conversation_history'] = _load_history(user.get('conversation_history'))
            if not user.get('name') or user.get('name') == 'Boss':
                fb_name = get_fb_name(sender_id)
                if fb_name: update_user(sender_id, {"name": fb_name}); user['name'] = fb_name
            return user
        else:
            fb_name = get_fb_name(sender_id)
            new_user = default.copy(); new_user.update({"name": fb_name})
            supabase.table('users').insert({**new_user, "conversation_history": _dump_history([])}).execute()
            return new_user
    except Exception as e: print(f"DB GET ERROR for {sender_id}:", e); return default

def update_user(sender_id, updates):
    if not supabase: return
    if "conversation_history" in updates: updates["conversation_history"] = _dump_history(updates["conversation_history"])
    try: supabase.table('users').update(updates).eq("sender_id", sender_id).execute()
    except Exception as e: print(f"DB UPDATE ERROR for {sender_id}:", e)

def send_message(sender_id, text, quick_replies=None):
    if not PAGE_ACCESS_TOKEN: return
    text = str(text)[:2000]
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "message": {"text": text}}
    if quick_replies: payload["message"]["quick_replies"] = quick_replies
    try: requests.post(url, json=payload, timeout=10)
    except Exception as e: print(f"Send error for {sender_id}:", e)

def send_button_template(sender_id, text, buttons):
    if not PAGE_ACCESS_TOKEN: return
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "message": {"attachment": {"type": "template", "payload": {"template_type": "button", "text": text[:640], "buttons": buttons}}}}
    try: requests.post(url, json=payload, timeout=10)
    except Exception as e: print(f"Button send error:", e)

# NEW: Send carousel of recommended products
def send_product_carousel(sender_id):
    if not PAGE_ACCESS_TOKEN: return
    elements = []
    for product, p in list(PRODUCT_MAP.items())[:4]: # show first 4 products
        tracked_link = get_tracked_link(p['shopee'], sender_id, product)
        elements.append({
            "title": p['name'],
            "subtitle": p['hook'],
            "buttons": [
                {"type": "web_url", "url": tracked_link, "title": "👉 Buy Now"},
                {"type": "postback", "title": "🔍 Details", "payload": f"details_{product}"}
            ]
        })
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
    try: requests.post(url, json=payload, timeout=10)
    except Exception as e: print(f"Carousel send error:", e)

def send_typing(sender_id, action="typing_on"):
    if not PAGE_ACCESS_TOKEN: return
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    try: requests.post(url, json={"recipient": {"id": sender_id}, "sender_action": action}, timeout=5)
    except: pass

def should_save_to_memory(msg):
    skip = ["hi", "hello", "hey", "help", "menu", "shop", "yes", "no", "y", "n", "reset name", "commands"]
    return msg.lower().strip() not in skip

def check_affiliate_intent(msg):
    msg = msg.lower()
    product_words = list(PRODUCT_MAP.keys())
    buy_words = ["buy", "shop", "shopee", "price", "link", "gear", "order", "store"]
    if msg in ["yes", "y", "no", "n"]: return False
    return any(w in msg for w in product_words) or any(w in msg for w in buy_words)

def get_affiliate_reply(sender_id, msg):
    msg = msg.lower()
    for product, p in PRODUCT_MAP.items():
        if re.search(r'\b' + re.escape(product) + r'\b', msg):
            tracked_link = get_tracked_link(p['shopee'], sender_id, product)
            text = f"💡 **{p['name']}**\n\n{p['hook']}\n\n✅ **Why students like it:** {p['benefit']}\n\n*Disclosure: Affiliate link*"
            buttons = [
                {"type": "web_url", "url": tracked_link, "title": "👉 View on Shopee"},
                {"type": "postback", "title": "🔍 Price Tips", "payload": f"compare_{product}"},
                {"type": "postback", "title": "📎 See All", "payload": "shop"}
            ]
            send_button_template(sender_id, text, buttons)
            return True
    if any(k in msg for k in ["buy", "shop", "shopee", "gear", "store"]):
        tracked_link = get_tracked_link(MAIN_SHOPEE_STORE, sender_id, "store")
        text = f"🛒 **Student Essentials Store**\n\nBrowse all student vouchers here.\n\n*Disclosure: Affiliate link*"
        buttons = [{"type": "web_url", "url": tracked_link, "title": "🛒 Open Store"}]
        send_button_template(sender_id, text, buttons)
        return True
    return False

def handle_commands(user_message, sender_id):
    try:
        msg = user_message.lower().strip(); raw_msg = user_message; user = get_user(sender_id); now = time.time()
        if user.get('reject_time') and now - user['reject_time'] > 86400:
            update_user(sender_id, {"rejected_affiliate": False, "auto_sent": False, "reject_time": None, "last_promo_time": None}); user = get_user(sender_id)
        if user.get('last_promo_time') and now - user['last_promo_time'] > 86400:
            update_user(sender_id, {"auto_sent": False}); user = get_user(sender_id)

        skip_count = ["hi","hello","hey","help","menu","shop","yes","no","y","n","reset name","commands","clear memory"]
        new_count = user.get('chat_count', 0) + 1 if msg not in skip_count else user.get('chat_count', 0)
        update_user(sender_id, {"chat_count": new_count})
        print(f"[{sender_id}] MSG: {msg} | COUNT: {new_count}")

        if "@meta ai" in raw_msg.lower() or "open link" in msg:
            if user.get('rejected_affiliate'): return "Got it! 😊 I'll stop asking about supplies for 24 hours."
            tracked_link = get_tracked_link(MAIN_SHOPEE_STORE, sender_id, "openlink")
            send_button_template(sender_id, f"🛒 **Here's my student essentials store:**\n\n*Disclosure: Affiliate link*", [{"type": "web_url", "url": tracked_link, "title": "🛒 Open Store"}]); return None
        if msg in ["clear memory", "reset memory"]: update_user(sender_id, {"conversation_history": [], "last_interest": None}); return "🧠 Memory cleared! Fresh start 😊"
        if user.get('waiting_for_name') and 1 <= len(msg.split()) <= 3 and msg not in skip_count:
            name = user_message.strip().title(); update_user(sender_id, {"name": name, "waiting_for_name": False}); return f"👋 Nice to meet you {name}! Got it saved 😊"
        if msg.startswith("shopee_"):
            product = msg.replace("shopee_", "")
            if product in PRODUCT_MAP:
                p = PRODUCT_MAP[product]
                tracked_link = get_tracked_link(p['shopee'], sender_id, product)
                send_button_template(sender_id, f"👉 **{p['name']}**\n\n*Disclosure: Affiliate link*", [{"type": "web_url", "url": tracked_link, "title": "Buy Now"}]); return None
        if msg in ["yes", "y"]:
    # NEW: If user says yes to "Need the link again?"
    if user.get('last_interest') and not user.get('last_bot_action') == "asked_promo":
        last_product = str(user['last_interest']).lower()
        for product in PRODUCT_MAP.keys():
            if product in last_product:
                get_affiliate_reply(sender_id, product) # resend the card
                return None
    
    # OLD: This is for promo "yes"
    if user.get('last_bot_action') == "asked_promo":
        if user.get('rejected_affiliate'): update_user(sender_id, {"last_bot_action": None}); return "No problem! 😊 I won't send store links until the 24 hours are up."
        update_user(sender_id, {"auto_sent": True, "last_promo_time": now, "last_bot_action": None})
        tracked_link = get_tracked_link(MAIN_SHOPEE_STORE, sender_id, "promo")
        send_button_template(sender_id, f"🛒 **Here's my student essentials store:**\n\n*Disclosure: Affiliate link*", [{"type": "web_url", "url": tracked_link, "title": "🛒 Open Store"}]); return None
    update_user(sender_id, {"last_bot_action": None}); return None
        if msg in ["no", "n", "no need", "not now", "pass", "later"]:
            if user.get('last_bot_action') == "asked_promo": update_user(sender_id, {"rejected_affiliate": True, "reject_time": now, "waiting_for_name": False, "last_bot_action": None}); return "Got it! 😊 I'll stop asking about supplies for 24 hours."
            update_user(sender_id, {"last_bot_action": None}); return None
        if msg == "reset name": update_user(sender_id, {"name": None, "waiting_for_name": True}); return "👋 Name reset! What's your name?"
        if msg.startswith("setname_"): fb_name = get_fb_name(sender_id) or "Friend"; update_user(sender_id, {"name": fb_name, "waiting_for_name": False}); return f"👋 Nice to meet you {fb_name}! Got it saved 😊"
        if msg in ["help", "menu", "commands"]: return """📚 **StudyBuddy Commands:**\n`Hi/Hello` - Greet\n`calculator/laptop/bag` - Product recommendation\n`shop` - Show recommended products\n`My name is [name]` - Save name\n`Reset name` - Change name\n`Clear memory` - Reset AI memory\n`Help` - Show this menu"""
        if "name is" in msg or "i am" in msg:
            name = msg.replace("my name is", "").replace("name is", "").replace("i am", "").strip().title()
            update_user(sender_id, {"name": name, "waiting_for_name": False}); return f"👋 Welcome {name}! Nice to meet you 😊"
        
        # UPDATED: shop now shows carousel
        if msg == "shop" or msg == "recommend":
            if user.get('rejected_affiliate'): return "Got it! 😊 I'll stop asking about supplies for 24 hours. Type `help` for other commands."
            send_message(sender_id, "🛒 **Here are my top student picks for you:**")
            send_product_carousel(sender_id)
            return None

        if msg in ["hi", "hello", "hey"]:
            name = user.get('name')
            if user.get('last_interest') and name:
                last = str(user['last_interest']).lower()
                if any(p in last for p in PRODUCT_MAP.keys()): return f"Hi {name}! 😊 How is the {user['last_interest']} you checked? Need the link again?"
            if not name: qr = [{"content_type":"text", "title":"👉 Set Name", "payload":"setname_User"}]; update_user(sender_id, {"waiting_for_name": True}); return {"text": "👋 Hi! Welcome to StudyBuddy PH 🤖\n\nTo make it personal, what's your name?", "quick_replies": qr}
            if new_count > 0 and new_count % 8 == 0 and not user.get('rejected_affiliate') and not user.get('auto_sent'):
                update_user(sender_id, {"auto_sent": True, "last_promo_time": now, "last_bot_action": "asked_promo"})
                qr = [{"content_type":"text", "title":"📎 Open Link", "payload":"shop"}, {"content_type":"text", "title":"❌ Pass", "payload":"no"}]
                return {"text": f"Quick tip {name} 😊\nNeed school supplies? I have a curated list with student vouchers.\n\nWant it?\n\nReply: `yes` or `no`", "quick_replies": qr}
            return f"**StudyBuddy v14.39.8 EN** 🤖\nHi {name}!\n\nAsk me anything 😊 Type `help` for commands"

        for product in PRODUCT_MAP.keys():
            if re.search(r'\b' + re.escape(product) + r'\b', msg):
                update_user(sender_id, {"last_interest": user_message})
                get_affiliate_reply(sender_id, msg)
                return None
        if not user.get('rejected_affiliate') and check_affiliate_intent(msg):
            update_user(sender_id, {"last_interest": user_message})
            if get_affiliate_reply(sender_id, msg): return None
        if any(w in msg for w in ["tired", "stress", "hard", "sad"]): return random.choice(["Hang in there! Take a 5 min break ☕ You got this!", "You can do it! One step at a time 😊 I'm here for you"])
    except Exception as e:
        print("HANDLE COMMANDS CRASH:", e)
        return "Oops I crashed 😅 Try typing again"
    return None

def ask_groq(user_message, sender_id):
    try:
        user = get_user(sender_id); name = user.get('name') or "there"
        if any(word in user_message.lower() for word in ["lyrics", "poem", "song"]): return "I can't share that due to copyright 😅 But you can ask me anything else!"
        history = user.get('conversation_history', [])
        if should_save_to_memory(user_message): history.append({"role": "user", "content": user_message})
        messages = [{"role": "system", "content": f"You are StudyBuddy PH v14.39.8 EN. A friendly AI Assistant from the Philippines. Reply ONLY in English. Keep it under 8 sentences. User name: {name}"}]
        messages.extend(history[-10:])
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        data = {"model": "llama-3.3-70b-versatile", "messages": messages, "temperature": 0.7, "max_tokens": 300}
        r = requests.post(url, headers=headers, json=data, timeout=45); r.raise_for_status()
        ai_reply = r.json()['choices'][0]['message']['content']
        if should_save_to_memory(user_message): history.append({"role": "assistant", "content": ai_reply}); update_user(sender_id, {"conversation_history": history})
        return ai_reply
    except Exception as e: print(f"GROQ EXCEPTION for {sender_id}:", e); return f"The AI had an error 😅 But I'm still here {name}. Try again."

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    global user_sessions
    if request.method == 'GET':
        if request.args.get("hub.verify_token") == VERIFY_TOKEN: return request.args.get("hub.challenge"), 200
        return "Error", 403
    if request.method == 'POST':
        if not verify_signature(request): abort(403)
        data = request.get_json()
        now = time.time()
        user_sessions = {k:v for k,v in user_sessions.items() if now - v < 3600}

        if data.get('object') == 'page':
            for entry in data.get('entry', []):
                for event in entry.get('messaging', []):
                    sender_id = event['sender']['id']
                    if sender_id in user_sessions and time.time() - user_sessions[sender_id] < SESSION_COOLDOWN: continue
                    user_sessions[sender_id] = time.time(); send_typing(sender_id)
                    try:
                        if 'postback' in event:
                            payload = event['postback']['payload']
                            if payload == 'GET_STARTED':
                                user = get_user(sender_id); name = user.get('name') or 'there'
                                send_message(sender_id, f"👋 **Welcome {name}!**\n\nI'm StudyBuddy PH 🤖\nYour AI study assistant.\n\nType `help` to see what I can do!"); continue

                            # NEW: Handle carousel details click
                            if payload.startswith("details_"):
                                product = payload.replace("details_", "")
                                if product in PRODUCT_MAP:
                                    p = PRODUCT_MAP[product]
                                    tracked_link = get_tracked_link(p['shopee'], sender_id, product)
                                    text = f"💡 **{p['name']}**\n\n{p['hook']}\n\n✅ **Why students like it:** {p['benefit']}\n\n*Disclosure: Affiliate link*"
                                    buttons = [
                                        {"type": "web_url", "url": tracked_link, "title": "👉 View on Shopee"},
                                        {"type": "postback", "title": "🔍 Price Tips", "payload": f"compare_{product}"}
                                    ]
                                    send_button_template(sender_id, text, buttons)
                                    continue

                            if payload.startswith("compare_"):
                                product = payload.replace("compare_", "")
                                if product in PRODUCT_MAP:
                                    p = PRODUCT_MAP[product]
                                    send_message(sender_id, f"📊 **{p['name']} Price Tips:**\n\n1. Check Shopee Mall for vouchers\n2. Add to cart during 15.15 / 25 sale\n3. Use student voucher for extra 10% off\nNeed the link again? Type `{product}`")
                                    continue

                            if payload == "shop":
                                tracked_link = get_tracked_link(MAIN_SHOPEE_STORE, sender_id, "shop")
                                send_button_template(sender_id, f"🛒 **Here's my student essentials store:**\n\n*Disclosure: Affiliate link*", [{"type": "web_url", "url": tracked_link, "title": "🛒 Open Store"}]); continue

                        if 'message' in event and 'attachments' in event['message']: send_message(sender_id, "I can only reply to text messages for now 😅"); continue
                        if 'message' in event and 'text' in event['message']:
                            user_message = event['message']['text']
                            cmd = handle_commands(user_message, sender_id)
                            if isinstance(cmd, dict): send_message(sender_id, cmd["text"], cmd.get("quick_replies"))
                            elif cmd: send_message(sender_id, cmd)
                            else: ai = ask_groq(user_message, sender_id); send_message(sender_id, ai)
                    except Exception as e: print(f"ERROR for {sender_id}:", e); send_message(sender_id, "Error 😅")
                    finally: send_typing(sender_id, "typing_off")
        return "ok", 200

@app.route('/', methods=['GET'])
def home(): return "StudyBuddy v14.39.8", 200
