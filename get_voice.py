"""
get_voice.py — Download Angel's voice sample from a YouTube URL.
Run: python get_voice.py <youtube_url>
"""

import sys
import os
import subprocess

def download_voice(url: str):
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "angel_voice.wav")
    print(f"[Angel] Downloading audio from: {url}")
    result = subprocess.run([
        sys.executable, "-m", "yt_dlp",
        "--extract-audio",
        "--audio-format", "wav",
        "--audio-quality", "0",
        "--postprocessor-args", "-ar 22050 -ac 1",
        "-o", out_path.replace(".wav", ".%(ext)s"),
        "--no-playlist",
        url
    ], capture_output=False)

    if result.returncode == 0 and os.path.exists(out_path):
        print(f"\n✅ Voice sample saved to: {out_path}")
        print("Now run: python angel.py")
    else:
        print("\n❌ Download failed. Make sure the URL is correct.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python get_voice.py <youtube_url>")
        print('Example: python get_voice.py "https://www.youtube.com/watch?v=XXXXXX"')
    else:
        download_voice(sys.argv[1])
