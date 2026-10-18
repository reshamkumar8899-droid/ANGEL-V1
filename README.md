<div align="center">

<img src="https://img.shields.io/badge/A.N.G.E.L-Variant%20I-00f5ff?style=for-the-badge&labelColor=0a0a0a&color=00f5ff" />
<img src="https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white" />
<img src="https://img.shields.io/badge/Gemini-AI-4285F4?style=for-the-badge&logo=google&logoColor=white" />
<img src="https://img.shields.io/badge/XTTS_v2-Voice_Cloning-00f5ff?style=for-the-badge" />
<img src="https://img.shields.io/badge/Status-Active-00ff88?style=for-the-badge" />

<br/><br/>

# A.N.G.E.L — Variant I

**A personal AI desktop assistant with a custom HUD interface, voice cloning, and Gemini AI.**  
*Inspired by GTA Online's Angel character. Built for Larpbase.*

</div>

---

## ✨ Features

| Feature | Status |
|---|---|
| 🧠 Gemini AI (conversational brain) | ✅ Active |
| 🎙️ Microphone voice input | ✅ Active |
| 🗣️ XTTS v2 voice cloning | ✅ Active |
| 💻 Custom cyan HUD interface | ✅ Active |
| 🌐 Chrome app mode (native window feel) | ✅ Active |
| ⚡ Real-time WebSocket communication | ✅ Active |

---

## 🖥️ Preview

> A sleek, blueprint-style HUD with animated orb, scanlines, and real-time AI chat.  
> Runs as a frameless window via Chrome app mode.

---

## ⚙️ Requirements

### System
- **Windows 10/11** (64-bit)
- **Python 3.10 or higher** — [Download here](https://www.python.org/downloads/)
- **Google Chrome** — [Download here](https://www.google.com/chrome/)
- **GPU (optional but recommended)** — NVIDIA RTX for real-time XTTS v2 voice cloning

### API Keys
- **Gemini API Key** (free tier available) — [Get one here](https://aistudio.google.com/app/apikey)

---

## 🚀 Installation

### Step 1 — Clone the repo

```bash
git clone https://github.com/Larpbase/angel-variant-i.git
cd angel-variant-i
```

### Step 2 — Set up your API key

```bash
# Copy the example env file
copy .env.example .env
```

Then open `.env` in any text editor and replace the placeholder:

```env
GEMINI_API_KEY=your_actual_key_here
```

### Step 3 — Install dependencies

**Option A — Use the setup script (recommended)**
```
Double-click setup.bat
```

**Option B — Manual install**
```bash
pip install google-genai python-dotenv SpeechRecognition pyttsx3 websockets pyaudio
```

### Step 4 — (Optional) Enable voice cloning

To use XTTS v2 voice cloning, you need PyTorch + coqui-tts:

1. Install PyTorch for your system from [pytorch.org](https://pytorch.org/get-started/locally/)
   - Select your CUDA version (e.g. CUDA 12.1 for RTX 30-series)
2. Then install coqui-tts:
   ```bash
   pip install coqui-tts
   ```
3. Place a `.wav` voice sample file named `angel_voice.wav` in the project root
   - Must be a clean 10–30 second audio clip of the target voice
   - No background music or noise

> **Note:** First run will auto-download the XTTS v2 model (~1.8 GB). This only happens once.  
> Without `angel_voice.wav`, Angel falls back to a default system voice automatically.

---

## ▶️ Running

```
Double-click run.bat
```

Or from terminal:
```bash
python angel.py
```

Angel will:
1. Start a local HTTP server on port `7771`
2. Start a WebSocket server on port `7772`
3. Open the HUD in Chrome app mode automatically

---

## 📁 Project Structure

```
angel-variant-i/
├── angel.py            # Main backend (AI + TTS + WebSocket server)
├── web/
│   ├── index.html      # HUD interface
│   ├── style.css       # Cyan blueprint stylesheet
│   └── app.js          # Frontend WebSocket client
├── .env.example        # API key template (copy to .env)
├── setup.bat           # Auto-installer
├── run.bat             # One-click launcher
└── requirements.txt    # Python dependencies
```

---

## 🔧 Configuration

All settings are in `.env`:

```env
GEMINI_API_KEY=your_key_here
```

Advanced config (edit `angel.py` directly):

| Variable | Default | Description |
|---|---|---|
| `HTTP_PORT` | `7771` | Local web server port |
| `WS_PORT` | `7772` | WebSocket server port |
| `VOICE_SAMPLE` | `angel_voice.wav` | Path to voice clone reference |
| `SYSTEM_PROMPT` | Angel persona | AI personality/behavior |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| AI Brain | Google Gemini (via `google-genai`) |
| Voice Cloning | XTTS v2 (Coqui TTS) |
| Speech-to-Text | Google Speech Recognition |
| Frontend | HTML5 / CSS3 / Vanilla JS |
| Backend | Python (asyncio + websockets) |
| Window | Chrome `--app` mode |

---

## 🗺️ Roadmap

- [ ] Wake word detection ("Hey Angel")
- [ ] Persistent memory across sessions
- [ ] Live web search
- [ ] PC control (open apps, screenshots)
- [ ] Proactive reminders & timers
- [ ] Music / media control

---

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

---

<div align="center">
<sub>Built by <a href="https://github.com/reshamkumar8899-droid">Rajeev-kun</a> · Powered by Google Gemini · Voice by XTTS v2</sub>
</div>
