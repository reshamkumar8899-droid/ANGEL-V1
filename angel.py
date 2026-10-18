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
import sqlite3
import datetime
from dotenv import load_dotenv

load_dotenv()

# ── Config ───────────────────────────────────────────────
HTTP_PORT  = 7771
WS_PORT    = 7772
WEB_DIR    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
VOICE_SAMPLE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "angel_voice.wav")
DB_PATH    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "angel_memory.db")
USE_XTTS   = os.path.exists(VOICE_SAMPLE)

SYSTEM_PROMPT = """You are Angel — a sleek, intelligent AI assistant.
You always address the user as "Daddy".
You are confident, smooth, and slightly playful, like a trusted partner who's always one step ahead.
You are extremely capable: you can answer anything, help with code, research, writing, games — anything Daddy needs.
Keep responses elegant and concise. Never break character. You are Angel, not a chatbot or AI model."""

# Keywords that trigger a live web search before answering
SEARCH_TRIGGERS = (
    "search", "look up", "lookup", "find", "google",
    "latest", "recent", "news", "today", "right now",
    "current", "who is", "what is happening", "price of",
    "weather", "score", "update", "release", "when did",
)

# Keywords that trigger PC control
PC_TRIGGERS = (
    "open ", "launch ", "start ", "run ",
    "screenshot", "take a screenshot", "snap screen",
    "close ", "volume up", "volume down", "mute",
    "type ", "press ", "click ",
)

# Common app name → executable mapping
APP_MAP = {
    "spotify":      "spotify.exe",
    "chrome":       r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    "discord":      "discord.exe",
    "notepad":      "notepad.exe",
    "calculator":   "calc.exe",
    "file explorer":"explorer.exe",
    "explorer":     "explorer.exe",
    "task manager": "taskmgr.exe",
    "cmd":          "cmd.exe",
    "terminal":     "wt.exe",
    "vs code":      "code.exe",
    "vscode":       "code.exe",
    "steam":        "steam.exe",
    "vlc":          "vlc.exe",
    "paint":        "mspaint.exe",
    "word":         "winword.exe",
    "excel":        "excel.exe",
}


# ── Persistent Memory (SQLite) ────────────────────────────
class AngelMemory:
    """Stores every conversation turn in a local SQLite database."""

    def __init__(self, db_path: str):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._lock = threading.Lock()
        self._create_tables()

    def _create_tables(self):
        with self._lock:
            self._conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    role      TEXT NOT NULL,
                    content   TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            self._conn.commit()

    def save(self, role: str, content: str):
        """Save a message to memory."""
        ts = datetime.datetime.now().isoformat()
        with self._lock:
            self._conn.execute(
                "INSERT INTO messages (role, content, timestamp) VALUES (?, ?, ?)",
                (role, content, ts)
            )
            self._conn.commit()

    def load_recent(self, limit: int = 20) -> list:
        """Load last N messages as list of dicts."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT role, content FROM messages ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

    def clear(self):
        """Wipe all memory."""
        with self._lock:
            self._conn.execute("DELETE FROM messages")
            self._conn.commit()
        print("[Angel] Memory cleared.")




# ── AI + Voice engine ─────────────────────────────────────
class AngelEngine:
    def __init__(self):
        self._client     = None
        self._history    = []
        self._xtts       = None
        self._tts_engine = None
        self._recognizer = None
        self._mic_active = False
        self._wake_active = True          # wake word listener running
        self._api_key    = os.getenv("GEMINI_API_KEY", "")
        self._ws         = None           # active websocket connection
        self._memory     = AngelMemory(DB_PATH)
        threading.Thread(target=self._init_all, daemon=True).start()

    def _init_all(self):
        self._init_gemini()
        self._init_tts()
        self._init_stt()
        self._emit("status", {"state": "LISTENING"})
        # start wake word listener after everything is ready
        threading.Thread(target=self._wake_word_loop, daemon=True).start()

    def _init_gemini(self):
        try:
            from google import genai
            from google.genai import types
            if self._api_key:
                self._client = genai.Client(api_key=self._api_key)
                # ── Restore history from memory ──────────────────
                saved = self._memory.load_recent(limit=40)
                self._history = []
                for msg in saved:
                    role = "user" if msg["role"] == "user" else "model"
                    self._history.append(
                        types.Content(role=role, parts=[types.Part(text=msg["content"])])
                    )
                count = len(saved)
                print(f"[Angel] Gemini ready. Restored {count} messages from memory.")
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

    # ── Wake Word Listener ────────────────────────────────
    WAKE_WORDS = ("hey angel", "angel", "yo angel", "ok angel", "wake up angel")

    def _wake_word_loop(self):
        """Continuously listens for wake word in background."""
        if not self._recognizer:
            return
        import speech_recognition as sr
        print("[Angel] Wake word listener active — say 'Hey Angel' to activate")
        while self._wake_active:
            # Skip listening if mic is already active (user already talking)
            if self._mic_active:
                import time; time.sleep(0.5)
                continue
            try:
                with sr.Microphone() as src:
                    self._recognizer.adjust_for_ambient_noise(src, duration=0.3)
                    # Short timeout — just checking for wake word
                    audio = self._recognizer.listen(src, timeout=3, phrase_time_limit=3)
                text = self._recognizer.recognize_google(audio).lower()
                print(f"[Angel] Wake listener heard: '{text}'")
                if any(w in text for w in self.WAKE_WORDS):
                    print("[Angel] Wake word detected!")
                    self._emit("wake", {"text": text})
                    # Slight pause so the full mic capture doesn't pick up the wake word
                    import time; time.sleep(0.6)
            except sr.WaitTimeoutError:
                pass   # silence — keep looping
            except sr.UnknownValueError:
                pass   # couldn't understand — keep looping
            except Exception as e:
                import time; time.sleep(1)  # brief pause on error, then retry

    # ── Emit helper (thread-safe) ─────────────────────────
    def _emit(self, type_: str, data: dict):
        if self._ws:
            payload = json.dumps({"type": type_, **data})
            asyncio.run_coroutine_threadsafe(
                self._ws.send(payload), self._loop
            )

    # ── Web Search ────────────────────────────────────────
    def _web_search(self, query: str) -> str:
        """Search DuckDuckGo and return top results as a string."""
        try:
            from ddgs import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=3))
            if not results:
                return ""
            lines = [f"[Web Search Results for: '{query}']"]
            for i, r in enumerate(results, 1):
                lines.append(f"{i}. {r.get('title','')}: {r.get('body','')}")
            summary = "\n".join(lines)
            print(f"[Angel] Web search: {query} → {len(results)} results")
            return summary
        except Exception as e:
            print(f"[Angel] Web search failed: {e}")
            return ""

    def _needs_search(self, message: str) -> bool:
        """Detect if message needs a live web search."""
        low = message.lower()
        return any(t in low for t in SEARCH_TRIGGERS)

    def _needs_pc_control(self, message: str) -> bool:
        """Detect if message is a PC control command."""
        low = message.lower()
        return any(t in low for t in PC_TRIGGERS)

    # ── PC Control ────────────────────────────────────────
    def _handle_pc_command(self, message: str) -> str:
        """Parse and execute a PC control command. Returns result string."""
        low = message.lower()

        # ── Screenshot ───────────────────────────────────
        if any(k in low for k in ("screenshot", "snap screen", "take a screenshot")):
            return self._take_screenshot()

        # ── Open app ─────────────────────────────────────
        if any(low.startswith(k) for k in ("open ", "launch ", "start ", "run ")):
            # extract app name after the verb
            for verb in ("open ", "launch ", "start ", "run "):
                if low.startswith(verb):
                    app_name = low[len(verb):].strip()
                    break
            return self._open_app(app_name)

        # ── Volume ───────────────────────────────────────
        if "volume up" in low:
            import pyautogui
            for _ in range(5): pyautogui.press("volumeup")
            return "Volume up, Daddy."
        if "volume down" in low:
            import pyautogui
            for _ in range(5): pyautogui.press("volumedown")
            return "Volume down, Daddy."
        if "mute" in low:
            import pyautogui
            pyautogui.press("volumemute")
            return "Muted, Daddy."

        return ""  # not a recognized PC command

    def _open_app(self, app_name: str) -> str:
        """Open an app by name."""
        # Check known map first
        for key, exe in APP_MAP.items():
            if key in app_name:
                try:
                    subprocess.Popen(exe, shell=True)
                    return f"Opening {key} for you, Daddy."
                except Exception as e:
                    return f"Couldn't open {key}, Daddy: {e}"
        # Try running directly as command
        try:
            subprocess.Popen(app_name, shell=True)
            return f"Trying to open '{app_name}' for you, Daddy."
        except Exception as e:
            return f"Couldn't open '{app_name}', Daddy: {e}"

    def _take_screenshot(self) -> str:
        """Take a screenshot and save it to the desktop."""
        try:
            import pyautogui
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            path = os.path.join(desktop, f"angel_screenshot_{ts}.png")
            pyautogui.screenshot(path)
            print(f"[Angel] Screenshot saved: {path}")
            return f"Screenshot saved to your Desktop as angel_screenshot_{ts}.png, Daddy."
        except Exception as e:
            return f"Couldn't take screenshot, Daddy: {e}"


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

            # ── PC control intercept (runs before AI/search) ──
            if self._needs_pc_control(message):
                result = self._handle_pc_command(message)
                if result:
                    self._memory.save("user", message)
                    self._memory.save("assistant", result)
                    self._emit("status", {"state": "SPEAKING"})
                    self._emit("message", {"role": "assistant", "content": result})
                    self._speak(result)
                    return

            # ── Web search injection ──────────────────────
            prompt = message
            if self._needs_search(message):
                self._emit("status", {"state": "SEARCHING"})
                web_ctx = self._web_search(message)
                if web_ctx:
                    prompt = f"{web_ctx}\n\nUsing the above web results, answer this: {message}"

            self._memory.save("user", message)
            self._history.append(types.Content(role="user", parts=[types.Part(text=prompt)]))
            self._emit("status", {"state": "THINKING"})
            response = self._client.models.generate_content(
                model="gemini-3.5-flash-lite",
                contents=self._history,
                config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
            )
            text = response.text
            self._history.append(types.Content(role="model", parts=[types.Part(text=text)]))
            self._memory.save("assistant", text)
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
                elif t == "clear_memory":
                    engine._memory.clear()
                    engine._history = []
                    await websocket.send(json.dumps({"type": "status", "state": "LISTENING"}))
                elif t == "toggle_wake":
                    engine._wake_active = not engine._wake_active
                    state = "on" if engine._wake_active else "off"
                    print(f"[Angel] Wake word listener: {state}")
                    await websocket.send(json.dumps({"type": "pong"}))
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
