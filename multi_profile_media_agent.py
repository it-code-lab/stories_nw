# multi_profile_media_agent_static.py
# ------------------------------------------------------------
# Multi-profile, no-API, UI-driven image->video pipeline
# Keeps ALL account/profile/config in this file.
#
# First run per profile: headless=False, log in manually.
# After sessions persist, you can try headless=True.
# ------------------------------------------------------------

import asyncio
import os
import random
import re
import subprocess
from pathlib import Path
from typing import Dict, List
from playwright.async_api import async_playwright, BrowserContext, Page, expect
from datetime import datetime

# =========================
# GLOBAL CONFIG (edit here)
# =========================

# Prompts source: one prompt per line
PROMPTS_FILE = "prompts.txt"

# Video rendering (local ffmpeg) defaults
RESOLUTION = "1080x1920"   # "1920x1080" for landscape, "1080x1920" for portrait
DURATION   = 8             # seconds per clip
FPS        = 30
KENBURNS   = True          # gentle zoom-in effect with ffmpeg
VIDEO_FROM = "ffmpeg"      # "ffmpeg" (default) or "meta" to attempt Meta UI

# Playwright / Browser
BROWSER_NAME     = "chromium"   # "chromium" | "firefox" | "webkit"
CHROME_EXECUTABLE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
HEADLESS         = False        # first run: False to log in; later you may try True
POLITE_MIN_WAIT  = 0.8
POLITE_MAX_WAIT  = 1.8

# Work distribution
MAX_PROMPTS_PER_ACCOUNT = 5      # how many prompts to run per account
SHUFFLE_PROMPTS         = True   # randomize prompt order on each run
DRY_RUN                 = False  # True = don't click generate/download; placeholders instead

# ============
# ACCOUNTS
# ============
# Add as many as you want. Each account has:
# id, profile (Chrome user-data-dir), out (downloads/output folder),
# and per-account URLs if you want (or use global).
ACCOUNTS: List[Dict[str, str]] = [
    {
        "id": "numero_uno",
        "profile": r"C:\Users\mail2\AppData\Local\Google\Chrome\User Data\Profile 1",
        "out": r"downloads\numero_uno",
        "google_url": "https://aistudio.google.com/prompts/1SHiNmxmlkmYTqHH8wseV4evAegV0pRvH",
        "meta_url":   "https://www.meta.ai/media/?nr=1",
    },
    # # Example second account (edit these paths/URLs before use):
    # {
    #     "id": "mail2k",
    #     "profile": r"C:\Users\mail2\AppData\Local\Google\Chrome\User Data\Profile 3",
    #     "out": r"downloads\mail2k",
    #     "google_url": "https://aistudio.google.com/prompts/1SHiNmxmlkmYTqHH8wseV4evAegV0pRvH",
    #     "meta_url":   "https://www.meta.ai/media/?nr=1",
    # },
]

# ========
# Helpers
# ========

def load_prompts(path: str) -> List[str]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Prompts file not found: {p.resolve()}")
    lines = [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return lines

def split_work(prompts: List[str], accounts: List[Dict[str, str]], per_account: int) -> None:
    """
    Mutates accounts: injects "_prompts" list in each account dict.
    """
    idx = 0
    for acc in accounts:
        acc["_prompts"] = prompts[idx: idx + per_account]
        idx += per_account

def ensure_dir(path: str | Path):
    Path(path).mkdir(parents=True, exist_ok=True)

def safe_basename(s: str, maxlen: int = 60) -> str:
    # Clean prompt string
    s = re.sub(r"[^a-zA-Z0-9._-]+", "_", s).strip("_")
    base = s[:maxlen] or "asset"

    # Timestamp prefix
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    return f"{ts}_{base}"

def ffmpeg_make_clip(image_path: Path, out_path: Path, resolution: str, duration: int, fps: int, kenburns: bool):
    """
    Create a short video from a still image using local FFmpeg (no API cost).
    """
    w, h = resolution.split("x")
    if kenburns:
        vf = (
            f"[0:v]scale=w=min(iw*{int(w)}/ih*{h},{w}):"
            f"h=min(ih*{int(h)}/iw*{w},{h}):force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,"
            f"zoompan=z='min(1.05,zoom+0.0008)':d={duration*fps}:s={w}x{h}[v]"
        )
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", str(image_path),
            "-filter_complex", vf,
            "-map", "[v]",
            "-t", str(duration),
            "-r", str(fps),
            "-pix_fmt", "yuv420p",
            str(out_path)
        ]
    else:
        vf = (
            f"scale=w=min(iw*{int(w)}/ih*{h},{w}):"
            f"h=min(ih*{int(h)}/iw*{w},{h}):force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2"
        )
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", str(image_path),
            "-vf", vf,
            "-t", str(duration),
            "-r", str(fps),
            "-pix_fmt", "yuv420p",
            str(out_path)
        ]
    print("FFmpeg:", " ".join(cmd))
    subprocess.run(cmd, check=True)

# =========================
# Site-specific automation
# =========================

async def ensure_logged_in(page: Page, post_login_selector: str, site_name: str):
    """
    Wait for a selector that only appears after login.
    Do manual login in the visible window the first time.
    """
    print(f"[{site_name}] Waiting for post-login marker: {post_login_selector}")
    try:
        await page.wait_for_selector(post_login_selector, timeout=120_000)
    except Exception:
        raise RuntimeError(f"[{site_name}] Login check timed out. Log in manually the first time.")

async def generate_image_google_ai(page: Page, url: str, prompt: str, out_dir: Path, dry_run=False) -> Path:
    await page.goto(url)
    # Post-login marker: the prompt textbox (adjust the name if it changes)
    textbox = page.get_by_role("textbox", name="Enter a prompt to generate an")
    await expect(textbox).to_be_visible(timeout=120_000)

    # Count images BEFORE we run (so we can detect the new one)
    gallery_items = page.locator("ms-image-generation-gallery-image")
    before_cnt = await gallery_items.count()

    # Fill prompt
    await textbox.fill(prompt)

    # Optional control (only if present) — your snippet showed a button named ":9"
    try:
        await page.get_by_role("button", name=":9").click(timeout=2_000)
    except Exception:
        pass  # ignore if not present

    if dry_run:
        # Create a tiny placeholder png so the pipeline continues
        ph = out_dir / f"{safe_basename(prompt)}__DRYRUN.png"
        try:
            from PIL import Image
            Image.new("RGB", (16, 16), (210, 210, 210)).save(ph)
        except Exception:
            ph.write_bytes(b"")
        return ph

    # Click Run (exact)
    run_btn = page.get_by_role("button", name="Run", exact=True)
    await expect(run_btn).to_be_enabled()
    await run_btn.click()

    # Wait for generation to complete:
    # Strategy: wait until gallery item count increases OR a “generating” spinner disappears.
    # Primary: count increases
    async def gallery_increased():
        return await gallery_items.count() > before_cnt

    # Give the UI a moment to start work
    await asyncio.sleep(random.uniform(POLITE_MIN_WAIT, POLITE_MAX_WAIT))

    # Poll up to ~90s for new image(s)
    for _ in range(90):
        if await gallery_increased():
            break
        await asyncio.sleep(1.0)
    else:
        raise RuntimeError("Timed out waiting for new generated image in gallery.")

    after_cnt = await gallery_items.count()

    # Figure out which *new* item to download.
    # Some UIs prepend newest at index 0; others append to the end.
    # We'll try BOTH orders deterministically:
    candidates = []
    # If prepended, index 0 is new
    candidates.append(gallery_items.nth(0))
    # If appended, the item at old count index is the first new one
    if after_cnt > before_cnt:
        candidates.append(gallery_items.nth(before_cnt))

    # Prepare output path
    out_path = out_dir / f"{safe_basename(prompt)}.png"

    # Try to click the "Download this image" button within a candidate item
    last_err = None
    for cand in candidates:
        try:
            # Make sure the candidate is attached/visible
            await cand.wait_for(state="visible", timeout=10_000)

            # Prefer a *real* browser download if the site triggers one:
            async with page.expect_download(timeout=30_000) as dl_info:
                # The download control is inside the gallery item:
                dl_btn = cand.get_by_label("Download this image")
                await dl_btn.click()
            dl = await dl_info.value
            await dl.save_as(str(out_path))
            print(f"[Google AI] Saved: {out_path}")
            return out_path
        except Exception as e:
            last_err = e
            # Fall through to try the next candidate
            continue

    # If no real download fired (e.g., it opens a lightbox or uses canvas),
    # fallback to screenshotting the image node:
    try:
        target = candidates[0] if candidates else gallery_items.nth(0)
        # Many custom elements render an <img> inside; try to pierce into it,
        # otherwise screenshot the whole card.
        img_inside = target.locator("img").first
        if await img_inside.count() > 0:
            await img_inside.screenshot(path=str(out_path))
        else:
            await target.screenshot(path=str(out_path))
        print(f"[Google AI] Captured via screenshot: {out_path}")
        return out_path
    except Exception as e:
        raise RuntimeError(f"Could not download/screenshot latest image. Last error: {last_err or e}") from e
    
async def make_video_from_image_meta(page: Page, url: str, image_path: Path, out_dir: Path, dry_run=False) -> Path | None:
    """
    Drive Meta AI UI to create a short video from an image and download it.
    TODO: Replace selectors with real ones from your UI.
    """
    await page.goto(url)
    await ensure_logged_in(page, "text=Create", "Meta AI")

    if dry_run:
        # Generate a local placeholder video
        out_video = out_dir / (image_path.stem + "__DRYRUN.mp4")
        ffmpeg_make_clip(image_path, out_video, "1080x1920", 4, 24, False)
        return out_video

    # TODO: navigate if needed
    # await page.click("text=Image to Video")

    # Upload
    # TODO: replace with actual file input selector
    # file_input = await page.query_selector("input[type='file']")
    # await file_input.set_input_files(str(image_path))

    await asyncio.sleep(random.uniform(POLITE_MIN_WAIT, POLITE_MAX_WAIT))

    # TODO: click Generate
    # await page.click("button:has-text('Generate')")
    await asyncio.sleep(random.uniform(3.0, 5.0))

    out_video = out_dir / (image_path.stem + ".mp4")

    try:
        async with page.expect_download(timeout=180_000) as dl_info:
            # TODO: click the actual Download UI
            # await page.click("button:has-text('Download')")
            pass
        dl = await dl_info.value
        await dl.save_as(str(out_video))
        print(f"[Meta AI] Saved: {out_video}")
        return out_video
    except Exception:
        print("[Meta AI] Download not detected. You can fall back to local FFmpeg.")
        return None

# =========================
# Per-account worker
# =========================

async def run_account(pw, account: Dict[str, str], prompts: List[str]):
    out_dir = Path(account["out"])
    ensure_dir(out_dir)

    browser_type = getattr(pw, BROWSER_NAME)
    print(f"[{account['id']}] Launching with profile: {account['profile']}")
    ctx: BrowserContext = await browser_type.launch_persistent_context(
        user_data_dir=account["profile"],
        headless=HEADLESS,
        executable_path=CHROME_EXECUTABLE,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--start-maximized",
            "--no-default-browser-check",
            "--no-first-run",
        ],
        accept_downloads=True,
    )
    page: Page = await ctx.new_page()
    await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    for i, prompt in enumerate(prompts, start=1):
        try:
            # 1) Generate image (Google AI Studio)
            img_path = await generate_image_google_ai(page, account["google_url"], prompt, out_dir, dry_run=DRY_RUN)
            await asyncio.sleep(random.uniform(POLITE_MIN_WAIT, POLITE_MAX_WAIT))

            # 2) Create video
            if VIDEO_FROM.lower() == "meta":
                vid = await make_video_from_image_meta(page, account["meta_url"], img_path, out_dir, dry_run=DRY_RUN)
                if vid is None:
                    # fallback to local ffmpeg
                    out_mp4 = out_dir / (img_path.stem + ".mp4")
                    ffmpeg_make_clip(img_path, out_mp4, RESOLUTION, DURATION, FPS, KENBURNS)
            else:
                out_mp4 = out_dir / (img_path.stem + ".mp4")
                ffmpeg_make_clip(img_path, out_mp4, RESOLUTION, DURATION, FPS, KENBURNS)

            print(f"[{account['id']}] Completed {i}/{len(prompts)}")
            await asyncio.sleep(random.uniform(POLITE_MIN_WAIT, POLITE_MAX_WAIT))
        except Exception as e:
            print(f"[{account['id']}] ERROR on prompt: {prompt}\n  -> {e}")

    await ctx.close()
    print(f"[{account['id']}] Done.")

# =========================
# Coordinator
# =========================

async def main_async():

    # refuse duplicates
    profiles = [acc["profile"] for acc in ACCOUNTS]
    dupes = {p for p in profiles if profiles.count(p) > 1}
    if dupes:
        raise RuntimeError(f"Duplicate Chrome profiles in ACCOUNTS: {dupes}. "
                        "Each account must use a different user-data-dir.")

    prompts = load_prompts(PROMPTS_FILE)
    if SHUFFLE_PROMPTS:
        random.shuffle(prompts)

    # allocate prompts evenly across accounts
    split_work(prompts, ACCOUNTS, MAX_PROMPTS_PER_ACCOUNT)
    jobs = [(acc, acc.get("_prompts", [])) for acc in ACCOUNTS if acc.get("_prompts")]

    if not jobs:
        print("No prompts assigned. Check PROMPTS_FILE and MAX_PROMPTS_PER_ACCOUNT.")
        return

    # Make sure account output folders exist
    for acc, _ in jobs:
        ensure_dir(acc["out"])

    async with async_playwright() as pw:
        await asyncio.gather(*[run_account(pw, acc, batch) for acc, batch in jobs])

def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("Interrupted by user.")

if __name__ == "__main__":
    main()
