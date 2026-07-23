import hashlib
import hmac
import json
import os
import random
import re
import threading
import time
from flask import Flask, abort, request
import requests
from supabase import create_client

app = Flask(__name__)

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

if not PAGE_ACCESS_TOKEN or not GROQ_API_KEY:
  raise ValueError("Missing PAGE_ACCESS_TOKEN or GROQ_API_KEY")

VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "TUBO2026")
APP_SECRET = os.environ.get("FB_APP_SECRET")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

supabase = (
    create_client(SUPABASE_URL, SUPABASE_KEY)
    if SUPABASE_URL and SUPABASE_KEY
    else None
)
user_sessions = {}
SESSION_COOLDOWN = 1.2
AFFILIATE_ID = "studybuddy"
MAIN_SHOPEE_STORE = "https://s.shopee.ph/qhsFU3xcr?smtt=0.0.9"

PRODUCT_MAP = {
    "calculator": {
        "name": "Casio fx-991EX Scientific Calculator",
        "shopee": "https://s.shopee.ph/903Zywb2BV?smtt=0.0.9",
        "hook": "Struggling with complex math? 📐",
        "benefit": "Approved for board exams. 552 functions",
    },
    "notebook": {
        "name": "National Notebook 80 Leaves",
        "shopee": "https://s.shopee.ph/BSBSox6US?smtt=0.0.9",
        "hook": "Ink keeps bleeding through? 📓",
        "benefit": "Thick 70gsm paper",
    },
    "laptop": {
        "name": "Lenovo Ideapad 3 Laptop",
        "shopee": "https://s.shopee.ph/9AN0C8jKBb?smtt=0.0.9",
        "hook": "Need a laptop for school & work? 💻",
        "benefit": "Budget-friendly. Intel i3",
    },
    "mouse": {
        "name": "Wireless Silent Mouse",
        "shopee": "https://s.shopee.ph/7pKqL9xAbc?smtt=0.0.9",
        "hook": "Wrist pain from clicking? 🖱️",
        "benefit": "Ergonomic design. Silent click",
    },
    "keyboard": {
        "name": "RGB Mechanical Keyboard",
        "shopee": "https://s.shopee.ph/8rLmN2pQrs?smtt=0.0.9",
        "hook": "Want faster typing? ⌨️",
        "benefit": "Blue switches. Plug and play",
    },
    "headset": {
        "name": "Gaming Headset with Noise Cancelling Mic",
        "shopee": "https://s.shopee.ph/4wZxY6vTuv?smtt=0.0.9",
        "hook": "Can't hear clearly in online class? 🎧",
        "benefit": "Crystal clear mic",
    },
    "bag": {
        "name": "JanSport SuperBreak Backpack",
        "shopee": "https://s.shopee.ph/5AqrQ58Yd1?smtt=0.0.9",
        "hook": "Bag keeps getting wet? 🎒",
        "benefit": "Water resistant. 15L capacity",
    },
    "lamp": {
        "name": "LED Desk Study Lamp with USB",
        "shopee": "https://s.shopee.ph/2Vq6FK56cb?smtt=0.0.9",
        "hook": "Eyes getting tired at night? 💡",
        "benefit": "3 light modes. Eye protection",
    },
}


def get_tracked_link(base_url, sender_id, product="store"):
  tracker = f"aff_id={AFFILIATE_ID}_{sender_id}_{product}"
  return f"{base_url}&{tracker}" if "?" in base_url else f"{base_url}?{tracker}"


def setup_menu():
  if not PAGE_ACCESS_TOKEN:
    return
  url = f"https://graph.facebook.com/v19.0/me/messenger_profile?access_token={PAGE_ACCESS_TOKEN}"
  payload = {
      "persistent_menu": [{
          "locale": "default",
          "composer_input_disabled": False,
          "call_to_actions": [
              {"type": "postback", "title": "🛒 Shop", "payload": "shop"},
              {
                  "type": "postback",
                  "title": "🧠 Clear Memory",
                  "payload": "clear_memory",
              },
              {"type": "postback", "title": "❓ Help", "payload": "help"},
          ],
      }]
  }
  try:
    requests.post(url, json=payload, timeout=10)
  except requests.exceptions.RequestException:
    pass


def verify_signature(req):
  if not APP_SECRET:
    return True
  signature = req.headers.get("X-Hub-Signature-256", "")
  if not signature:
    return False
  hash_val = (
      hmac.new(APP_SECRET.encode("utf-8"), req.data, hashlib.sha256)
      .hexdigest()
  )
  return hmac.compare_digest(f"sha256={hash_val}", signature)


def get_fb_name(sender_id):
  if not PAGE_ACCESS_TOKEN:
    return None
  try:
    url = f"https://graph.facebook.com/v19.0/{sender_id}?fields=first_name&access_token={PAGE_ACCESS_TOKEN}"
    r = requests.get(url, timeout=5)
    if r.status_code == 200:
      return r.json().get("first_name")
  except requests.exceptions.RequestException as e:
    print(f"FB NAME ERROR for {sender_id}:", e)
  return None


def _load_history(raw):
  if not raw:
    return []
  if isinstance(raw, list):
    return raw
  try:
    return json.loads(raw)
  except Exception:
    return []


def _dump_history(hist):
  trimmed = []
  for m in hist[-10:]:
    m_copy = {
        "role": m.get("role", "user"),
        "content": str(m.get("content", ""))[:500],
    }
    trimmed.append(m_copy)
  return json.dumps(trimmed)


def get_user(sender_id):
  default = {
      "sender_id": sender_id,
      "name": None,
      "chat_count": 0,
      "rejected_affiliate": False,
      "reject_time": None,
      "auto_sent": False,
      "last_promo_time": None,
      "waiting_for_name": False,
      "conversation_history": [],
      "last_interest": None,
      "last_bot_action": None,
  }
  if not supabase:
    return default
  try:
    data = (
        supabase.table("users").select("*").eq("sender_id", sender_id).execute()
    )
    if data and getattr(data, "data", None):
      user = data.data[0]
      user["conversation_history"] = _load_history(
          user.get("conversation_history")
      )
      if not user.get("name"):
        fb_name = get_fb_name(sender_id)
        if fb_name:
          update_user(sender_id, {"name": fb_name})
          user["name"] = fb_name
      return user
    else:
      fb_name = get_fb_name(sender_id)
      new_user = default.copy()
      new_user.update({"name": fb_name})
      supabase.table("users").upsert(
          {**new_user, "conversation_history": _dump_history([])},
          on_conflict="sender_id",
      ).execute()
      return new_user
  except Exception as e:
    print(f"DB GET ERROR for {sender_id}:", e)
    return default


def update_user(sender_id, updates):
  if not supabase:
    return
  if "conversation_history" in updates:
    updates["conversation_history"] = _dump_history(
        updates["conversation_history"]
    )
  try:
    supabase.table("users").update(updates).eq("sender_id", sender_id).execute()
  except Exception as e:
    print(f"DB UPDATE ERROR for {sender_id}:", e)


def send_message(sender_id, text, quick_replies=None):
  if not PAGE_ACCESS_TOKEN:
    return
  text = str(text)[:2000]
  url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
  payload = {"recipient": {"id": sender_id}, "message": {"text": text}}
  if quick_replies:
    payload["message"]["quick_replies"] = quick_replies
  try:
    requests.post(url, json=payload, timeout=10)
  except requests.exceptions.RequestException as e:
    print(f"Send error for {sender_id}:", e)


def send_button_template(sender_id, text, buttons):
  if not PAGE_ACCESS_TOKEN:
    return
  url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
  payload = {
      "recipient": {"id": sender_id},
      "message": {
          "attachment": {
              "type": "template",
              "payload": {
                  "template_type": "button",
                  "text": text[:640],
                  "buttons": buttons,
              },
          }
      },
  }
  try:
    requests.post(url, json=payload, timeout=10)
  except requests.exceptions.RequestException as e:
    print(f"Button send error:", e)


def call_groq_api(messages):
  headers = {
      "Authorization": f"Bearer {GROQ_API_KEY}",
      "Content-Type": "application/json",
  }
  payload = {
      "model": "llama-3.3-70b-versatile",
      "messages": messages,
      "temperature": 0.7,
      "max_tokens": 500,
  }
  try:
    res = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        json=payload,
        headers=headers,
        timeout=12,
    )
    if res.status_code == 200:
      return res.json()["choices"][0]["message"]["content"]
  except requests.exceptions.RequestException as e:
    print("GROQ API ERROR:", e)
  return (
      "I'm having a little trouble thinking right now. Please try again in a"
      " moment! 😅"
  )


def handle_incoming_message(sender_id, text):
  user = get_user(sender_id)
  text_lower = text.strip().lower()

  standard_quick_replies = [
      {"content_type": "text", "title": "🛒 Shop", "payload": "shop"},
      {"content_type": "text", "title": "🧠 Clear Memory", "payload": "clear_memory"},
  ]
  
  welcome_quick_replies = [
      {"content_type": "text", "title": "🛒 Shop", "payload": "shop"},
      {"content_type": "text", "title": "📝 Set Name", "payload": "set_name"},
      {"content_type": "text", "title": "🧠 Clear Memory", "payload": "clear_memory"},
  ]

  if user.get("waiting_for_name"):
    update_user(
        sender_id, {"name": text.strip(), "waiting_for_name": False}
    )
    send_message(
        sender_id,
        f"Sige, {text.strip()}! 🙋‍♀️ Na-update na ang name mo. 😊 Kamusta? Anong plano mo ngayon?",
        quick_replies=standard_quick_replies,
    )
    return

  # Kapag bagong salta o nag-hi/hello, isasama ang Set Name
  if text_lower in ["hi", "hello", "start"]:
    name = user.get("name") or "there"
    send_message(
        sender_id,
        f"Hello {name}! 👋\n\n📚 Need school supplies? I have vouchers.\n\nWant it?",
        quick_replies=welcome_quick_replies,
    )
    return

  chat_count = user.get("chat_count", 0) + 1
  history = user.get("conversation_history", [])
  history.append({"role": "user", "content": text})

  system_prompt = {
      "role": "system",
      "content": (
          "You are StudyBuddy PH, a helpful student assistant chatbot in the"
          f" Philippines. The user's name is {user.get('name', 'Friend')}."
          " Respond concisely, friendly, and helpfully."
      ),
  }

  ai_messages = [system_prompt] + history[-10:]
  bot_reply = call_groq_api(ai_messages)

  history.append({"role": "assistant", "content": bot_reply})
  
  if chat_count % 8 == 0:
    prod_key = random.choice(list(PRODUCT_MAP.keys()))
    prod = PRODUCT_MAP[prod_key]
    tracked_url = get_tracked_link(prod["shopee"], sender_id, prod_key)
    bot_reply += (
        f"\n\n💡 {prod['hook']}\n{prod['benefit']}!\nCheck it out here:"
        f" {tracked_url}"
    )

  update_user(sender_id, {"conversation_history": history, "chat_count": chat_count})
  
  # Regular chat responses ay Shop at Clear Memory na lang (standard)
  send_message(
      sender_id,
      bot_reply,
      quick_replies=standard_quick_replies,
  )


def handle_postback(sender_id, payload):
  standard_quick_replies = [
      {"content_type": "text", "title": "🛒 Shop", "payload": "shop"},
      {"content_type": "text", "title": "🧠 Clear Memory", "payload": "clear_memory"},
  ]
  
  welcome_quick_replies = [
      {"content_type": "text", "title": "🛒 Shop", "payload": "shop"},
      {"content_type": "text", "title": "📝 Set Name", "payload": "set_name"},
      {"content_type": "text", "title": "🧠 Clear Memory", "payload": "clear_memory"},
  ]

  if payload == "shop":
    tracked_store_url = get_tracked_link(MAIN_SHOPEE_STORE, sender_id, "main_store")
    send_message(
        sender_id,
        "Check out our main store and vouchers here:"
        f" {tracked_store_url}",
        quick_replies=standard_quick_replies,
    )
  elif payload == "set_name":
    update_user(sender_id, {"waiting_for_name": True})
    send_message(
        sender_id,
        "Sige! Anong bagong name mo? I-type mo lang dito. 📝💬",
        quick_replies=standard_quick_replies,
    )
  elif payload == "clear_memory":
    update_user(sender_id, {"conversation_history": [], "chat_count": 0})
    # Pagkatapos mag-Clear Memory, isasama ang Set Name sa quick replies
    send_message(
        sender_id,
        "🧠 Na-clear ko na ang memory natin. Fresh start na tayo!",
        quick_replies=welcome_quick_replies,
    )
  elif payload == "help":
    send_message(
        sender_id,
        "Puwede mo akong tanungin tungkol sa pag-aaral, o i-click ang Shop para sa mga school supplies.",
        quick_replies=standard_quick_replies,
    )


@app.route("/", methods=["GET"])
def home():
  return "Bot is running!", 200


@app.route("/webhook", methods=["GET", "POST"])
def webhook():
  if request.method == "GET":
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
      return challenge, 200
    return abort(403)

  if request.method == "POST":
    if not verify_signature(request):
      return abort(403)
    data = request.get_json()
    if data.get("object") == "page":
      try:
        for entry in data.get("entry", []):
          for messaging in entry.get("messaging", []):
            sender_id = messaging.get("sender", {}).get("id")
            if messaging.get("message"):
              text = messaging["message"].get("text", "")
              if text:
                handle_incoming_message(sender_id, text)
            elif messaging.get("postback"):
              payload = messaging["postback"].get("payload")
              if payload:
                handle_postback(sender_id, payload)
      except Exception as e:
        print("WEBHOOK PROCESSING ERROR:", e)

      return "EVENT_RECEIVED", 200
    return abort(404)


if __name__ == "__main__":
  setup_menu()
  app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
