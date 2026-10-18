@echo off
echo ================================================
echo   A.N.G.E.L -- Variant I  ^|  Setup
echo ================================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo [1/4] Installing core dependencies...
pip install google-genai python-dotenv SpeechRecognition pyttsx3 websockets
echo.

echo [2/4] Installing PyAudio for microphone input...
pip install pyaudio
if errorlevel 1 (
    echo [WARN] PyAudio install failed. Try manually:
    echo        pip install pipwin ^&^& pipwin install pyaudio
)
echo.

echo [3/4] Checking for PyTorch (needed for XTTS voice cloning)...
python -c "import torch; print('[OK] PyTorch found:', torch.__version__)" 2>nul
if errorlevel 1 (
    echo [INFO] PyTorch not found. Angel will use basic TTS voice instead.
    echo        To enable voice cloning, install PyTorch from:
    echo        https://pytorch.org/get-started/locally/
    echo        Then run: pip install coqui-tts
)
echo.

echo [4/4] Setting up .env file...
if not exist .env (
    copy .env.example .env >nul
    echo [OK] Created .env from template.
    echo      Open .env and paste your Gemini API key.
) else (
    echo [OK] .env already exists.
)
echo.

echo ================================================
echo   Setup complete!
echo.
echo   Next steps:
echo   1. Open .env and add your GEMINI_API_KEY
echo   2. (Optional) Place angel_voice.wav for voice cloning
echo   3. Double-click run.bat to launch Angel
echo ================================================
pause
