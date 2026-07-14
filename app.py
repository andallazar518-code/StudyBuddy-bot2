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

if not PAGE_ACCESS_TOKEN or not GROQ_API_KEY:
    print("ERROR: Missing PAGE_ACCESS_TOKEN or GROQ_API_KEY in ENV")

user_memory = {}
user_sessions = {}

def cleanup_memory():
    if len(user_memory) > 50:
        oldest = list(user_memory.keys())[0]
        del user_memory[oldest]

def send_message(sender_id, text, quick_replies=None):
    text = text[:2000]
    if "```" not in text and any(kw in text for kw in ["def ", "public class", "SELECT", "import ", "function ", "#include"]):
        text = f"```\n{text}\n```"

    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "message": {"text": text}}
    if quick_replies:
        payload["message"]["quick_replies"] = quick_replies
    try: requests.post(url, json=payload, timeout=10)
    except: print("Send error")

def send_typing(sender_id, action="typing_on"):
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "sender_action": action}
    try: requests.post(url, json=payload, timeout=5)
    except: pass

# = AFFILIATE PRODUCTS - HINDI TINANGGAL
MAIN_SHOPEE_STORE = "https://s.shopee.ph/qhsFU3xcr?smtt=0.0.9"
PRODUCT_MAP = {
    "calculator": {"name": "Casio fx-991EX", "shopee": "https://s.shopee.ph/903Zywb2BV?smtt=0.0.9"},
    "notebook": {"name": "National Notebook 80s", "shopee": "https://s.shopee.ph/BSBSox6US?smtt=0.0.9"},
    "bag": {"name": "JanSport Backpack", "shopee": "https://s.shopee.ph/5AqrQ58Yd1?smtt=0.0.9"},
    "pen": {"name": "Pilot G2 0.5 Gel Pen", "shopee": "https://s.shopee.ph/AAFXNKQ3JD?smtt=0.0.9"},
    "lamp": {"name": "LED Study Lamp", "shopee": "https://s.shopee.ph/2Vq6FK56cb?smtt=0.0.9"},
    "laptop": {"name": "Lenovo Ideapad", "shopee": "https://s.shopee.ph/9AN0C8jKBb?smtt=0.0.9"},
    "phone": {"name": "Tecno", "shopee": "https://s.shopee.ph/30mMqwHnbk?smtt=0.0.9"},
    "mouse": {"name": "Wireless Mouse", "shopee": "https://s.shopee.ph/30mMqwHnbk?smtt=0.0.9"},
    "keyboard": {"name": "Mechanical Keyboard", "shopee": "https://s.shopee.ph/30mMqwHnbk?smtt=0.0.9"},
    "headset": {"name": "Gaming Headset", "shopee": "https://s.shopee.ph/30mMqwHnbk?smtt=0.0.9"},
}

def is_product_related(user_message):
    product_keywords = ["buy", "price", "magkano", "how much", "order", "bili", "shop", "shopee", "link", "recommend"]
    message_lower = user_message.lower()
    for product in PRODUCT_MAP.keys():
        if re.search(r'\b' + re.escape(product) + r'\b', message_lower):
            return True
    for keyword in product_keywords:
        if keyword in message_lower:
            return True
    return False

def check_product(user_message, sender_id):
    user_message_lower = user_message.lower().strip()

    if "name is" in user_message_lower:
        name = user_message_lower.replace("my name is", "").replace("name is", "").strip()
        user_memory[sender_id] = {'name': name.title()}
        return f"Got it {name.title()}! 😎 BSIT Coding Mode + Affiliate ON"

    greetings = ["hi", "hello", "hey", "kamusta"]
    if user_message_lower in greetings:
        name = user_memory.get(sender_id, {}).get('name', 'BSIT Student')
        qr = [
            {"content_type":"text", "title":"💻 Debug Code", "payload":"debug"},
            {"content_type":"text", "title":"📚 Subject Help", "payload":"subject"},
            {"content_type":"text", "title":"🛒 School Gear", "payload":"gear"}
        ]
        send_message(sender_id, f"👋 Hi {name}!\nWelcome to BSIT Coding Buddy 🤖\nCode help + School gear recos here", qr)
        return "HANDLED"

    # = PRODUCT CHECK FIRST
    found_products = []
    for product, p in PRODUCT_MAP.items():
        if re.search(r'\b' + re.escape(product) + r'\b', user_message_lower):
            found_products.append(p)

    if found_products:
        reply = "💡 Eto ma-recommend ko for BSIT:\n\n"
        for p in found_products:
            reply += f"**{p['name']}**\nShop here: {p['shopee']}\n\n"
        return reply.strip()

    if is_product_related(user_message):
        return f"🔍 Check mo lahat ng BSIT gear ko dito:\n🛒 {MAIN_SHOPEE_STORE}"

    # = TODO
    if "add task" in user_message_lower:
        task = user_message_lower.replace("add task:", "").strip()
        if sender_id not in user_memory: user_memory[sender_id] = {}
        if 'tasks' not in user_memory[sender_id]: user_memory[sender_id]['tasks'] = []
        user_memory[sender_id]['tasks'].append(task)
        return f"✅ Added: '{task}'"

    if "my tasks" in user_message_lower:
        tasks = user_memory.get(sender_id, {}).get('tasks', [])
        if not tasks: return "Wala ka pang tasks 📝"
        return "📝 Your Tasks:\n" + "\n".join([f"{i+1}. {t}" for i,t in enumerate(tasks)])

    return None

def ask_groq_bsit(user_message):
    # = BLOCK COPYRIGHT
    if any(word in user_message.lower() for word in ["lyrics", "poem", "book"]):
        return "I can't share that due to copyright 😅 Pero sa coding and IT help kita 100%"

    tagalog_words = ["ng", "ang", "sa", "paano", "ano", "gawa"]
    language = "Tagalog" if any(word in user_message.lower().split() for word in tagalog_words) else "English"

    # = SUPER SMART CODING PROMPT
    models = ["llama-3.1-70b-versatile", "llama-3.1-8b-instant"]
    for model in models:
        try:
            prompt = f"""You are BSIT Coding Master AI. Expert in Python, Java, C++, WebDev, SQL, DSA.
            PERSONALITY: Senior Dev. Direct, helpful, 1 emoji max. Reply in {language}.
            RULES:
            1. If "gawa mo code" or "write code": Give FULL working code in ``` with comments.
            2. If "debug": Find error, explain, give FIXED code.
            3. If "explain": Simple explanation + 1 example code.
            4. Always give code that runs. No placeholders.
            5. Max 5 sentences + code block.

            Student: {user_message}
            Answer:"""
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
            data = {"model": model, "messages": [{"role": "user", "content": prompt}]}
            r = requests.post(url, headers=headers, json=data, timeout=20)
            r.raise_for_status()
            return r.json()['choices'][0]['message']['content']
        except:
            continue
    return "Sorry busy si AI ngayon 😅 Try mo ulit"

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
                    if sender_id in user_sessions and time.time() - user_sessions[sender_id] < 1:
                        continue
                    user_sessions[sender_id] = time.time()

                    if 'message' in event and 'text' in event['message']:
                        user_message = event['message']['text']
                        send_typing(sender_id, "typing_on")
                        time.sleep(0.5)
                        try:
                            product_reply = check_product(user_message, sender_id)
                            if product_reply == "HANDLED": pass
                            elif product_reply: send_message(sender_id, product_reply)
                            else:
                                reply = ask_groq_bsit(user_message)
                                send_message(sender_id, reply)
                        except Exception as e:
                            print("ERROR:", e)
                            send_message(sender_id, "Ay sorry nagka-error 😅")
                        finally:
                            send_typing(sender_id, "typing_off")
        return "ok", 200

@app.route('/', methods=['GET'])
def home():
    return "BSIT Coding + Affiliate v10.0", 200
