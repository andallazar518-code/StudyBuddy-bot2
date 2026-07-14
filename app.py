from flask import Flask, request
import requests
import os
import random

app = Flask(__name__)

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
VERIFY_TOKEN = "TUBO2026"
GENERIC_LINK_SHOPEE = "https://s.shopee.ph/qhsFU3xcr?smtt=0.0.9"

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
    requests.post(url, json={"recipient": {"id": sender_id}, "message": {"text": text[:2000]}})

def check_product(user_message):
    user_message = user_message.lower()
    for product, p in PRODUCT_MAP.items():
        if product in user_message:
            return f"💡 {p['name']}\nShopee: {p['shopee']}"
    return ""

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
                        print(f"Received: {user_message}") # = para makita sa logs
                        
                        product_reply = check_product(user_message)
                        
                        if product_reply:
                            reply = f"Naghahanap ka ba nito? \n{product_reply}"
                        elif "hi" in user_message.lower() or "hello" in user_message.lower():
                            reply = "Uy! Ako si Study Buddy AI 🤖\nNaubos muna AI ko for today 😅\nPero pwede kita tulungan maghanap ng gamit. Type: calculator, bag, laptop"
                        else:
                            reply = "Boss naubos muna AI credits ko today 😅\nPero sabihin mo lang kung anong gamit need mo, bibigyan kita Shopee link"
                        
                        send_message(sender_id, reply) # = ITO YUNG KULANG BOSS
        return "ok", 200

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
                            reply = f"Naghahanap ka ba nito? \n{product_reply}"
                        elif "hi" in user_message.lower() or "hello" in user_message.lower():
                            reply = "Uy! Ako si Study Buddy AI 🤖\nNaubos muna AI ko for today 😅\nPero pwede kita tulungan maghanap ng gamit. Type: calculator, bag, laptop"
                        else:
                            reply = "Boss naubos muna AI credits ko today 😅\nPero sabihin mo lang kung anong gamit need mo, bibigyan kita Shopee link"
                        
                        send_message(sender_id, reply)
        return "ok", 200

@app.route('/', methods=['GET'])
def home():
    return "StudyBuddy Bot is Live", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
