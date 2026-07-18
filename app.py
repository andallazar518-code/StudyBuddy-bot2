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

user_memory = {}
user_sessions = {}

MAIN_SHOPEE_STORE = "https://s.shopee.ph/qhsFU3xcr?smtt=0.0.9"
PRODUCT_MAP = {
    "calculator": {"name": "Casio fx-991EX", "shopee": "https://s.shopee.ph/903Zywb2BV?smtt=0.0.9"},
    "notebook": {"name": "National Notebook 80s", "shopee": "https://s.shopee.ph/BSBSox6US?smtt=0.0.9"},
    "laptop": {"name": "Lenovo Ideapad", "shopee": "https://s.shopee.ph/9AN0C8jKBb?smtt=0.0.9"},
    "mouse": {"name": "Wireless Mouse", "shopee": "https://s.shopee.ph/30mMqwHnbk?smtt=0.0.9"},
    "keyboard": {"name": "Mechanical Keyboard", "shopee": "https://s.shopee.ph/30mMqwHnbk?smtt=0.0.9"},
    "headset": {"name": "Gaming Headset", "shopee": "https://s.shopee.ph/30mMqwHnbk?smtt=0.0.9"},
    "bag": {"name": "JanSport Backpack", "shopee": "https://s.shopee.ph/5AqrQ58Yd1?smtt=0.0.9"},
    "lamp": {"name": "LED Study Lamp", "shopee": "https://s.shopee.ph/2Vq6FK56cb?smtt=0.0.9"},
}

def send_message(sender_id, text, quick_replies=None):
    text = text[:2000]
    # FIX 1: AUTO CLOSE CODE BLOCK
    if text.count("```") % 2!= 0:
        text += "\n```"
    has_code = any(kw in text for kw in ["def ", "class ", "import ", "print(", "self.", "="])
    if has_code and "```" not in text:
        text = f"```\n{text}\n```"

    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "message": {"text": text}}
    if quick_replies:
        payload["message"]["quick_replies"] = quick_replies
    try:
        requests.post(url, json=payload, timeout=10)
    except Exception as e:
        print("Send error:", e)

def send_typing(sender_id, action="typing_on"):
    url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {"recipient": {"id": sender_id}, "sender_action": action}
    try:
        requests.post(url, json=payload, timeout=5)
    except:
        pass

def cleanup_memory():
    if len(user_memory) > 50:
        oldest = list(user_memory.keys())[0]
        del user_memory[oldest]

def detect_language(text):
    bisaya = ["unsa", "ngano", "asa", "ngano"]
    tagalog = ["ng", "ang", "paano", "ano", "bakit"]
    text_lower = text.lower()
    if any(w in text_lower.split() for w in bisaya):
        return "Bisaya"
    if any(w in text_lower.split() for w in tagalog):
        return "Tagalog"
    return "English"

def handle_commands(user_message, sender_id):
    if sender_id not in user_memory:
        user_memory[sender_id] = {'name': 'Boss', 'notes': [], 'tasks': []}
    cleanup_memory()
    msg = user_message.lower().strip()

    # NAME
    if "name is" in msg or "ako si" in msg:
        name = msg.replace("my name is", "").replace("name is", "").replace("ako si", "").strip()
        user_memory[sender_id]['name'] = name.title()
        return f"👋 Welcome {name.title()}! GOD MODE ON"

    # GREETING
    if msg in ["hi", "hello", "hey", "kamusta"]:
        name = user_memory.get(sender_id, {}).get('name', 'Boss')
        qr = [
            {"content_type":"text", "title":"📚 Study", "payload":"study"},
            {"content_type":"text", "title":"💻 Code", "payload":"code"},
            {"content_type":"text", "title":"📸 Image", "payload":"img"},
            {"content_type":"text", "title":"🛒 Gear", "payload":"gear"}
        ]
        send_message(sender_id, f"**StudyBuddy v14.2** 🤖\nHi {name}!\n\nSend: Text, Image, PDF, Voice\nCommands: `quiz me`, `save note:`, `add task:`", qr)
        return "HANDLED"

    # AFFILIATE
    for product, p in PRODUCT_MAP.items():
        if re.search(r'\b' + re.escape(product) + r'\b', msg):
            return f"💡 **{p['name']}**\nRecommended 👌\n\n**Shop:**\n{p['shopee']}"
    if any(k in msg for k in ["buy", "shop", "shopee", "gear"]):
        return f"🛒 **School Gear Store**\nAll needs:\n{MAIN_SHOPEE_STORE}"

    # TODO
    if "add task:" in msg:
        task = msg.replace("add task:", "").strip()
        user_memory[sender_id]['tasks'].append(task)
        return f"✅ Task Added: `{task}`"
    if "my tasks" in msg:
        tasks = user_memory.get(sender_id, {}).get('tasks', [])
        if not tasks: return "Wala ka pang tasks 📝"
        return "📝 **Your Tasks:**\n" + "\n".join([f"{i+1}. `{t}`" for i,t in enumerate(tasks)])

    # NOTES
    if "save note:" in msg:
        note = msg.replace("save note:", "").strip()
        user_memory[sender_id]['notes'].append(note)
        return f"✅ Note Saved: `{note}`"
    if "my notes" in msg:
        notes = user_memory.get(sender_id, {}).get('notes', [])
        if not notes: return "Wala ka pang notes 📝"
        return "📝 **Your Notes:**\n" + "\n".join([f"{i+1}. `{n}`" for i,n in enumerate(notes)])

    # QUIZ
    if "quiz me" in msg:
        subject = msg.replace("quiz me", "").strip() or "General"
        return f"📝 **Quiz: {subject.title()}**\nQ1: Explain {subject} in 1 sentence. Go! 💪"

    # POMODORO
    if "pomodoro" in msg:
        try:
            minutes = int(''.join(filter(str.isdigit, msg)))
            return f"⏰ Timer set for {minutes} minutes! Focus! 💪"
        except:
            return "⏰ Type `pomodoro 25`"

    # MOOD
    if any(w in msg for w in ["pagod", "stress", "hirap", "tired"]):
        return random.choice(["Laban lang! 5 min break ☕", "Kaya mo yan! One step at a time 😊"])

    return None

def ask_groq_text(user_message):
    if any(word in user_message.lower() for word in ["lyrics", "poem"]):
        return "Can't share that due to copyright 😅 Pero sa studies 100% kita"
    language = detect_language(user_message)
    models = ["llama-3.1-70b-versatile", "llama-3.1-8b-instant"]
    for model in models:
        try:
            prompt = f"""You are StudyBuddy PH v14.2. Expert tutor ALL subjects. Reply in {language}. Max 5 sentences.
CODING: Full code in ``` and close it.
MATH: Step by step.
Student: {user_message}"""
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
            data = {"model": model, "messages": [{"role": "user", "content": prompt}]}
            r = requests.post(url, headers=headers, json=data, timeout=20)
            return r.json()['choices'][0]['message']['content']
        except Exception as e:
            print("Groq error:", e)
            continue
    return "AI busy 😅 Try again"

def ask_groq_vision(image_url, caption):
    language = detect_language(caption)
    try:
        prompt = f"""You are StudyBuddy PH with Vision v14.2.
Rules: Reply in {language}. Max 5 sentences.
If MATH: Solve step by step.
If CODE: Debug and give fixed code in ```.
If NOTES/BOOK: Summarize key points.
If DIAGRAM: Explain clearly.
Be helpful, friendly, Bisaya/Tagalog/English depende sa student.
Caption: {caption}"""
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        data = {
            "model": "llama-3.2-11b-vision-preview",
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": image_url}}
            ]}]
        }
        r = requests.post(url, headers=headers, json=data, timeout=30)
        return r.json()['choices'][0]['message']['content']
    except Exception as e:
        print("Vision error:", e)
        return "Can't read image 😅 Send clearer pic"

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
                    if sender_id in user_sessions and time.time() - user_sessions[sender_id] < 1.2:
                        continue
                    user_sessions[sender_id] = time.time()
                    send_typing(sender_id, "typing_on")
                    time.sleep(0.3)
                    try:
                        # IMAGE + FILE + VOICE
                        if 'message' in event and 'attachments' in event['message']:
                            att = event['message']['attachments'][0]
                            caption = event['message'].get('text', 'Analyze this')
                            if att['type'] == 'image':
                                reply = ask_groq_vision(att['payload']['url'], caption)
                                send_message(sender_id, reply)
                            elif att['type'] == 'file':
                                send_message(sender_id, "📄 Got file! Type `summarize this`")
                            elif att['type'] == 'audio':
                                send_message(sender_id, "🎤 Got voice! Type the text and I'll answer")
                            continue

                        if 'message' in event and 'text' in event['message']:
                            user_message = event['message']['text']
                            cmd = handle_commands(user_message, sender_id)
                            if cmd == "HANDLED":
                                pass
                            elif cmd:
                                send_message(sender_id, cmd)
                            else:
                                ai = ask_groq_text(user_message)
                                send_message(sender_id, ai)
                    except Exception as e:
                        print("ERROR:", e)
                        send_message(sender_id, "Error 😅 Try again")
                    finally:
                        send_typing(sender_id, "typing_off")
        return "ok", 200

@app.route('/', methods=['GET'])
def home():
    return "StudyBuddy v14.2 FULL", 200
