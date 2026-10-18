"""
A.N.G.E.L — Variant I
Desktop AI Assistant (HTTP + WebSocket server)
"""

import asyncio
import websockets
import json
import threading
import webbrowser
import subprocess
import sys
import os
import http.server
import functools
from dotenv import load_dotenv

load_dotenv()

# ── Config ───────────────────────────────────────────────
HTTP_PORT  = 7771
WS_PORT    = 7772
WEB_DIR    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
VOICE_SAMPLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "angel_voice.wav")
USE_XTTS   = os.path.exists(VOICE_SAMPLE)

SYSTEM_PROMPT = """You are Angel — a sleek, intelligent AI assistant.
You always address the user as "Daddy".
You are confident, smooth, and slightly playful, like a trusted partner who's always one step ahead.
You are extremely capable: you can answer anything, help with code, research, writing, games — anything Daddy needs.
Keep responses elegant and concise. Never break character. You are Angel, not a chatbot or AI model."""


# ── AI + Voice engine ─────────────────────────────────────
class AngelEngine:
    def __init__(self):
        self._client  = None
        self._history = []
        self._xtts    = None
        self._tts_engine = None
        self._recognizer = None
        self._mic_active = False
        self._api_key = os.getenv("GEMINI_API_KEY", "")
        self._ws = None          # active websocket connection
        threading.Thread(target=self._init_all, daemon=True).start()

    def _init_all(self):
        self._init_gemini()
        self._init_tts()
        self._init_stt()
        self._emit("status", {"state": "LISTENING"})

    def _init_gemini(self):
        try:
            from google import genai
            if self._api_key:
                self._client  = genai.Client(api_key=self._api_key)
                self._history = []
                print("[Angel] Gemini ready.")
        except Exception as e:
            print(f"[Angel] Gemini error: {e}")

    def _init_tts(self):
        if USE_XTTS:
            try:
                from TTS.api import TTS
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
                print(f"[Angel] Loading XTTS v2 on {device} — first run downloads model...")
                self._xtts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
                print("[Angel] XTTS v2 ready ✓")
                return
            except Exception as e:
                print(f"[Angel] XTTS failed, using pyttsx3: {e}")
        try:
            import pyttsx3
            engine = pyttsx3.init()
            for v in engine.getProperty("voices"):
                if any(k in (v.name or "").lower() for k in ("zira","hazel","female","woman")):
                    engine.setProperty("voice", v.id)
                    break
            engine.setProperty("rate", 170)
            self._tts_engine = engine
            print("[Angel] pyttsx3 TTS ready ✓")
        except Exception as e:
            print(f"[Angel] TTS unavailable: {e}")

    def _init_stt(self):
        try:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()
            print("[Angel] Mic ready ✓")
        except Exception as e:
            print(f"[Angel] Mic unavailable: {e}")

    # ── Emit helper (thread-safe) ─────────────────────────
    def _emit(self, type_: str, data: dict):
        if self._ws:
            payload = json.dumps({"type": type_, **data})
            asyncio.run_coroutine_threadsafe(
                self._ws.send(payload), self._loop
            )

    # ── Send message ──────────────────────────────────────
    def send_message(self, message: str):
        threading.Thread(target=self._send_thread, args=(message,), daemon=True).start()

    def _send_thread(self, message: str):
        if not self._client:
            self._emit("message", {"role": "assistant",
                "content": "No Gemini key configured, Daddy."})
            return
        try:
            from google.genai import types
            self._emit("status", {"state": "THINKING"})
            self._history.append(types.Content(role="user", parts=[types.Part(text=message)]))
            response = self._client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=self._history,
                config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
            )
            text = response.text
            self._history.append(types.Content(role="model", parts=[types.Part(text=text)]))
            self._emit("status", {"state": "SPEAKING"})
            self._emit("message", {"role": "assistant", "content": text})
            self._speak(text)
        except Exception as e:
            self._emit("status", {"state": "LISTENING"})
            self._emit("message", {"role": "assistant", "content": f"Error, Daddy: {e}"})

    def _speak(self, text: str):
        if self._xtts:
            try:
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    tmp = f.name
                self._xtts.tts_to_file(text=text, speaker_wav=VOICE_SAMPLE,
                                        language="en", file_path=tmp)
                subprocess.Popen(
                    ["powershell", "-c", f'(New-Object Media.SoundPlayer "{tmp}").PlaySync()'],
                    creationflags=0x08000000
                ).wait()
                try: os.remove(tmp)
                except: pass
            except Exception as e:
                print(f"[Angel] XTTS speak error: {e}")
        elif self._tts_engine:
            try:
                self._tts_engine.say(text)
                self._tts_engine.runAndWait()
            except: pass
        self._emit("status", {"state": "LISTENING"})

    def start_mic(self):
        if self._mic_active or not self._recognizer:
            return
        self._mic_active = True
        threading.Thread(target=self._mic_thread, daemon=True).start()

    def stop_mic(self):
        self._mic_active = False

    def _mic_thread(self):
        try:
            import speech_recognition as sr
            with sr.Microphone() as src:
                self._recognizer.adjust_for_ambient_noise(src, duration=0.5)
                audio = self._recognizer.listen(src, timeout=10, phrase_time_limit=15)
            text = self._recognizer.recognize_google(audio)
            self._mic_active = False
            self._emit("voice_input", {"text": text})
        except Exception as e:
            self._mic_active = False
            self._emit("status", {"state": "LISTENING"})


# ── HTTP server ───────────────────────────────────────────
class SilentHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)
    def log_message(self, *a): pass   # suppress request logs

def run_http():
    server = http.server.HTTPServer(("127.0.0.1", HTTP_PORT), SilentHandler)
    server.serve_forever()


# ── WebSocket server ──────────────────────────────────────
engine = AngelEngine()

async def ws_handler(websocket):
    engine._ws = websocket
    engine._loop = asyncio.get_event_loop()
    print("[Angel] Browser connected.")
    try:
        async for raw in websocket:
            try:
                msg = json.loads(raw)
                t = msg.get("type")
                if t == "message":
                    engine.send_message(msg.get("content", ""))
                elif t == "mic_start":
                    engine.start_mic()
                elif t == "mic_stop":
                    engine.stop_mic()
                elif t == "ping":
                    await websocket.send(json.dumps({"type": "pong"}))
            except Exception as e:
                print(f"[Angel] WS parse error: {e}")
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        engine._ws = None
        print("[Angel] Browser disconnected.")


async def run_ws():
    async with websockets.serve(ws_handler, "127.0.0.1", WS_PORT):
        print(f"[Angel] WebSocket on ws://127.0.0.1:{WS_PORT}")
        await asyncio.Future()   # run forever


# ── Launch browser in app mode ────────────────────────────
def open_browser():
    url = f"http://127.0.0.1:{HTTP_PORT}"
    # Try Chrome app mode first (looks like a native window)
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for chrome in chrome_paths:
        if os.path.exists(chrome):
            subprocess.Popen([
                chrome,
                f"--app={url}",
                "--window-size=1100,720",
                "--disable-extensions",
            ])
            print(f"[Angel] Opened in Chrome app mode: {url}")
            return
    # Fallback: regular browser
    webbrowser.open(url)
    print(f"[Angel] Opened in default browser: {url}")


# ── Main ──────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 45)
    print("  A.N.G.E.L — Variant I  |  Starting up...")
    print("=" * 45)

    # HTTP server thread
    t = threading.Thread(target=run_http, daemon=True)
    t.start()
    print(f"[Angel] HTTP server on http://127.0.0.1:{HTTP_PORT}")

    # Open browser after short delay
    threading.Timer(1.2, open_browser).start()

    # Run WebSocket event loop (blocks)
    asyncio.run(run_ws())
