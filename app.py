import hashlib
import hmac
import json
import os
import random
import re
import threading
import time
from urllib.parse import quote
from flask import Flask, abort, request
import requests
from supabase import create_client

app = Flask(__name__)

PAGE_ACCESS_TOKEN = os.environ.get("PAGE_ACCESS_TOKEN")
GROQ_API_KEY_1 = os.environ.get("GROQ_API_KEY")
GROQ_API_KEY_2 = os.environ.get("GROQ_API_KEY_2") # Optional secondary key for multi-account limit balancing

if not PAGE_ACCESS_TOKEN or not GROQ_API_KEY_1:
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
SESSION_COOLDOWN = 3.0
last_request_times = {}

AFFILIATE_ID = "test123"
MAIN_SHOPEE_STORE = "https://s.shopee.ph/8fQz7TwnGa"

PRODUCT_MAP = {
    "calculator": {
        "name": "Casio fx-991EX Scientific Calculator",
        "shopee": "https://s.shopee.ph/903Zywb2BV",
        "hook": "Struggling with complex math? 📐",
        "benefit": "Approved for board exams. 552 functions",
    },
    "notebook": {
        "name": "Steno Notebook",
        "shopee": "https://s.shopee.ph/2g9lyGVq1j",
        "hook": "Ink keeps bleeding through? 📓",
        "benefit": "Thick 70gsm paper",
    },
    "laptop": {
        "name": "Recommended Laptop",
        "shopee": "https://s.shopee.ph/9AN0C8jKBb",
        "hook": "Need a laptop for school & work? 💻",
        "benefit": "Budget-friendly. Intel i7",
    },
    "mouse": {
        "name": "Wireless Silent Mouse",
        "shopee": "https://s.shopee.ph/AAFmtvFjIy",
        "hook": "Wrist pain from clicking? 🖱️",
        "benefit": "Ergonomic design. Silent click",
    },
    "keyboard": {
        "name": "RGB Mechanical Keyboard",
        "shopee": "https://s.shopee.ph/8rLmN2pQrs",
        "hook": "Want faster typing? ⌨️",
        "benefit": "Blue switches. Plug and play",
    },
    "headset": {
        "name": "Gaming Headset with Noise Cancelling Mic",
        "shopee": "https://s.shopee.ph/1LeONYhvY0",
        "hook": "Can't hear clearly in online class? 🎧",
        "benefit": "Crystal clear mic",
    },
    "bag": {
        "name": "JanSport SuperBreak Backpack",
        "shopee": "https://s.shopee.ph/5AqrQ58Yd1",
        "hook": "Bag keeps getting wet? 🎒",
        "benefit": "Water resistant. 15L capacity",
    },
    "lamp": {
        "name": "LED Desk Study Lamp with USB",
        "shopee": "https://s.shopee.ph/2Vq6FK56cb",
        "hook": "Eyes getting tired at night? 💡",
        "benefit": "3 light modes. Eye protection",
    },
}


def get_tracked_link(base_url, sender_id, product="store"):
  return base_url.strip()


def get_dynamic_shopee_search_link(user_message, sender_id):
  stop_words = ["nag", "hahanap", "ako", "ng", "gusto", "kong", "bumili", "meron", "ka", "bang", "mga", "search", "sa", "po", "ba", "yung"]
  words = user_message.lower().split()
  filtered_words = [w for w in words if w not in stop_words]
  
  query = " ".join(filtered_words) if filtered_words else user_message
  formatted_query = quote(query.strip())
  
  base_search_url = f"{MAIN_SHOPEE_STORE}?keyword={formatted_query}"
  return base_search_url


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


def send_typing_indicator(sender_id, action="typing_on"):
  if not PAGE_ACCESS_TOKEN:
    return
  url = f"https://graph.facebook.com/v19.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
  payload = {"recipient": {"id": sender_id}, "sender_action": action}
  try:
    requests.post(url, json=payload, timeout=5)
  except requests.exceptions.RequestException:
    pass


def send_message(sender_id, text, quick_replies=None):
  if not PAGE_ACCESS_TOKEN:
    return
  send_typing_indicator(sender_id, "typing_off")
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
  send_typing_indicator(sender_id, "typing_off")
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
  attempts_plan = [
      {"model": "llama-3.3-70b-versatile", "key": GROQ_API_KEY_1},
      {"model": "llama-3.1-8b-instant", "key": GROQ_API_KEY_1},
  ]
  
  if GROQ_API_KEY_2:
    attempts_plan.append({"model": "llama-3.3-70b-versatile", "key": GROQ_API_KEY_2})
    attempts_plan.append({"model": "llama-3.1-8b-instant", "key": GROQ_API_KEY_2})

  for plan in attempts_plan:
    if not plan["key"]:
      continue
      
    headers = {
        "Authorization": f"Bearer {plan['key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": plan["model"],
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 300,
    }
    
    for attempt in range(2):
      try:
        res = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            json=payload,
            headers=headers,
            timeout=12,
        )
        if res.status_code == 200:
          return res.json()["choices"][0]["message"]["content"]
        elif res.status_code == 429:
          print(f"Rate limited (429) on {plan['model']}. Retrying...")
          time.sleep(1.5)
          continue
        else:
          break
      except requests.exceptions.RequestException as e:
        print(f"GROQ API ERROR on {plan['model']}:", e)
        time.sleep(1)

  return (
      "I'm having a little trouble thinking right now. Please try again in a"
      " moment! 😅"
  )


def handle_incoming_message(sender_id, text, quick_reply_payload=None, qr_text=""):
  send_typing_indicator(sender_id, "typing_on")
  
  last_time = last_request_times.get(sender_id, 0)
  if time.time() - last_time < SESSION_COOLDOWN:
    send_typing_indicator(sender_id, "typing_off")
    return
  last_request_times[sender_id] = time.time()

  user = get_user(sender_id)
  text_lower = text.strip().lower()
  qr_text_lower = qr_text.strip().lower()

  standard_quick_replies = [
      {"content_type": "text", "title": "🛒 Shop", "payload": "shop"},
      {"content_type": "text", "title": "🧠 Clear Memory", "payload": "clear_memory"},
  ]
  
  welcome_quick_replies = [
      {"content_type": "text", "title": "🛒 Shop", "payload": "shop"},
      {"content_type": "text", "title": "📝 Set Name", "payload": "set_name"},
      {"content_type": "text", "title": "🧠 Clear Memory", "payload": "clear_memory"},
  ]

  effective_payload = quick_reply_payload
  if not effective_payload:
    combined_check = f"{text_lower} {qr_text_lower}"
    if "shop" in combined_check:
      effective_payload = "shop"
    elif "set name" in combined_check or "set_name" in combined_check:
      effective_payload = "set_name"
    elif "clear memory" in combined_check or "clear_memory" in combined_check:
      effective_payload = "clear_memory"
    elif "help" in combined_check:
      effective_payload = "help"

  if effective_payload:
    handle_postback(sender_id, effective_payload)
    return

  current_qr = welcome_quick_replies if not user.get("name") else standard_quick_replies

  if user.get("waiting_for_name"):
    update_user(
        sender_id, {"name": text.strip(), "waiting_for_name": False}
    )
    send_message(
        sender_id,
        f"Alright, {text.strip()}! 🙋‍♀️ Your name has been updated. 😊 How are you? What are your plans for today?",
        quick_replies=standard_quick_replies,
    )
    return

  if text_lower in ["hi", "hello", "start"]:
    name = user.get("name") or "there"
    send_message(
        sender_id,
        f"Hello {name}! 👋\n\n📚 Need school supplies? I have vouchers.\n\nWant it?",
        quick_replies=current_qr,
    )
    return

  # --- SMART PRODUCT / ITEM FINDER LOGIC ---
  matched_product = None
  for key, prod in PRODUCT_MAP.items():
    if key in text_lower or any(word in text_lower for word in prod["name"].lower().split()):
      matched_product = (key, prod)
      break

  chat_count = user.get("chat_count", 0) + 1
  history = user.get("conversation_history", [])
  history.append({"role": "user", "content": text})

  system_prompt = {
      "role": "system",
      "content": (
          "You are StudyBuddy PH, a helpful student assistant chatbot in the"
          f" Philippines. The user's name is {user.get('name', 'Friend')}."
          " Respond concisely, friendly, and helpfully in English."
      ),
  }

  # --- QUICK MATH INTERCEPTOR ---
  math_match = re.search(r"(\d+)\s*[\*xX]\s*(\d+)", text)
  if math_match:
    num1 = int(math_match.group(1))
    num2 = int(math_match.group(2))
    exact_result = num1 * num2
    bot_reply = f"{text.strip()} = {exact_result:,}"
  else:
    ai_messages = [system_prompt] + history[-10:]
    bot_reply = call_groq_api(ai_messages)

  if matched_product:
    pkey, pval = matched_product
    tracked_url = get_tracked_link(pval["shopee"], sender_id, pkey)
    bot_reply += (
        f"\n\n🔍 Speaking of that, I found this for you:\n"
        f"📦 **{pval['name']}**\n"
        f"✨ {pval['benefit']}!\n"
        f"👉 Check it here: {tracked_url}"
    )
  elif any(word in text_lower for word in ["buy", "search", "magkano", "price", "kano", "hanap", "pwede", "meron", "shop", "order"]):
    search_tracked_url = get_dynamic_shopee_search_link(text, sender_id)
    bot_reply += (
        f"\n\n🔍 I couldn't find that exact item in our featured list, but you can search and check it here with our vouchers:\n"
        f"👉 {search_tracked_url}"
    )
  elif chat_count % 4 == 0:
    prod_key = random.choice(list(PRODUCT_MAP.keys()))
    prod = PRODUCT_MAP[prod_key]
    tracked_url = get_tracked_link(prod["shopee"], sender_id, prod_key)
    bot_reply += (
        f"\n\n💡 {prod['hook']}\n{prod['benefit']}!\nCheck it out here:"
        f" {tracked_url}"
    )

  history.append({"role": "assistant", "content": bot_reply})
  update_user(sender_id, {"conversation_history": history, "chat_count": chat_count})
  
  send_message(
      sender_id,
      bot_reply,
      quick_replies=current_qr,
  )


def handle_postback(sender_id, payload):
  send_typing_indicator(sender_id, "typing_on")
  user = get_user(sender_id)
  
  standard_quick_replies = [
      {"content_type": "text", "title": "🛒 Shop", "payload": "shop"},
      {"content_type": "text", "title": "🧠 Clear Memory", "payload": "clear_memory"},
  ]
  
  welcome_quick_replies = [
      {"content_type": "text", "title": "🛒 Shop", "payload": "shop"},
      {"content_type": "text", "title": "📝 Set Name", "payload": "set_name"},
      {"content_type": "text", "title": "🧠 Clear Memory", "payload": "clear_memory"},
  ]

  current_qr = welcome_quick_replies if not user.get("name") else standard_quick_replies

  if payload == "shop":
    tracked_store_url = get_tracked_link(MAIN_SHOPEE_STORE, sender_id, "main_store")
    shop_message = (
            f"Hi! 🛍️ **Welcome to StudyBuddy Shop**\n\n"
            f"Browse ka lang dito ng mga gamit sa school. May discount codes din kami!\n\n"
            f"👉 {tracked_store_url}\n\n"
            f"*Support our page by shopping through this link. Thank you!*"
        )
    send_message(
        sender_id,
        shop_message,
        quick_replies=current_qr,
    )
  elif payload == "set_name":
    update_user(sender_id, {"waiting_for_name": True})
    send_message(
        sender_id,
        "Alright! What is your new name? Just type it here. 📝💬",
        quick_replies=standard_quick_replies,
    )
  elif payload == "clear_memory":
    update_user(sender_id, {"conversation_history": [], "chat_count": 0, "name": None, "waiting_for_name": False})
    send_message(
        sender_id,
        "🧠 I have cleared our memory. Let's start fresh!",
        quick_replies=welcome_quick_replies,
    )
  elif payload == "help":
    send_message(
        sender_id,
        "You can ask me questions about your studies, or click Shop for school supplies.",
        quick_replies=current_qr,
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
              msg = messaging["message"]
              text = msg.get("text", "")
              qr_payload = messaging.get("message", {}).get("quick_reply", {}).get("payload")
              qr_text = msg.get("text", "") if qr_payload else ""
              if text or qr_payload:
                threading.Thread(
                    target=handle_incoming_message,
                    args=(sender_id, text, qr_payload, qr_text)
                ).start()
            elif messaging.get("postback"):
              payload = messaging["postback"].get("payload")
              if payload:
                threading.Thread(
                    target=handle_postback,
                    args=(sender_id, payload)
                ).start()
      except Exception as e:
        print("WEBHOOK PROCESSING ERROR:", e)

      return "EVENT_RECEIVED", 200
    return abort(404)


if __name__ == "__main__":
  setup_menu()
  app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
