"""
get_voice.py — Download Angel's voice sample from a YouTube URL.
Run: python get_voice.py <youtube_url>
"""

import sys
import os
import subprocess

def download_voice(url: str):
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "angel_voice.wav")
    # Use a temp name so yt-dlp's intermediate files don't clash
    tmp_template = os.path.join(os.path.dirname(os.path.abspath(__file__)), "angel_voice_dl.%(ext)s")
    print(f"[Angel] Downloading audio from: {url}")
    result = subprocess.run([
        sys.executable, "-m", "yt_dlp",
        "--extract-audio",
        "--audio-format", "wav",
        "--audio-quality", "0",
        "--postprocessor-args", "-ar 22050 -ac 1",
        "-o", tmp_template,
        "--no-playlist",
        url
    ], capture_output=False)

    # yt-dlp outputs to angel_voice_dl.wav after conversion
    tmp_wav = os.path.join(os.path.dirname(os.path.abspath(__file__)), "angel_voice_dl.wav")
    if result.returncode == 0 and os.path.exists(tmp_wav):
        # Rename to final path (overwrite if exists)
        if os.path.exists(out_path):
            os.remove(out_path)
        os.rename(tmp_wav, out_path)
        print(f"\n✅ Voice sample saved to: {out_path}")
        print("Now run: python angel.py")
    else:
        # Clean up any leftover temp files
        for f in os.listdir(os.path.dirname(os.path.abspath(__file__))):
            if f.startswith("angel_voice_dl."):
                os.remove(os.path.join(os.path.dirname(os.path.abspath(__file__)), f))
        print("\n❌ Download failed. Make sure the URL is correct.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python get_voice.py <youtube_url>")
        print('Example: python get_voice.py "https://www.youtube.com/watch?v=XXXXXX"')
    else:
        download_voice(sys.argv[1])
