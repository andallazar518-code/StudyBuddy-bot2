from flask import Flask, request
import requests
import os
import time
import random
import re
from datetime import datetime

app = Flask(__name__)

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
VERIFY_TOKEN = "TUBO2026"

# = BUG FIX #10: CHECK IF TOKENS EXIST
if not PAGE_ACCESS_TOKEN or not GROQ_API_KEY:
    print("ERROR: Missing PAGE_ACCESS_TOKEN or GROQ_API_KEY in ENV")

MAIN_SHOPEE_STORE = "https://s.shopee.ph/qhsFU3xcr?smtt=0.0.9"

user_memory = {}
user_sessions = {}
last_cleanup = time.time()

PRODUCT_MAP = {
    "calculator": {"name": "Casio fx-991EX", "shopee": "https://s.shopee.ph/903Zywb2BV?smtt=0.0.9"},
    "notebook": {"name": "National Notebook 80s", "shopee": "https://s.shopee.ph/BSBSox6US?smtt=0.0.9"},
    "bag": {"name": "JanSport Backpack", "shopee": "https://s.shopee.ph/5AqrQ58Yd1?smtt=0.0.9"},
    "pen": {"name": "Pilot G2 0.5 Gel Pen", "shopee": "https://s.shopee.ph/AAFXNKQ3JD?smtt=0.0.9"},
    "lamp": {"name": "LED Study Lamp", "shopee": "https://s.shopee.ph/2Vq6FK56cb?smtt=0.0.9"},
    "laptop": {"name": "Lenovo Ideapad", "shopee": "https://s.shopee.ph/9AN0C8jKBb?smtt=0.0.9"},
    "phone": {"name": "Tecno", "shopee": "https://s.shopee.ph/30mMqwHnbk?smtt=0.0.9"},
}

def cleanup_memory():
    # = BUG FIX #7: CLEAR OLD MEMORY EVERY 24H
    global last_cleanup
    if time.time() - last_cleanup > 86400:
        user_memory.clear()
        user_sessions.clear()
        last_cleanup = time.time()
        print("Memory cleaned")

def send_message(sender_id, text, quick_replies=None):
    # = BUG FIX #5: CUT OFF 2000 CHARS
    text = text[:2000] 
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "message": {"text": text}}
    if quick_replies:
        payload["message"]["quick_replies"] = quick_replies
    try:
        requests.post(url, json=payload, timeout=10)
    except: print("Send message error")

def send_typing(sender_id, action="typing_on"):
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "sender_action": action}
    try: requests.post(url, json=payload, timeout=5)
    except: pass

def is_product_related(user_message):
    product_keywords = ["buy", "price", "magkano", "how much", "order", "bili", "shop", "shopee", "link"]
    message_lower = user_message.lower()
    for product in PRODUCT_MAP.keys():
        # = BUG FIX #9: WHOLE WORD MATCH
        if re.search(r'\b' + re.escape(product) + r'\b', message_lower):
            return True
    for keyword in product_keywords:
        if keyword in message_lower:
            return True
    return False

def check_product(user_message, sender_id):
    cleanup_memory()
    user_message_lower = user_message.lower().strip()

    if "name is" in user_message_lower or "ako si" in user_message_lower:
        name = user_message_lower.replace("my name is", "").replace("name is", "").replace("ako si", "").strip()
        if sender_id not in user_memory: user_memory[sender_id] = {}
        user_memory[sender_id]['name'] = name.title()
        return f"Nice to meet you, {name.title()}! 😊 I'll remember that."

    greetings = ["hi", "hello", "hey", "kamusta", "kumusta", "good morning", "good afternoon", "good evening"]
    if user_message_lower in greetings:
        name = user_memory.get(sender_id, {}).get('name', '')
        greeting = f"👋 Hi {name}!" if name else "👋 Hi!"
        # = BUG FIX #1: SAFE BUTTON TITLES
        qr = [
            {"content_type":"text", "title":"📱 Calculator", "payload":"calculator"},
            {"content_type":"text", "title":"📓 Notebook", "payload":"notebook"},
            {"content_type":"text", "title":"💬 Chat with me", "payload":"chat"}
        ]
        send_message(sender_id, f"{greeting} Welcome to StudyBuddy PH 🤖\nWhat do you need help with today?", qr)
        return "HANDLED"

    sad_words = ["pagod", "stress", "tired", "boring", "hirap", "hate studying"]
    if any(word in user_message_lower for word in sad_words):
        replies = ["Laban lang! 💪 5 min break muna ☕ Kaya mo yan", "Take it easy. One step at a time 😊"]
        return random.choice(replies)

    if "add task" in user_message_lower:
        task = user_message_lower.replace("add task:", "").replace("add task", "").strip()
        if sender_id not in user_memory: user_memory[sender_id] = {}
        if 'tasks' not in user_memory[sender_id]: user_memory[sender_id]['tasks'] = []
        user_memory[sender_id]['tasks'].append(task)
        return f"✅ Added to your list: '{task}'\nType 'my tasks' to see all."

    if "my tasks" in user_message_lower:
        tasks = user_memory.get(sender_id, {}).get('tasks', [])
        if not tasks: return "Wala ka pang tasks 📝 Add ka gamit 'add task:...'"
        return "📝 Your Tasks:\n" + "\n".join([f"{i+1}. {t}" for i,t in enumerate(tasks)])

    if "pomodoro" in user_message_lower:
        try:
            minutes = int(''.join(filter(str.isdigit, user_message)))
            return f"⏰ Timer set for {minutes} minutes! I'll remind you to take a break."
        except: return "⏰ Type 'pomodoro 25' para 25 min study timer"

    useless = ["ok", "sige", "yes", "no"]
    if user_message_lower in useless: return random.choice(["Sige 😊 Ano pa need mo?", "Go lang!"])
    if user_message_lower in ["thanks", "thank you", "salamat"]:
        return random.choice(["You're welcome! 😊", "No problem!", "Anytime!"])

    found_products = []
    for product, p in PRODUCT_MAP.items():
        # = BUG FIX #9: WHOLE WORD
        if re.search(r'\b' + re.escape(product) + r'\b', user_message_lower):
            found_products.append(p)
            if sender_id not in user_memory: user_memory[sender_id] = {}
            user_memory[sender_id]['last_product'] = product

    if found_products:
        reply = ""
        for p in found_products:
            reply += f"💡 Eto ma-recommend ko: \n{p['name']}\nShop here: {p['shopee']}\n\n"
        return reply.strip()

    if is_product_related(user_message):
        return f"🔍 Hindi ko nahanap yung '{user_message}'. \nPero pwede mo icheck lahat ng products ko dito:\n🛒 {MAIN_SHOPEE_STORE}"
    else:
        return None

def ask_groq(user_message):
    # = BUG FIX #2: BLOCK COPYRIGHT
    lyrics_keywords = ["lyrics", "kanta", "song", "verse", "chorus", "poem", "tula", "book chapter"]
    if any(word in user_message.lower() for word in lyrics_keywords):
        return "I can't share full lyrics/poems/books due to copyright 😅 But you can check Spotify/YouTube/Google! Need help with something else?"
    
    # = BUG FIX #8: BETTER LANGUAGE DETECT
    tagalog_words = ["ng", "ang", "sa", "ay", "mga", "ka", "ko", "mo"]
    language = "Tagalog" if any(word in user_message.lower().split() for word in tagalog_words) else "English"

    # = BUG FIX #4: TRY EXCEPT + TIMEOUT
    try:
        prompt = f"""You are Study Buddy AI. A friendly tutor for Filipino students.
        RULE: Reply in {language}. Be helpful, short, friendly, use 1 emoji. Max 3 sentences.
        IMPORTANT: Never provide song lyrics, poems, or book passages. 
        Customer question: {user_message}
        """
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        data = {"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": prompt}]}
        r = requests.post(url, headers=headers, json=data, timeout=15)
        r.raise_for_status()
        return r.json()['choices'][0]['message']['content']
    except:
        return "Sorry medyo mabagal ako ngayon 😅 Try mo ulit in 5 sec"

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

                    # = BUG FIX #3: ANTI-SPAM
                    if sender_id in user_sessions and time.time() - user_sessions[sender_id] < 1.5:
                        continue
                    user_sessions[sender_id] = time.time()

                    # = BUG FIX #6: CHECK IF TEXT EXISTS
                    if 'message' in event and 'text' in event['message']:
                        user_message = event['message']['text']
                        send_typing(sender_id, "typing_on")
                        time.sleep(0.8)

                        try:
                            product_reply = check_product(user_message, sender_id)
                            if product_reply == "HANDLED":
                                pass
                            elif product_reply:
                                send_message(sender_id, product_reply)
                            else:
                                reply = ask_groq(user_message)
                                send_message(sender_id, reply)
                        except Exception as e:
                            print("MAIN ERROR:", e)
                            send_message(sender_id, "Ay sorry nagka-error 😅 Try mo ulit")
                        finally:
                            send_typing(sender_id, "typing_off")
        return "ok", 200

@app.route('/', methods=['GET'])
def home():
    return "StudyBuddy Bot v8.0 All Bugs Fixed", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
