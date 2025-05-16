import subprocess
import time
import os

def record_video(output_path: str, duration: int, orientation: str = "portrait",
                 max_words: int = 5, caption_style: str = "style1",
                 background_music: str = "story-classical-3-710.mp3",
                 bg_music_volume: str = "0.05", effect_volume: str = "1"):

    puppeteer_cmd = [
        "node", "puppeteer-launcher.js",
        orientation, str(max_words), caption_style,
        background_music, bg_music_volume, effect_volume
    ]
    print("▶️ Launching Puppeteer:", puppeteer_cmd)
    try:
        subprocess.run(puppeteer_cmd, check=True)
    except subprocess.CalledProcessError as e:
        print("❌ Puppeteer script failed:", e)

    print("✅ Puppeteer step complete, now moving to OBS...")
    time.sleep(5)

    scene = "LandscapeScene" if orientation == "landscape" else "PortraitScene"
    profile = "LandscapeProfile" if orientation == "landscape" else "PortraitProfile"

    obs_cmd = [
        "node", "obs-recorder.js",
        scene, profile, str(duration), output_path
    ]
    print("📦 Going to run OBS cmd:\n", obs_cmd)
    print("📁 Current working directory:", os.getcwd())
    print("📦 Looking for:", os.path.abspath("obs-recorder.js"))

    try:
        result = subprocess.run(obs_cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", shell=True)

        print("📦 OBS stdout:\n", result.stdout)
        print("❌ OBS stderr:\n", result.stderr)
    except Exception as e:
        print("❌ Exception while running OBS recorder:", e)

    if os.path.exists(output_path):
        print(f"✅ Video created at: {output_path}")
    else:
        print(f"❌ No video found at: {output_path}. Check OBS recording folder or logs.")

# ✅ Call the function
if __name__ == "__main__":
    record_video(
        output_path="test.mp4",
        duration=10,
        orientation="portrait",
        max_words=4,
        caption_style="style2",
        background_music="story-classical-3-710.mp3"
    )
