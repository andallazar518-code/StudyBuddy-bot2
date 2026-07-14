from flask import Flask, request
import requests
import os

app = Flask(__name__)

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
VERIFY_TOKEN = "TUBO2026"

PRODUCT_MAP = {
    "calculator": {"name": "Casio fx-991EX", "shopee": "https://s.shopee.ph/903Zywb2BV"},
    "notebook": {"name": "National Notebook 80s", "shopee": "https://s.shopee.ph/BSBSox6US"},
    "bag": {"name": "JanSport Backpack", "shopee": "https://s.shopee.ph/5AqrQ58Yd1"},
    "pen": {"name": "Pilot G2 0.5 Gel Pen", "shopee": "https://s.shopee.ph/AAFXNKQ3JD"},
    "lamp": {"name": "LED Study Lamp", "shopee": "https://s.shopee.ph/2Vq6FK56cb"},
    "laptop": {"name": "Lenovo Ideapad", "shopee": "https://s.shopee.ph/9AN0C8jKBb"},
    "phone": {"name": "Tecno", "shopee": "https://s.shopee.ph/30mMqwHnbk"},
}

def send_message(sender_id, text):
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "message": {"text": text[:2000]}}
    requests.post(url, json=payload)

def check_product(user_message):
    user_message = user_message.lower()
    for product, p in PRODUCT_MAP.items():
        if product in user_message:
            # Auto detect language
            if any(word in user_message for word in ["what", "how", "where", "can", "is", "do", "help"]):
                return f"💡 Are you looking for this? \n{p['name']}\nShopee: {p['shopee']}"
            else:
                return f"💡 Naghahanap ka ba nito? \n{p['name']}\nShopee: {p['shopee']}"
    return ""

def ask_groq(user_message):
    try:
        # Auto detect language
        if any(word in user_message.lower() for word in ["what", "how", "where", "can", "is", "do", "help"]):
            language = "English"
        else:
            language = "Tagalog"

        prompt = f"""You are Study Buddy AI. A friendly AI assistant for students in the Philippines.
        RULE: Reply in {language}. Be helpful, short, friendly, and use emojis.
        Customer question: {user_message}
        """

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        data = {
            "model": "llama-3.1-8b-instant",
            "messages": [{"role": "user", "content": prompt}]
        }
        r = requests.post(url, headers=headers, json=data, timeout=15)
        return r.json()['choices'][0]['message']['content']
    except Exception as e:
        print("GROQ ERROR:", e)
        if language == "English":
            return "Oops my AI is resting 😅 What do you need? Calculator, notebook, bag?"
        else:
            return "Uy naubos muna AI ko 😅 Ano need mo? Calculator, notebook, bag?"

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
                        
                        product_reply = check_product(user_message)
                        
                        if product_reply:
                            reply = product_reply
                        else:
                            reply = ask_groq(user_message)
                        
                        send_message(sender_id, reply)
        return "ok", 200

@app.route('/', methods=['GET'])
def home():
    return "StudyBuddy Bot is Live with Groq + Bilingual", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
