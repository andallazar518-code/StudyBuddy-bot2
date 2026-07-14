from flask import Flask, request
import requests
import os
import time
import random
from datetime import datetime

app = Flask(__name__)

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
VERIFY_TOKEN = "TUBO2026"

# = PALITAN MO TO NG TUNAY MONG SHOPEE SHOP LINK
MAIN_SHOPEE_STORE = "https://s.shopee.ph/qhsFU3xcr?smtt=0.0.9"

# = MEMORY NG BOT: {sender_id: {name, last_product, tasks}}
user_memory = {}
user_sessions = {}

PRODUCT_MAP = {
    "calculator": {"name": "Casio fx-991EX", "shopee": "https://s.shopee.ph/903Zywb2BV?smtt=0.0.9"},
    "notebook": {"name": "National Notebook 80s", "shopee": "https://s.shopee.ph/BSBSox6US?smtt=0.0.9"},
    "bag": {"name": "JanSport Backpack", "shopee": "https://s.shopee.ph/5AqrQ58Yd1?smtt=0.0.9"},
    "pen": {"name": "Pilot G2 0.5 Gel Pen", "shopee": "https://s.shopee.ph/AAFXNKQ3JD?smtt=0.0.9"},
    "lamp": {"name": "LED Study Lamp", "shopee": "https://s.shopee.ph/2Vq6FK56cb?smtt=0.0.9"},
    "laptop": {"name": "Lenovo Ideapad", "shopee": "https://s.shopee.ph/9AN0C8jKBb?smtt=0.0.9"},
    "phone": {"name": "Tecno", "shopee": "https://s.shopee.ph/30mMqwHnbk?smtt=0.0.9"},
}

def send_message(sender_id, text, quick_replies=None):
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "message": {"text": text[:2000]}}

    # = QUICK REPLIES BUTTONS
    if quick_replies:
        payload["message"]["quick_replies"] = quick_replies

    requests.post(url, json=payload)

def send_typing(sender_id, action="typing_on"):
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "sender_action": action}
    requests.post(url, json=payload)

def is_product_related(user_message):
    product_keywords = ["buy", "price", "magkano", "how much", "order", "bili", "shop", "shopee", "link"]
    message_lower = user_message.lower()
    for product in PRODUCT_MAP.keys():
        if product in message_lower:
            return True
    for keyword in product_keywords:
        if keyword in message_lower:
            return True
    return False

def check_product(user_message, sender_id):
    user_message_lower = user_message.lower().strip()

    # = MEMORY: SAVE NAME
    if "name is" in user_message_lower or "ako si" in user_message_lower:
        name = user_message_lower.replace("my name is", "").replace("name is", "").replace("ako si", "").strip()
        if sender_id not in user_memory: user_memory[sender_id] = {}
        user_memory[sender_id]['name'] = name.title()
        return f"Nice to meet you, {name.title()}! 😊 I'll remember that."

    # = GREETING HANDLER + QUICK REPLIES
    greetings = ["hi", "hello", "hey", "kamusta", "kumusta", "good morning", "good afternoon", "good evening"]
    if user_message_lower in greetings:
        name = user_memory.get(sender_id, {}).get('name', '')
        greeting = f"👋 Hi {name}!" if name else "👋 Hi!"
        qr = [
            {"content_type":"text", "title":"📱 Calculator", "payload":"calculator"},
            {"content_type":"text", "title":"📓 Notebook", "payload":"notebook"},
            {"content_type":"text", "title":"❓ Ask Question", "payload":"ask question"}
        ]
        send_message(sender_id, f"{greeting} Welcome to StudyBuddy PH 🤖\nWhat do you need help with today?", qr)
        return "HANDLED" # = Para hindi na mag reply ulit

    # = MOOD DETECTOR
    sad_words = ["pagod", "stress", "tired", "boring", "hirap", "hate studying"]
    if any(word in user_message_lower for word in sad_words):
        replies = ["Laban lang! 💪 5 min break muna ☕ Kaya mo yan", "Take it easy. One step at a time 😊", "Rest muna. Bumalik ka pag ready ka na"]
        return random.choice(replies)

    # = TO-DO LIST
    if "add task" in user_message_lower or "gawin" in user_message_lower:
        task = user_message_lower.replace("add task:", "").replace("add task", "").replace("gawin:", "").strip()
        if sender_id not in user_memory: user_memory[sender_id] = {}
        if 'tasks' not in user_memory[sender_id]: user_memory[sender_id]['tasks'] = []
        user_memory[sender_id]['tasks'].append(task)
        return f"✅ Added to your list: '{task}'\nType 'my tasks' to see all."

    if "my tasks" in user_message_lower:
        tasks = user_memory.get(sender_id, {}).get('tasks', [])
        if not tasks: return "Wala ka pang tasks 📝 Add ka gamit 'add task:...'"
        return "📝 Your Tasks:\n" + "\n".join([f"{i+1}. {t}" for i,t in enumerate(tasks)])

    # = STUDY TIMER
    if "pomodoro" in user_message_lower or "timer" in user_message_lower:
        try:
            minutes = int(''.join(filter(str.isdigit, user_message)))
            return f"⏰ Timer set for {minutes} minutes! I'll remind you to take a break."
        except: return "⏰ Type 'pomodoro 25' para 25 min study timer"

    # = WALANG KWENTANG WORDS
    useless = ["ok", "sige", "yes", "no", "thanks", "thank you", "salamat"]
    if user_message_lower in useless:
        if user_message_lower in ["thanks", "thank you", "salamat"]:
            return random.choice(["You're welcome! 😊", "No problem!", "Anytime!"])
        else:
            return "Sige 😊 Ano pa need mo?"

    found_products = []
    for product, p in PRODUCT_MAP.items():
        if product in user_message_lower:
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
    language = "Tagalog" if any(c in "ng ang sa" for c in user_message.lower()) else "English"
    try:
        name = ""
        prompt = f"""You are Study Buddy AI. A friendly tutor for Filipino students.
        RULE: Reply in {language}. Be helpful, short, friendly, use 1 emoji. Max 3 sentences.
        If it's homework/subject question, explain simply with 1 example.
        Customer question: {user_message}
        """
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        data = {"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": prompt}]}
        r = requests.post(url, headers=headers, json=data, timeout=15)
        r.raise_for_status()
        return r.json()['choices'][0]['message']['content']
    except Exception as e:
        print("GROQ ERROR:", e)
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

                    # = ANTI-SPAM
                    if sender_id in user_sessions and time.time() - user_sessions[sender_id] < 1:
                        continue
                    user_sessions[sender_id] = time.time()

                    if 'message' in event and 'text' in event['message']:
                        user_message = event['message']['text']
                        send_typing(sender_id, "typing_on")
                        time.sleep(0.8)

                        try:
                            product_reply = check_product(user_message, sender_id)
                            if product_reply == "HANDLED":
                                pass # = Na-handle na sa loob ng function
                            elif product_reply:
                                send_message(sender_id, product_reply)
                            else:
                                reply = ask_groq(user_message)
                                send_message(sender_id, reply)
                        finally:
                            send_typing(sender_id, "typing_off")
        return "ok", 200

@app.route('/', methods=['GET'])
def home():
    return "StudyBuddy Bot v7.0 All Features", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
