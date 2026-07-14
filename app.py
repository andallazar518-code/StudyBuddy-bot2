from flask import Flask, request
import requests
import os
import time
import urllib.parse

app = Flask(__name__)

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
VERIFY_TOKEN = "TUBO2026"

# = ITO PALITAN MO NG DOMAIN MO
YOUR_WEBSITE = "https://bit.ly/4fdUCot" # = Gawa tayo ng redirect page dito

PRODUCT_MAP = {
    "calculator": {"name": "Casio fx-991EX", "shopee": "https://shopee.ph/Casio-fx-991EX?smtt=0.0.9"},
    "notebook": {"name": "National Notebook 80s", "shopee": "https://shopee.ph/National-Notebook?smtt=0.0.9"},
    "bag": {"name": "JanSport Backpack", "shopee": "https://shopee.ph/JanSport-Bag?smtt=0.0.9"},
}

def send_message(sender_id, text):
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "message": {"text": text[:2000]}}
    requests.post(url, json=payload)

def send_typing(sender_id, action="typing_on"):
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "sender_action": action}
    requests.post(url, json=payload)

def get_safe_shopee_link(query):
    # = HINDI NA DIRECT SA SHOPEE. SA WEBSITE MO MUNA
    search_query = urllib.parse.quote_plus(query)
    return f"{YOUR_WEBSITE}/go?item={search_query}"

def check_product(user_message):
    user_message_lower = user_message.lower()
    found_products = []
    
    for product, p in PRODUCT_MAP.items():
        if product in user_message_lower:
            found_products.append(p)
    
    if found_products:
        reply = ""
        for p in found_products:
            if any(word in user_message_lower for word in ["what", "how", "where", "can", "is", "do", "help"]):
                reply += f"💡 I recommend this: \n{p['name']}\nShop here: {p['shopee']}\n\n"
            else:
                reply += f"💡 Eto ma-recommend ko: \n{p['name']}\nShop here: {p['shopee']}\n\n"
        return reply.strip()
    
    else:
        safe_link = get_safe_shopee_link(user_message)
        if any(word in user_message_lower for word in ["what", "how", "where", "can", "is", "do", "help"]):
            return f"🔍 I couldn't find that exact item. \nBut you can browse it here safely:\n{ safe_link }"
        else:
            return f"🔍 Hindi ko nahanap yung exact na item. \nPero pwede mo icheck dito ng safe:\n{ safe_link }"

def ask_groq(user_message):
    language = "Tagalog"
    try:
        if any(word in user_message.lower() for word in ["what", "how", "where", "can", "is", "do", "help"]):
            language = "English"

        prompt = f"""You are Study Buddy AI. A friendly AI assistant for students in the Philippines selling school supplies.
        RULE: Reply in {language}. Be helpful, short, friendly, and use emojis. Max 2 sentences.
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
                                reply = ask_groq(user_message)
                        finally:
                            send_typing(sender_id, "typing_off")
                        
                        send_message(sender_id, reply)
        return "ok", 200

@app.route('/', methods=['GET'])
def home():
    return "StudyBuddy Bot v4.0 Anti-Ban", 200

@app.route('/go', methods=['GET']) # = DAGDAG TO PARA SA REDIRECT
def go():
    item = request.args.get('item', '')
    shopee_url = f"https://shopee.ph/search?keyword={urllib.parse.quote_plus(item)}"
    return f'<script>window.location.href="{shopee_url}";</script>', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
