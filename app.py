import os
import json
import requests
from flask import Flask, request
from google import genai

app = Flask(__name__)

# KUNIN NATIN SA RENDER ENVIRONMENT
PAGE_ACCESS_TOKEN = os.getenv('PAGE_ACCESS_TOKEN')
VERIFY_TOKEN = "TUBO2026" 
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')

# BAGONG GEMINI CLIENT
client = genai.Client(api_key=GOOGLE_API_KEY)
model = "gemini-1.5-flash-8b-latest"

def send_message(recipient_id, message_text):
    """Para magreply sa Messenger"""
    url = "https://graph.facebook.com/v19.0/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    data = json.dumps({
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    })
    requests.post(url, params=params, headers=headers, data=data)

def get_ai_reply(user_message):
    """Para sumagot si Gemini AI"""
    prompt = f"Ikaw si Study Buddy AI. Turuan mo ng simple at maikli. Tagalog ka kung tagalog ang tanong. English kung english. Tanong: {user_message}"
    
    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt
        )
        return response.text
    except Exception as e:
        print(f"AI Error: {e}")
        return "Ay sorry, nagka-error si AI. Try mo ulit."

@app.route('/webhook', methods=['GET', 'POST'])
def webhook():
    if request.method == 'GET':
        # Para sa verification
        if request.args.get("hub.verify_token") == VERIFY_TOKEN:
            return request.args.get("hub.challenge")
        return "Verification token mismatch", 403

    if request.method == 'POST':
        data = request.get_json()
        
        if data.get("object") == "page":
            for entry in data.get("entry", []):
                for messaging_event in entry.get("messaging", []):
                    sender_id = messaging_event["sender"]["id"]
                    
                    if "message" in messaging_event:
                        user_msg = messaging_event["message"]["text"]
                        
                        # Tawagin si AI
                        ai_reply = get_ai_reply(user_msg)
                        
                        # Ireply sa user
                        send_message(sender_id, ai_reply)
                        
        return "ok", 200

if __name__ == "__main__":
    app.run()
