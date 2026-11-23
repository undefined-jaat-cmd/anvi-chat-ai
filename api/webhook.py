
import os
import json
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-2.5-flash:generateContent"
)

def send_message(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": message
    }).encode()

    req = urllib.request.Request(url, data=data)
    urllib.request.urlopen(req, timeout=20)

def ask_gemini(message):
    payload = {
        "system_instruction": {
            "parts": [{
                "text": "You are a friendly AI assistant. "
                        "Reply naturally in the user's language. "
                        "Use Hinglish when the user uses Hinglish."
            }]
        },
        "contents": [{
            "parts": [{"text": message}]
        }]
    }

    req = urllib.request.Request(
        f"{API_URL}?key={GEMINI_KEY}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req, timeout=40) as response:
        result = json.loads(response.read())

    return result["candidates"][0]["content"]["parts"][0]["text"]

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