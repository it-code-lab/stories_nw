# multi_profile_media_agent.py  (Excel-enabled, with account_id_1/account_id_2)
# ------------------------------------------------------------
# Two-pass workflow:
#   1) RUN_MODE="images" -> read prompts from Excel, generate images, write image_path (+account_id_1)
#   2) RUN_MODE="videos" -> read image_path + video_cmd, render, write video_path (+account_id_2)
#
# Sheet: Jobs
# Columns (case-insensitive): prompt, account_id, image_path, video_cmd, video_path, status,
#                             account_id_1, account_id_2
# ------------------------------------------------------------

import asyncio
import os
import random
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import uuid
from playwright.async_api import async_playwright, BrowserContext, Page, expect

# ===== Excel =====
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

# =========================
# GLOBAL CONFIG (edit here)
# =========================

RUN_MODE = "videos"   # "images" or "videos"

EXCEL_FILE  = r"media_jobs.xlsx"
SHEET_NAME  = "Jobs"

# default video rendering if video_cmd is blank
DEFAULT_VIDEO_CMD = (
    'ffmpeg -y -loop 1 -i "{image}" -t 8 -r 30 -pix_fmt yuv420p "{out}"'
)

# "Video account" label when videos are created locally (not by a browser account)
VIDEO_ACCOUNT_ID = "local_ffmpeg"

# Video rendering defaults for the local helper (not used by DEFAULT_VIDEO_CMD directly)
RESOLUTION = "1080x1920"
DURATION   = 8
FPS        = 30
KENBURNS   = True

# Playwright / Browser
BROWSER_NAME      = "chromium"
CHROME_EXECUTABLE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
HEADLESS          = False
POLITE_MIN_WAIT   = 0.8
POLITE_MAX_WAIT   = 1.8

# Make screenshots crisper (also helps UI fallbacks)
DEVICE_SCALE_FACTOR = 2

# Downloads isolation (prevents Chrome saving into OS default Downloads)
ISOLATE_DOWNLOADS = True

# Work distribution
MAX_GGL_IMG_PROMPTS_PER_ACCOUNT = 40
MAX_META_VID_PROMPTS_PER_ACCOUNT = 60
SHUFFLE_PROMPTS         = False
DRY_RUN                 = False

# ---- Account audit columns (do not rename unless you also update ensure_columns) ----
ACCOUNT_ID1_COL = "account_id_1"   # who generated the image
ACCOUNT_ID2_COL = "account_id_2"   # who generated the video

# ============ ACCOUNTS ============
ACCOUNTS: List[Dict[str, str]] = [
    {
        "id": "numero_uno",
        "profile": r"C:\Users\mail2\AppData\Local\Google\Chrome\User Data\Profile 1",
        "out": r"downloads",
        "google_url": "https://aistudio.google.com/prompts/1SHiNmxmlkmYTqHH8wseV4evAegV0pRvH",
        "meta_url":   "https://www.meta.ai/media/?nr=1",
    },
    {
        "id": "s173m",
        "profile": r"C:\Users\mail2\AppData\Local\Google\Chrome\User Data\Profile 3",
        "out": r"downloads",
        "google_url": "https://aistudio.google.com/prompts/1Tyv17HS3-w0sVP6oPNQ8ULMDBzAMvIMF",
        "meta_url":   "https://www.meta.ai/media/?nr=1",
    },
    {
        "id": "mail2km",
        "profile": r"C:\Users\mail2\AppData\Local\Google\Chrome\User Data\Profile 4",
        "out": r"downloads",
        "google_url": "https://aistudio.google.com/prompts/1CzRw-7NIzeaIqFCpYc5-vV_vM2kRMDXh",
        "meta_url":   "https://www.meta.ai/media/?nr=1",
    },
    {
        "id": "mail2kishnm",
        "profile": r"C:\Users\mail2\AppData\Local\Google\Chrome\User Data\Profile 6",
        "out": r"downloads",
        "google_url": "https://aistudio.google.com/prompts/1NC_HmDTCGQhQQflVtof2MgN0UUqGGpYO",
        "meta_url":   "https://www.meta.ai/media/?nr=1",
    },    
    {
        "id": "mail2sm",
        "profile": r"C:\Users\mail2\AppData\Local\Google\Chrome\User Data\Profile 7",
        "out": r"downloads",
        "google_url": "https://aistudio.google.com/prompts/1812Pe1f0s06ygMIfn_IT8hNfP-aqSnmS",
        "meta_url":   "https://www.meta.ai/media/?nr=1",
    }, 
    {
        "id": "mail2nishm1",
        "profile": r"C:\Users\mail2\AppData\Local\Google\Chrome\User Data\Profile 8",
        "out": r"downloads",
        "google_url": "https://aistudio.google.com/prompts/14ghA9r3kNxMo0GCgX5mxcfA8i-fk7ee-",
        "meta_url":   "https://www.meta.ai/media/?nr=1",
    }, 
    {
        "id": "mail2nakshm",
        "profile": r"C:\Users\mail2\AppData\Local\Google\Chrome\User Data\Profile 9",
        "out": r"downloads",
        "google_url": "https://aistudio.google.com/prompts/1GhH0rXYgQtwTY7h9FtKUfYCWtT0n8oph",
        "meta_url":   "https://www.meta.ai/media/?nr=1",
    }, 
    {
        "id": "mummy",
        "profile": r"C:\Users\mail2\AppData\Local\Google\Chrome\User Data\Profile 10",
        "out": r"downloads",
        "google_url": "https://aistudio.google.com/prompts/1NvEngwCN7o0ghPVb_x-MNOsi0ESIc_5M",
        "meta_url":   "https://www.meta.ai/media/?nr=1",
    }, 
    {
        "id": "papa",
        "profile": r"C:\Users\mail2\AppData\Local\Google\Chrome\User Data\Profile 11",
        "out": r"downloads",
        "google_url": "https://aistudio.google.com/prompts/1Dyaf1Zo_EzdUIiZGlJzasLD6k0WvQcnU",
        "meta_url":   "https://www.meta.ai/media/?nr=1",
    },
]

META_ACCOUNTS: List[Dict[str, str]] = [
    {
        "id": "mail2sm",
        "profile": r"C:\Users\mail2\AppData\Local\Google\Chrome\User Data\Profile 1",
        "out": r"downloads",
        "google_url": "https://aistudio.google.com/prompts/1SHiNmxmlkmYTqHH8wseV4evAegV0pRvH",
        "meta_url":   "https://www.meta.ai/media/?nr=1",
    },
    {
        "id": "numero_uno",
        "profile": r"C:\Users\mail2\AppData\Local\Google\Chrome\User Data\Profile 3",
        "out": r"downloads",
        "google_url": "https://aistudio.google.com/prompts/18LNm8fsaraxHYYWCB92vGp4BC1-put7S",
        "meta_url":   "https://www.meta.ai/media/?nr=1",
    },
    {
        "id": "mail2km",
        "profile": r"C:\Users\mail2\AppData\Local\Google\Chrome\User Data\Profile 4",
        "out": r"downloads",
        "google_url": "https://aistudio.google.com/prompts/1CzRw-7NIzeaIqFCpYc5-vV_vM2kRMDXh",
        "meta_url":   "https://www.meta.ai/media/?nr=1",
    },
]
# ======== Helpers ========

def ensure_dir(p: str | Path):
    Path(p).mkdir(parents=True, exist_ok=True)

def safe_basename(s: str, maxlen: int = 30) -> str:
    s = re.sub(r"[^a-zA-Z0-9._-]+", "_", s).strip("_")
    base = s[:maxlen] or "asset"
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{ts}_{base}"

def open_wb_with_retry(path: str, attempts: int = 5, delay: float = 0.5):
    for i in range(attempts):
        try:
            return load_workbook(path)
        except PermissionError:
            if i == attempts - 1:
                raise
            import time; time.sleep(delay)

def save_wb_with_retry(wb, path: str, attempts: int = 5, delay: float = 0.5):
    for i in range(attempts):
        try:
            wb.save(path)
            return
        except PermissionError:
            if i == attempts - 1:
                raise
            import time; time.sleep(delay)

def ensure_columns(ws, required_headers: List[str]) -> None:
    """Create any missing headers at the end of row 1."""
    existing = { (str(c.value).strip().lower() if c.value else ""): j
                 for j, c in enumerate(ws[1], start=1) }
    max_col = ws.max_column
    for name in required_headers:
        key = name.lower()
        if key not in existing or existing.get(key) is None:
            max_col += 1
            ws.cell(1, max_col).value = name
            existing[key] = max_col

def colmap_from_headers(ws) -> Dict[str, int]:
    """Map header name (lower) -> column index (1-based)."""
    header = {}
    for j, cell in enumerate(ws[1], start=1):
        if cell.value:
            header[str(cell.value).strip().lower()] = j
    return header

def read_jobs_from_excel_for_images() -> List[Dict]:
    """Rows needing image generation: prompt set AND image_path empty."""
    wb = open_wb_with_retry(EXCEL_FILE)
    ws = wb[SHEET_NAME]

    # Ensure columns exist (adds audit columns if missing)
    ensure_columns(ws, [
        "prompt", "account_id", "image_path", "video_cmd", "video_path", "status",
        ACCOUNT_ID1_COL, ACCOUNT_ID2_COL
    ])
    h = colmap_from_headers(ws)

    rows = []
    for i in range(2, ws.max_row + 1):
        prompt = (ws.cell(i, h["prompt"]).value or "").strip()
        img    = (ws.cell(i, h["image_path"]).value or "").strip()
        acct   = (ws.cell(i, h["account_id"]).value or "").strip()
        if prompt and not img:
            rows.append({"row": i, "prompt": prompt, "account_id": acct})
    save_wb_with_retry(wb, EXCEL_FILE)  # in case we added headers
    wb.close()
    return rows

def read_jobs_from_excel_for_videos() -> List[Dict]:
    """Rows needing video generation: image_path set AND video_path empty."""
    wb = open_wb_with_retry(EXCEL_FILE)
    ws = wb[SHEET_NAME]

    # Ensure columns exist
    ensure_columns(ws, [
        "prompt", "account_id", "image_path", "video_cmd", "video_path", "status",
        ACCOUNT_ID1_COL, ACCOUNT_ID2_COL
    ])
    h = colmap_from_headers(ws)

    rows = []
    for i in range(2, ws.max_row + 1):
        image_path = (ws.cell(i, h["image_path"]).value or "").strip()
        vout  = (ws.cell(i, h["video_path"]).value or "").strip()
        vcmd  = (ws.cell(i, h["video_cmd"]).value or "").strip()
        acct       = (ws.cell(i, h["account_id"]).value or "").strip()
        if image_path and not vout:
            rows.append({
                "row": i,
                "account_id": acct,
                "image_path": image_path,
                "video_cmd": vcmd,  # we'll treat this as the Meta animation prompt
            })
    save_wb_with_retry(wb, EXCEL_FILE)
    wb.close()
    return rows

def write_image_result(row_idx: int, image_path: str, account_id_used: str, status: str = "ok"):
    wb = open_wb_with_retry(EXCEL_FILE)
    ws = wb[SHEET_NAME]

    ensure_columns(ws, [
        "prompt", "account_id", "image_path", "video_cmd", "video_path", "status",
        ACCOUNT_ID1_COL, ACCOUNT_ID2_COL
    ])
    h = colmap_from_headers(ws)

    # Write image path + status
    ws.cell(row_idx, h["image_path"]).value = image_path
    ws.cell(row_idx, h["status"]).value = status

    # If account_id_1 is empty, record who actually generated the image
    if ws.cell(row_idx, h[ACCOUNT_ID1_COL]).value in (None, ""):
        ws.cell(row_idx, h[ACCOUNT_ID1_COL]).value = account_id_used

    # Optional: if assignment account_id is blank, backfill with the one we used
    if ws.cell(row_idx, h["account_id"]).value in (None, ""):
        ws.cell(row_idx, h["account_id"]).value = account_id_used

    save_wb_with_retry(wb, EXCEL_FILE)
    wb.close()

def write_video_result(row_idx: int, video_path: str, account_id_used: str, status: str = "ok"):
    wb = open_wb_with_retry(EXCEL_FILE)
    ws = wb[SHEET_NAME]

    ensure_columns(ws, [
        "prompt", "account_id", "image_path", "video_cmd", "video_path", "status",
        ACCOUNT_ID1_COL, ACCOUNT_ID2_COL
    ])
    h = colmap_from_headers(ws)

    # Write video path + status
    ws.cell(row_idx, h["video_path"]).value = video_path
    ws.cell(row_idx, h["status"]).value = status

    # If account_id_2 is empty, record who actually generated the video
    if ws.cell(row_idx, h[ACCOUNT_ID2_COL]).value in (None, ""):
        ws.cell(row_idx, h[ACCOUNT_ID2_COL]).value = account_id_used

    save_wb_with_retry(wb, EXCEL_FILE)
    wb.close()

# =========================
# Site-specific automation
# =========================

async def ensure_logged_in(page: Page, post_login_selector: str, site_name: str):
    print(f"[{site_name}] Waiting for post-login marker: {post_login_selector}")
    await page.wait_for_selector(post_login_selector, timeout=120_000)

async def generate_image_google_ai(page: Page, prompt: str, out_dir: Path) -> Path:
    """
    Uses selectors:
    - Prompt textbox role name: 'Enter a prompt to generate an'
    - Run button: role 'button' with exact name 'Run'
    - Newest gallery item: assumes append; grabs item at old_count index
    - Large view button label: 'Large view of this image'
    - Modal download button role name: 'Download'
    """
    # Post-login marker: the prompt textbox (adjust if the UI changes)
    textbox = page.get_by_role("textbox", name="Enter a prompt to generate an")
    await expect(textbox).to_be_visible(timeout=120_000)

    gallery_items = page.locator("ms-image-generation-gallery-image")
    before_cnt = await gallery_items.count()
    print(f"before_cnt = {before_cnt}")
    await textbox.fill(prompt)

    if DRY_RUN:
        ph = out_dir / f"{safe_basename(prompt)}__DRYRUN.png"
        try:
            from PIL import Image; Image.new("RGB", (16, 16), (210, 210, 210)).save(ph)
        except Exception:
            ph.write_bytes(b"")
        return ph

    run_btn = page.get_by_role("button", name="Run", exact=True)
    await expect(run_btn).to_be_enabled()
    await run_btn.click()

    await asyncio.sleep(15)
    print("waited 15 seconds")

    # Wait for a new gallery item
    async def gallery_increased():
        return await gallery_items.count() > before_cnt

    for _ in range(90):
        if await gallery_increased():
            break
        await asyncio.sleep(1.0)

    after_cnt = await gallery_items.count()
    if after_cnt <= before_cnt:
        raise RuntimeError("No new image appeared.")

    print(f"after_cnt = {after_cnt}")
    # Candidate: first new item (append behavior)
    candidate = gallery_items.nth(before_cnt)
    out_path = out_dir / f"{safe_basename(prompt)}.png"

    # Try large-view modal and proper download
    try:
        await candidate.get_by_label("Large view of this image").click()
        print("Large view button clicked")

        async with page.expect_download(timeout=30_000) as dl_info:
            await page.get_by_role("button", name="Download").click()
        dl = await dl_info.value

        # move to final path (avoid duplicate in default download dir)
        # suggested = dl.suggested_filename or out_path.name
        # dest = out_path.with_name(suggested)

        dest = out_path.with_name(out_path.name)
        src = await dl.path()
        shutil.move(src, dest)

        # close modal if present
        try:
            await page.get_by_role("button", name="Close").click()
        except Exception:
            pass

        # Optional: quick dimension log (requires Pillow)
        try:
            from PIL import Image
            w, h = Image.open(dest).size
            print(f"[Google AI] Saved full-size {w}x{h}: {dest}")
        except Exception:
            print(f"[Google AI] Saved: {dest}")

        return dest

    except Exception:
        # Full-size fallback via modal image element (or thumb if needed)
        try:
            modal_img = page.get_by_role("img", name="Generated image").first
            await modal_img.wait_for(state="visible", timeout=30_000)

            # Try reading raw bytes from <img src>
            src_attr = await modal_img.get_attribute("src")
            if src_attr and src_attr.startswith("data:"):
                import base64
                m = re.match(r"data:(.*?);base64,(.*)", src_attr, re.DOTALL)
                if m:
                    raw = base64.b64decode(m.group(2))
                    out_path.write_bytes(raw)
                    await page.keyboard.press("Escape")
                    return out_path

            # Else screenshot as last resort
            await modal_img.screenshot(path=str(out_path))
            await page.keyboard.press("Escape")
            return out_path

        except Exception:
            # last resort: thumbnail screenshot
            img_inside = candidate.locator("img").first
            if await img_inside.count() > 0:
                await img_inside.screenshot(path=str(out_path))
                return out_path
            await candidate.screenshot(path=str(out_path))
            return out_path


async def generate_video_meta_ai(page: Page, imagePath: str, prompt: str, out_dir: Path, url) -> Path:
    """
    Automates Meta AI 'Media' -> Video-from-Image flow.

    It will:
      - Switch to 'Video' tab (from Image)
      - Click 'Upload image' and attach the file
      - Fill 'Describe your animation...' with `prompt`
      - Click 'Animate'
      - Wait for rendering to finish
      - Click 'Download media' and MOVE the .mp4 into out_dir (no OS Downloads duplicate)

    Returns: Path to the saved .mp4 in out_dir
    """

    await page.goto(url)

    # Ensure absolute paths
    image_path = str(Path(imagePath).resolve())
    ensure_dir(out_dir)

    # 0) Be sure the meta media page is loaded (your caller already navigates here)
    # Try to land on the media composer area by clicking the "Media" (image/video) entry if present
    # try:
    #     # Some UIs have an icon cluster first; clicking first item opens the composer
    #     await page.locator(".x78zum5.xdt5ytf.x1qughib").first.click(timeout=3000)
    # except Exception:
    #     pass  # optional, UI-dependent

    # 1) Switch to "Video" mode (recorded flows showed two variants)
    switched = False
    try:
        # Variant A: a toggle button then literal "Video" text
        await page.get_by_role("button", name="Image").click(timeout=3000)
        await page.get_by_text("Video", exact=True).click(timeout=3000)
        switched = True
    except Exception:
        try:
            # Variant B: direct "Video" tab
            await page.get_by_text("Video", exact=True).click(timeout=3000)
            switched = True
        except Exception:
            pass

    # if not switched:
    #     # Some shells show a small tab container; try again by clicking the tab region
    #     try:
    #         await page.locator(".xt9c220").click(timeout=3000)
    #         await page.get_by_text("Video", exact=True).click(timeout=3000)
    #     except Exception:
    #         # If we still can’t switch, proceed—the upload button usually scopes the correct panel
    #         pass

    # 2) Click "Upload image" and feed the file chooser (prefer file chooser to avoid targeting wrong input)
    try:
        async with page.expect_file_chooser(timeout=10_000) as fc_info:
            await page.get_by_role("button", name="Upload image").click()
        fc = await fc_info.value
        await fc.set_files(image_path)
    except Exception:
        # Fallback: set first visible file input directly
        try:
            await page.set_input_files("input[type='file']", image_path)
        except Exception as e:
            raise RuntimeError(f"Could not upload image: {e}")

    # 3) Fill the animation prompt (textbox labeled "Describe your animation...")
    try:
        # Focus (some UIs require a paragraph/canvas click first)
        try:
            await page.get_by_role("paragraph").click(timeout=1500)
        except Exception:
            pass
        box = page.get_by_role("textbox", name="Describe your animation...")
        await expect(box).to_be_visible(timeout=20_000)
        await box.fill(prompt or "Animate this image smoothly with parallax camera move.")
    except Exception as e:
        raise RuntimeError(f"Could not set the animation description: {e}")


    # 0) Create a unique stamp for THIS render
    stamp = f"seen-{uuid.uuid4().hex}"

    # 1) Tag ALL existing download buttons with data-stamp="<stamp>"
    #    We tag both common patterns:
    #    - ARIA labeled buttons: [role="button"][aria-label="Download media"]
    #    - Any role="button" containing 'download' in its text (fallback)
    await page.evaluate("""
    (stamp) => {
    const tag = (btn) => { try { btn.setAttribute('data-stamp', stamp); } catch(_){} };
    const byAria = document.querySelectorAll('[role="button"][aria-label="Download media"]');
    byAria.forEach(tag);

    // Fallback: text-based (case-insensitive contains 'download')
    const allButtons = document.querySelectorAll('[role="button"]');
    allButtons.forEach(b => {
        const t = (b.textContent || '').toLowerCase();
        const aria = (b.getAttribute('aria-label') || '').toLowerCase();
        if (t.includes('download') || aria.includes('download')) tag(b);
    });
    }
    """, stamp)

    # 2) Now click Animate (as you already do)
    animate_btn = page.get_by_role("button", name="Animate")
    await expect(animate_btn).to_be_enabled(timeout=10_000)
    await animate_btn.click()

    # 3) Wait for a *new* download button that does NOT have our stamp
    #    First prefer the precise ARIA label, then the text fallback.
    new_dl = page.locator(f'[role="button"][aria-label="Download media"]:not([data-stamp="{stamp}"])')
    fallback_dl = page.locator(f'[role="button"]:not([data-stamp="{stamp}"])').filter(has_text=re.compile(r'download', re.I))

    # Poll up to ~4 minutes for either to appear
    deadline_seconds = 240
    found = False
    for _ in range(deadline_seconds):
        if await new_dl.count() > 0:
            found = True
            target_btn = new_dl.first
            break
        if await fallback_dl.count() > 0:
            found = True
            target_btn = fallback_dl.first
            break
        await asyncio.sleep(1.0)

    if not found:
        raise RuntimeError("Timeout: no new 'Download media' button appeared after Animate.")

    # 4) Click THAT specific new button, bind expect_download to it, and MOVE the file
    await target_btn.scroll_into_view_if_needed()
    await expect(target_btn).to_be_visible(timeout=15_000)
    await expect(target_btn).to_be_enabled(timeout=15_000)

    base = Path(imagePath).resolve().stem
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"{ts}_{base}_meta.mp4"

    async with page.expect_download(timeout=90_000) as dl_info:
        await target_btn.click()

    dl = await dl_info.value
    src_path = await dl.path()
    shutil.move(src_path, out_path)

    # # Try to close any overlay
    # for sel in [
    #     ('role=button[name="Close"]', lambda: page.get_by_role("button", name="Close")),
    # ]:
    #     try:
    #         await sel[1]().click(timeout=800)
    #     except Exception:
    #         pass

    return out_path

        
# =========================
# Per-account worker (images pass)
# =========================

async def run_account_images(pw, account: Dict[str, str], jobs: List[Dict]):
    out_dir = Path(account["out"])
    ensure_dir(out_dir)

    browser_type = getattr(pw, BROWSER_NAME)
    print(f"[{account['id']}] Launching with profile: {account['profile']}")
    ctx_kwargs = dict(
        user_data_dir=account["profile"],
        headless=HEADLESS,
        executable_path=CHROME_EXECUTABLE,
        device_scale_factor=DEVICE_SCALE_FACTOR,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--start-maximized",
            "--no-default-browser-check",
            "--no-first-run",
        ],
        accept_downloads=True,
    )
    if ISOLATE_DOWNLOADS:
        ensure_dir(out_dir / "__tmp_downloads")
        ctx_kwargs["downloads_path"] = str(out_dir / "__tmp_downloads")

    ctx: BrowserContext = await browser_type.launch_persistent_context(**ctx_kwargs)
    page: Page = await ctx.new_page()
    await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    # open Google AI Studio once per account
    await page.goto(account["google_url"])

    for job in jobs:
        row_idx = job["row"]
        prompt  = job["prompt"]
        try:
            img_path = await generate_image_google_ai(page, prompt, out_dir)
            write_image_result(row_idx, str(Path(img_path).resolve()), account_id_used=account["id"], status="ok")
            print(f"[{account['id']}] Row {row_idx} -> {img_path}")
            await asyncio.sleep(random.uniform(POLITE_MIN_WAIT, POLITE_MAX_WAIT))
            await asyncio.sleep(10)
            print("Waited 10 seconds before generating next image")
        except Exception as e:
            write_image_result(row_idx, "", account_id_used=account["id"], status=f"error: {e}")
            print(f"[{account['id']}] Row {row_idx} ERROR: {e}")

    await ctx.close()
    print(f"[{account['id']}] Images pass done.")


# =========================
# Per-account worker (videos pass)
# =========================

async def run_account_videos(pw, account: Dict[str, str], jobs: List[Dict]):
    out_dir = Path(account["out"])
    ensure_dir(out_dir)

    browser_type = getattr(pw, BROWSER_NAME)
    print(f"[{account['id']}] Launching with profile: {account['profile']}")
    ctx_kwargs = dict(
        user_data_dir=account["profile"],
        headless=HEADLESS,
        executable_path=CHROME_EXECUTABLE,
        device_scale_factor=DEVICE_SCALE_FACTOR,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--start-maximized",
            "--no-default-browser-check",
            "--no-first-run",
        ],
        accept_downloads=True,
    )
    if ISOLATE_DOWNLOADS:
        ensure_dir(out_dir / "__tmp_downloads")
        ctx_kwargs["downloads_path"] = str(out_dir / "__tmp_downloads")

    ctx: BrowserContext = await browser_type.launch_persistent_context(**ctx_kwargs)
    page: Page = await ctx.new_page()
    await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    # open Meta AI once per account
    # await page.goto(account["meta_url"])

    for job in jobs:
        row_idx = job["row"]
        prompt  = job["video_cmd"]
        imagePath = job["image_path"]
        try:
            vid_path = await generate_video_meta_ai(page, imagePath, prompt, out_dir,account["meta_url"])
            write_video_result(row_idx, str(Path(vid_path).resolve()), account_id_used=account["id"], status="ok")
            print(f"[{account['id']}] Row {row_idx} -> {vid_path}")
            await asyncio.sleep(random.uniform(POLITE_MIN_WAIT, POLITE_MAX_WAIT))
            #await asyncio.sleep(10)
            #print("Waited 10 seconds before generating next image")
        except Exception as e:
            write_video_result(row_idx, "", account_id_used=account["id"], status=f"error: {e}")
            print(f"[{account['id']}] Row {row_idx} ERROR: {e}")

    await ctx.close()
    print(f"[{account['id']}] Images pass done.")

# =========================
# Videos pass (shell command or default)
# =========================

def run_shell(cmd: str):
    print("RUN:", cmd)
    completed = subprocess.run(cmd, shell=True)
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed with code {completed.returncode}")

def build_default_cmd(image: str, out: str) -> str:
    return DEFAULT_VIDEO_CMD.format(image=image, out=out)

def derive_video_out(image_path: str) -> str:
    p = Path(image_path)
    return str(p.with_suffix(".mp4"))

def process_videos_from_excel():
    rows = read_jobs_from_excel_for_videos()
    for job in rows:
        row_idx  = job["row"]
        image    = job["image"]
        video_out = derive_video_out(image)
        cmd_tpl  = job["video_cmd"] or ""
        cmd      = (cmd_tpl if cmd_tpl.strip() else build_default_cmd(image, video_out))
        # Replace common placeholders
        cmd = (cmd
               .replace("{image}", image)
               .replace("{out}", video_out))

        try:
            run_shell(cmd)
            write_video_result(row_idx, str(Path(video_out).resolve()), account_id_used=VIDEO_ACCOUNT_ID, status="ok")
            print(f"[videos] Row {row_idx} -> {video_out}")
        except Exception as e:
            write_video_result(row_idx, "", account_id_used=VIDEO_ACCOUNT_ID, status=f"error: {e}")
            print(f"[videos] Row {row_idx} ERROR: {e}")

# =========================
# Coordinator
# =========================

async def main_async_videos():
    # refuse duplicate profiles
    profiles = [acc["profile"] for acc in META_ACCOUNTS]
    dupes = {p for p in profiles if profiles.count(p) > 1}
    if dupes:
        raise RuntimeError(f"Duplicate Chrome profiles in ACCOUNTS: {dupes}")

    # read Excel rows (prompt + empty image_path)
    all_rows = read_jobs_from_excel_for_videos()
    if not all_rows:
        print("No rows need videos.")
        return

    # optional shuffle
    if SHUFFLE_PROMPTS:
        random.shuffle(all_rows)

    # partition rows per account:
    # if account_id present in Excel, bind to that account; else round-robin
    rows_per_account: Dict[str, List[Dict]] = {a["id"]: [] for a in META_ACCOUNTS}
    free_rows = []
    for r in all_rows:
        acct = r.get("account_id", "")
        if acct and acct in rows_per_account:
            rows_per_account[acct].append(r)
        else:
            free_rows.append(r)
    # round-robin free rows
    acc_ids = list(rows_per_account.keys())
    k = 0
    for r in free_rows:
        rows_per_account[acc_ids[k % len(acc_ids)]].append(r)
        k += 1

    # prune empties and limit per account if desired
    jobs = []
    for acc in META_ACCOUNTS:
        bucket = rows_per_account[acc["id"]]
        if MAX_META_VID_PROMPTS_PER_ACCOUNT:
            bucket = bucket[:MAX_META_VID_PROMPTS_PER_ACCOUNT]
        if bucket:
            jobs.append((acc, bucket))

    async with async_playwright() as pw:
        await asyncio.gather(*[run_account_videos(pw, acc, bucket) for acc, bucket in jobs])



async def main_async_images():
    # refuse duplicate profiles
    profiles = [acc["profile"] for acc in ACCOUNTS]
    dupes = {p for p in profiles if profiles.count(p) > 1}
    if dupes:
        raise RuntimeError(f"Duplicate Chrome profiles in ACCOUNTS: {dupes}")

    # read Excel rows (prompt + empty image_path)
    all_rows = read_jobs_from_excel_for_images()
    if not all_rows:
        print("No rows need images.")
        return

    # optional shuffle
    if SHUFFLE_PROMPTS:
        random.shuffle(all_rows)

    # partition rows per account:
    # if account_id present in Excel, bind to that account; else round-robin
    rows_per_account: Dict[str, List[Dict]] = {a["id"]: [] for a in ACCOUNTS}
    free_rows = []
    for r in all_rows:
        acct = r.get("account_id", "")
        if acct and acct in rows_per_account:
            rows_per_account[acct].append(r)
        else:
            free_rows.append(r)
    # round-robin free rows
    acc_ids = list(rows_per_account.keys())
    k = 0
    for r in free_rows:
        rows_per_account[acc_ids[k % len(acc_ids)]].append(r)
        k += 1

    # prune empties and limit per account if desired
    jobs = []
    for acc in ACCOUNTS:
        bucket = rows_per_account[acc["id"]]
        if MAX_GGL_IMG_PROMPTS_PER_ACCOUNT:
            bucket = bucket[:MAX_GGL_IMG_PROMPTS_PER_ACCOUNT]
        if bucket:
            jobs.append((acc, bucket))

    async with async_playwright() as pw:
        await asyncio.gather(*[run_account_images(pw, acc, bucket) for acc, bucket in jobs])

def createImages():
    asyncio.run(main_async_images())

def createVideos():
    asyncio.run(main_async_videos())

def main():
    if RUN_MODE.lower() == "images":
        asyncio.run(main_async_images())
    elif RUN_MODE.lower() == "videos":
        asyncio.run(main_async_videos())
        
        # process_videos_from_excel()
    else:
        raise SystemExit("RUN_MODE must be 'images' or 'videos'.")

if __name__ == "__main__":
    main()
