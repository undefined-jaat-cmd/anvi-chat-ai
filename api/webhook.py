
import os
import json
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

REDIS_URL = os.environ.get("UPSTASH_REDIS_REST_URL")
REDIS_TOKEN = os.environ.get("UPSTASH_REDIS_REST_TOKEN")

# IMPORTANT:
# Keep the exact API_URL from your currently working webhook.py.
API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-3.5-flash-lite:generateContent"
)

MAX_HISTORY = 20


# ---------------- REDIS MEMORY ----------------

def redis_command(*command):
    if not REDIS_URL or not REDIS_TOKEN:
        raise RuntimeError("Redis credentials missing")

    req = urllib.request.Request(
        REDIS_URL.rstrip("/"),
        data=json.dumps(list(command)).encode(),
        headers={
            "Authorization": f"Bearer {REDIS_TOKEN}",
            "Content-Type": "application/json"
        },
        method="POST"
    )

    with urllib.request.urlopen(req, timeout=15) as response:
        result = json.loads(response.read())

    if "error" in result:
        raise RuntimeError(result["error"])

    return result.get("result")


def get_history(chat_id):
    key = f"anvi:history:{chat_id}"
    data = redis_command("GET", key)

    if not data:
        return []

    return json.loads(data)


def save_history(chat_id, history):
    key = f"anvi:history:{chat_id}"

    redis_command(
        "SET",
        key,
        json.dumps(history, ensure_ascii=False)
    )


def clear_history(chat_id):
    redis_command("DEL", f"anvi:history:{chat_id}")


# ---------------- TELEGRAM ----------------

def telegram_request(method, payload):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read())


def send_message(chat_id, message):
    # Telegram text limit is 4096 characters.
    for i in range(0, len(message), 4000):
        telegram_request("sendMessage", {
            "chat_id": chat_id,
            "text": message[i:i + 4000]
        })


def send_typing(chat_id):
    telegram_request("sendChatAction", {
        "chat_id": chat_id,
        "action": "typing"
    })


# ---------------- GEMINI AI ----------------

def ask_gemini(history):
    payload = {
        "system_instruction": {
            "parts": [{
                "text": (
                    "You are ANVI Chat AI, a helpful conversational "
                    "assistant. Reply naturally. Use Hinglish when "
                    "the user uses Hinglish and English when they "
                    "use English. Remember the conversation context."
                )
            }]
        },
        "contents": history
    }

    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "x-goog-api-key": GEMINI_KEY
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=40) as response:
            result = json.loads(response.read())

        return result["candidates"][0]["content"]["parts"][0]["text"]

    except urllib.error.HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini HTTP {error.code}: {details}")


# ---------------- WEBHOOK ----------------

class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.respond(200, "ANVI Chat AI is running!")

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            update = json.loads(self.rfile.read(length))

            message = update.get("message", {})
            chat = message.get("chat", {})
            user_text = message.get("text", "")

            if not chat or not user_text:
                self.respond(200, "OK")
                return

            chat_id = chat["id"]
            command = user_text.split()[0].split("@")[0]

            if command == "/start":
                send_message(
                    chat_id,
                    "Hello! I am ANVI Chat AI.\n"
                    "I can remember our conversations.\n\n"
                    "Send me a message to start chatting!"
                )

            elif command == "/new":
                clear_history(chat_id)
                send_message(
                    chat_id,
                    "New conversation started! "
                    "Our previous chat history has been cleared."
                )

            else:
                send_typing(chat_id)

                history = get_history(chat_id)

                history.append({
                    "role": "user",
                    "parts": [{"text": user_text}]
                })

                reply = ask_gemini(history)

                history.append({
                    "role": "model",
                    "parts": [{"text": reply}]
                })

                history = history[-MAX_HISTORY:]

                save_history(chat_id, history)
                send_message(chat_id, reply)

        except Exception as error:
            print("ERROR:", str(error))

            try:
                if "chat_id" in locals():
                    send_message(
                        chat_id,
                        "Sorry, something went wrong. Please try again."
                    )
            except Exception as send_error:
                print("TELEGRAM ERROR:", str(send_error))

        self.respond(200, "OK")

    def respond(self, status, message):
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(message.encode())
