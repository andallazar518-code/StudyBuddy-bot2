from flask import Flask, request
import requests
import os
import time

app = Flask(__name__)

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
VERIFY_TOKEN = "TUBO2026"

# = PALITAN MO TO NG TUNAY MONG SHOPEE SHOP LINK
MAIN_SHOPEE_STORE = "https://s.shopee.ph/qhsFU3xcr?smtt=0.0.9"

PRODUCT_MAP = {
    "calculator": {"name": "Casio fx-991EX", "shopee": "https://s.shopee.ph/903Zywb2BV?smtt=0.0.9"},
    "notebook": {"name": "National Notebook 80s", "shopee": "https://s.shopee.ph/BSBSox6US?smtt=0.0.9"},
    "bag": {"name": "JanSport Backpack", "shopee": "https://s.shopee.ph/5AqrQ58Yd1?smtt=0.0.9"},
    "pen": {"name": "Pilot G2 0.5 Gel Pen", "shopee": "https://s.shopee.ph/AAFXNKQ3JD?smtt=0.0.9"},
    "lamp": {"name": "LED Study Lamp", "shopee": "https://s.shopee.ph/2Vq6FK56cb?smtt=0.0.9"},
    "laptop": {"name": "Lenovo Ideapad", "shopee": "https://s.shopee.ph/9AN0C8jKBb?smtt=0.0.9"},
    "phone": {"name": "Tecno", "shopee": "https://s.shopee.ph/30mMqwHnbk?smtt=0.0.9"},
}

def send_message(sender_id, text):
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "message": {"text": text[:2000]}}
    requests.post(url, json=payload)

def send_typing(sender_id, action="typing_on"):
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "sender_action": action}
    requests.post(url, json=payload)

def is_product_related(user_message):
    # = BUG FIX: CHECK KUNG PRODUCT BA TALAGA YUNG TINATANONG
    product_keywords = ["buy", "price", "magkano", "how much", "order", "bili", "shop", "shopee", "link"]
    message_lower = user_message.lower()

    # Kung may product keyword OR nasa PRODUCT_MAP
    for product in PRODUCT_MAP.keys():
        if product in message_lower:
            return True
    for keyword in product_keywords:
        if keyword in message_lower:
            return True
    return False

def check_product(user_message):
    user_message_lower = user_message.lower().strip()

    # = GREETING HANDLER
    greetings = ["hi", "hello", "hey", "kamusta", "kumusta", "good morning", "good afternoon", "good evening"]
    if user_message_lower in greetings:
        if any(word in user_message_lower for word in ["hi", "hello", "hey", "good"]):
            return "👋 Hi! Welcome to StudyBuddy PH 🤖\nWhat are you looking for today? Calculator, notebook, bag?"
        else:
            return "👋 Kumusta! Welcome sa StudyBuddy PH 🤖\nAnong hinahanap mo today? Calculator, notebook, bag?"

    # = WALANG KWENTANG WORDS
    useless = ["ok", "sige", "yes", "no", "thanks", "thank you", "salamat"]
    if user_message_lower in useless:
        if user_message_lower in ["thanks", "thank you", "salamat"]:
            return "You're welcome! 😊 Need anything else?"
        else:
            return "Sige 😊 Ano pa need mo? Sabihin mo lang product name."

    found_products = []
    for product, p in PRODUCT_MAP.items():
        if product in user_message_lower:
            found_products.append(p)

    # = KUNG MAY NAKITA SA PRODUCT_MAP
    if found_products:
        reply = ""
        for p in found_products:
            if any(word in user_message_lower for word in ["what", "how", "where", "can", "is", "do", "help"]):
                reply += f"💡 I recommend this: \n{p['name']}\nShop here: {p['shopee']}\n\n"
            else:
                reply += f"💡 Eto ma-recommend ko: \n{p['name']}\nShop here: {p['shopee']}\n\n"
        return reply.strip()

    # = BUG FIX DITO: KUNG WALANG PRODUCT AT HINDI PRODUCT RELATED, RETURN NONE
    # = Para si Groq na sumagot
    if is_product_related(user_message):
        if any(word in user_message_lower for word in ["what", "how", "where", "can", "is", "do", "help"]):
            return f"🔍 I couldn't find '{user_message}'. \nBut you can check all my products here:\n🛒 {MAIN_SHOPEE_STORE}"
        else:
            return f"🔍 Hindi ko nahanap yung '{user_message}'. \nPero pwede mo icheck lahat ng products ko dito:\n🛒 {MAIN_SHOPEE_STORE}"
    else:
        return None # = SI GROQ NA BAHALA DITO

def ask_groq(user_message):
    language = "Tagalog"
    try:
        if any(word in user_message.lower() for word in ["what", "how", "where", "can", "is", "do", "help"]):
            language = "English"

        prompt = f"""You are Study Buddy AI. A friendly AI assistant for students in the Philippines selling school supplies.
        RULE: Reply in {language}. Be helpful, short, friendly, and use emojis. Max 2 sentences.
        If they ask for a product not in the list, suggest they check the Shopee store.
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
        if language == "English":
            return "Sorry I'm a bit slow right now 😅 What product do you need?"
        else:
            return "Sorry medyo mabagal ako ngayon 😅 Anong product need mo?"

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
                    if 'message' in event and 'text' in event['message']:
                        user_message = event['message']['text']

                        send_typing(sender_id, "typing_on")
                        time.sleep(0.5)

                        try:
                            product_reply = check_product(user_message)
                            if product_reply:
                                reply = product_reply
                            else:
                                reply = ask_groq(user_message) # = DITO NA PAPASOK YUNG "1+1" AT "HOW TO COOK RICE"
                        finally:
                            send_typing(sender_id, "typing_off")

                        send_message(sender_id, reply)
        return "ok", 200

@app.route('/', methods=['GET'])
def home():
    return "StudyBuddy Bot v6.0 Smart Reply", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
