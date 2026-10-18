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
import re
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
    # music / media
    "play ", "pause", "resume", "stop music", "next song",
    "next track", "previous song", "previous track", "skip",
    "go back song", "replay", "restart song",
    # spotify
    "on spotify", "spotify play", "search spotify",
    "spotify search", "play on spotify", "find on spotify",
)

# Music-specific keywords → media key mapping
MUSIC_TRIGGERS = (
    "play ", "pause", "resume", "stop music",
    "next song", "next track", "skip song", "skip track", "skip",
    "previous song", "previous track", "go back song", "prev song",
    "replay", "restart song",
)

# Spotify search triggers
SPOTIFY_TRIGGERS = (
    "on spotify", "spotify play", "search spotify",
    "spotify search", "play on spotify", "find on spotify",
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

# Keywords that trigger reminder/timer creation
REMINDER_TRIGGERS = (
    "remind me", "set a reminder", "set a timer", "set timer",
    "alert me", "notify me", "wake me", "after ", "in ",
    "don't let me forget", "dont let me forget",
)


# ── Reminder Engine ───────────────────────────────────────
class AngelReminders:
    """Manages proactive reminders using threading.Timer."""

    # Matches: "in 5 minutes", "after 2 hours", "in 30 seconds", "in 1 hour"
    TIME_PATTERN = re.compile(
        r'\b(?:in|after)\s+(\d+(?:\.\d+)?)\s*(second|sec|minute|min|hour|hr)s?\b',
        re.IGNORECASE
    )
    # Multipliers to convert to seconds
    UNIT_MAP = {
        "second": 1, "sec": 1,
        "minute": 60, "min": 60,
        "hour": 3600, "hr": 3600,
    }

    def __init__(self):
        self._timers = []   # track active timers

    def parse_reminder(self, message: str):
        """
        Parse message for reminder intent.
        Returns (seconds, label) or (None, None) if not a reminder.
        """
        low = message.lower()
        # Must contain a reminder keyword
        if not any(t in low for t in REMINDER_TRIGGERS):
            return None, None
        # Must contain a time pattern
        match = self.TIME_PATTERN.search(message)
        if not match:
            return None, None

        amount = float(match.group(1))
        unit   = match.group(2).lower()
        seconds = int(amount * self.UNIT_MAP.get(unit, 60))

        # Extract the reminder label — everything after "to" or "about" or "for"
        label = ""
        for kw in (" to ", " about ", " for "):
            idx = low.find(kw)
            if idx != -1:
                label = message[idx + len(kw):].strip()
                # Strip trailing time clause if it crept in
                label = self.TIME_PATTERN.sub("", label).strip(" ,.")
                break
        if not label:
            label = "your reminder"

        return seconds, label

    def schedule(self, seconds: int, label: str, emit_fn, speak_fn):
        """Schedule a reminder to fire after `seconds`."""
        def _fire():
            msg = f"Daddy, just a reminder — {label}."
            emit_fn("reminder", {"content": msg})
            speak_fn(msg)
            print(f"[Angel] Reminder fired: {label}")

        t = threading.Timer(seconds, _fire)
        t.daemon = True
        t.start()
        self._timers.append(t)
        print(f"[Angel] Reminder set: '{label}' in {seconds}s")

    def cancel_all(self):
        for t in self._timers:
            t.cancel()
        self._timers.clear()


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
        self._mic_active  = False
        self._wake_active = True
        self._api_key    = os.getenv("GEMINI_API_KEY", "")
        self._ws         = None
        self._memory     = AngelMemory(DB_PATH)
        self._reminders  = AngelReminders()      # ← proactive reminders
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

        # ── Spotify search (before generic music) ────────────
        if any(t in low for t in SPOTIFY_TRIGGERS):
            return self._handle_spotify(message)

        # ── Music / Media control ─────────────────────────
        if any(t in low for t in MUSIC_TRIGGERS):
            return self._handle_music(low)

        return ""  # not a recognized PC command


    def _handle_music(self, low: str) -> str:
        """Control media player via system media keys."""
        import pyautogui

        # Play / Resume
        if any(k in low for k in ("play ", "resume", "unpause")):
            pyautogui.press("playpause")
            return "Playing, Daddy."

        # Pause
        if "pause" in low:
            pyautogui.press("playpause")
            return "Paused, Daddy."

        # Next track
        if any(k in low for k in ("next song", "next track", "skip song", "skip track", "skip")):
            pyautogui.press("nexttrack")
            return "Skipping to the next track, Daddy."

        # Previous track
        if any(k in low for k in ("previous song", "previous track", "go back song", "prev song")):
            pyautogui.press("prevtrack")
            return "Going back to the previous track, Daddy."

        # Stop
        if "stop music" in low:
            pyautogui.press("stop")
            return "Music stopped, Daddy."

        # Replay / restart
        if any(k in low for k in ("replay", "restart song")):
            pyautogui.press("prevtrack")
            return "Restarting the track, Daddy."

        return "Not sure what to do with the music, Daddy."


    def _handle_spotify(self, message: str) -> str:
        """Parse and open a Spotify search via URI scheme."""
        low = message.lower()

        # Extract the query — strip spotify keywords to get the song/artist name
        query = low
        for strip in ("on spotify", "play on spotify", "spotify play",
                      "search spotify for", "search spotify",
                      "spotify search for", "spotify search",
                      "find on spotify", "play", "search", "find"):
            query = query.replace(strip, "").strip()
        query = query.strip(" ,.")

        if not query:
            # Just open Spotify if no query
            subprocess.Popen("spotify.exe", shell=True)
            return "Opening Spotify for you, Daddy."

        # URI scheme — opens Spotify app directly to search results
        uri = f"spotify:search:{query.replace(' ', '%20')}"
        try:
            import urllib.parse
            clean_uri = f"spotify:search:{urllib.parse.quote(query)}"
            os.startfile(clean_uri)
            print(f"[Angel] Spotify search: {query}")
            return f"Searching Spotify for '{query}', Daddy. Hit play on what you want."
        except Exception:
            # Fallback: open Spotify web player search in Chrome
            import urllib.parse
            web_url = f"https://open.spotify.com/search/{urllib.parse.quote(query)}"
            chrome_paths = [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            ]
            for chrome in chrome_paths:
                if os.path.exists(chrome):
                    subprocess.Popen([chrome, web_url])
                    return f"Opening Spotify web search for '{query}', Daddy."
            webbrowser.open(web_url)
            return f"Searching Spotify for '{query}', Daddy."


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

            # ── Reminder intercept (highest priority) ─────────
            secs, label = self._reminders.parse_reminder(message)
            if secs is not None:
                mins = secs // 60
                time_str = f"{mins} minute{'s' if mins != 1 else ''}" if mins >= 1 else f"{secs} second{'s' if secs != 1 else ''}"
                reply = f"Got it, Daddy. I'll remind you to {label} in {time_str}."
                self._memory.save("user", message)
                self._memory.save("assistant", reply)
                self._emit("status", {"state": "SPEAKING"})
                self._emit("message", {"role": "assistant", "content": reply})
                self._reminders.schedule(secs, label, self._emit, self._speak)
                self._speak(reply)
                return

            # ── PC control intercept ──────────────────────────
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
