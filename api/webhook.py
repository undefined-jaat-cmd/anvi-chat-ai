
import os
import json
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-3.5-flash-lite:generateContent"
)

def send_message(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message
    }).encode()

    req = urllib.request.Request(url, data=data)
    urllib.request.urlopen(req, timeout=20)


import urllib.error

def ask_gemini(message):
    payload = {
        "system_instruction": {
            "parts": [{
                "text": "You are ANVI Chat AI. Reply naturally in Hinglish or English."
            }]
        },
        "contents": [{
            "parts": [{"text": message}]
        }]
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
        raise RuntimeError(
            f"Gemini HTTP {error.code}: {details}"
        )

class handler(BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            update = json.loads(self.rfile.read(length))

            message = update.get("message", {})
            chat = message.get("chat", {})
            text = message.get("text", "")

            if not chat or not text:
                self.respond(200, "OK")
                return

            chat_id = chat["id"]

            if text == "/start":
                reply = "Hello! I am ANVI Chat AI. Send me a message!"
            elif text == "/new":
                reply = "New chat started! What shall we discuss?"
            else:
                reply = ask_gemini(text)

            send_message(chat_id, reply)

        except Exception as error:
            print("ERROR:", error)

        self.respond(200, "OK")

    def do_GET(self):
        self.respond(200, "ANVI Chat AI is running!")

    def respond(self, status, message):
        self.send_response(status)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(message.encode())