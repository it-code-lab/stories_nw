import os
import time
from pathlib import Path
from datetime import datetime

from openpyxl import load_workbook
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError


# ================== CONFIG ==================
EXCEL_FILE = "heygen_submit_videos.xlsx"
SHEET_NAME = "Sheet1"

# Use a DEDICATED Chrome profile you already logged into HeyGen with
# (Same pattern as your Pinterest uploader)  :contentReference[oaicite:1]{index=1}
PROFILE_DIR = r"C:\Users\mail2\AppData\Local\Google\Chrome\User Data\Profile 21"
CHROME_EXECUTABLE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

HEADLESS = False

NAV_TIMEOUT = 120_000
UI_TIMEOUT = 60_000

# Excel columns required
COL_URL = "HeyGen_Template_url"
COL_TEXT = "story_text"
COL_NAME = "video_name"

# Status columns we maintain
COL_STATUS = "status"
COL_MESSAGE = "message"
COL_SUBMITTED_AT = "submitted_at"


# ================== HELPERS ==================

def norm(s) -> str:
    return ("" if s is None else str(s)).strip()


def is_excel_file_locked(file_path: str) -> bool:
    """Same style as your Pinterest script: try opening in append mode."""
    try:
        with open(file_path, "a"):
            pass
        return False
    except PermissionError:
        return True


def ensure_columns(ws, required_headers):
    """Ensure headers exist in row 1; create missing ones at the end."""
    headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
    headers = [norm(h) for h in headers]

    changed = False
    for h in required_headers:
        if h not in headers:
            ws.cell(row=1, column=len(headers) + 1, value=h)
            headers.append(h)
            changed = True

    colmap = {h: i + 1 for i, h in enumerate(headers)}  # 1-based
    return colmap, changed


def set_row_status(ws, colmap, row_idx, status, message=""):
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ws.cell(row=row_idx, column=colmap[COL_STATUS]).value = status
    ws.cell(row=row_idx, column=colmap[COL_MESSAGE]).value = message
    ws.cell(row=row_idx, column=colmap[COL_SUBMITTED_AT]).value = now_str


# ================== HEYGEN FLOW ==================

def _maybe_wait_for_login(page):
    """
    If HeyGen redirects to login, pause so user can login once in the Chrome profile.
    """
    if "login" in page.url.lower():
        print("⚠️ HeyGen login detected. Please login in the opened Chrome window.")
        print("   After you finish login, press ENTER here to continue...")
        input()


def click_any_text_editor(page):
    """
    Try multiple strategies to focus the main story text editor.
    HeyGen UI changes often; these fallbacks reduce flakiness.
    """
    # Strategy A: click on the "text" element used in your recording
    try:
        page.get_by_text("text", exact=True).click(timeout=10_000)
        return
    except Exception:
        pass

    # Strategy B: first visible contenteditable
    try:
        ce = page.locator("[contenteditable='true']").filter(has_not_text="").first
        # Some editors have empty text; prefer simply the first visible
        ce = page.locator("[contenteditable='true']").first
        ce.wait_for(state="visible", timeout=10_000)
        ce.click(timeout=10_000)
        return
    except Exception:
        pass

    # Strategy C: textarea
    try:
        ta = page.locator("textarea").first
        ta.wait_for(state="visible", timeout=10_000)
        ta.click(timeout=10_000)
        return
    except Exception:
        pass

    raise RuntimeError("Could not locate the story text editor (text/contenteditable/textarea).")


def fill_story_text(page, story_text: str):
    click_any_text_editor(page)

    # Replace text using keyboard (more robust than .fill() across editor types)
    page.keyboard.press("ControlOrMeta+A")
    page.keyboard.press("Backspace")
    page.keyboard.insert_text(story_text)


def click_generate(page):
    page.get_by_role("button", name="Generate").click(timeout=UI_TIMEOUT)

    # Minimal stabilization wait (UI can shift); keep small
    page.wait_for_timeout(800)


def rename_video(page, video_name: str):
    """
    Your recording uses: textbox name 'Untitled Video'.
    We'll try a few fallbacks in case the accessible name changes.
    """
    # Primary: recorded selector
    try:
        box = page.get_by_role("textbox", name="Untitled Video")
        box.click(timeout=10_000)
        box.press("ControlOrMeta+A")
        box.fill(video_name, timeout=10_000)
        return
    except Exception:
        pass

    # Fallback: any textbox currently showing Untitled
    try:
        box = page.locator('input[type="text"]').filter(has_text="").first
        # safer: search by value attribute containing "Untitled"
        box = page.locator('input[type="text"][value*="Untitled"]').first
        box.wait_for(state="visible", timeout=10_000)
        box.click(timeout=10_000)
        page.keyboard.press("ControlOrMeta+A")
        page.keyboard.insert_text(video_name)
        return
    except Exception:
        pass

    # Fallback: attempt common title placeholders
    for ph in ["Untitled Video", "Video title", "Title"]:
        try:
            box = page.get_by_placeholder(ph)
            box.wait_for(state="visible", timeout=5_000)
            box.click()
            box.press("ControlOrMeta+A")
            box.fill(video_name)
            return
        except Exception:
            continue

    raise RuntimeError("Could not find the video title textbox to rename.")


def click_submit(page):
    page.get_by_role("button", name="Submit").click(timeout=UI_TIMEOUT)
    page.wait_for_timeout(800)


def submit_one_bk(page, template_url: str, story_text: str, video_name: str):
    # page.goto(template_url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)

    page.goto("https://app.heygen.com/home")
    time.sleep(20000)  # wait for full UI load
    
    page.goto(template_url)

    # _maybe_wait_for_login(page)
    time.sleep(20000)  # wait for full UI load
    # In case it redirected after login
    if page.url != template_url and "create" not in page.url:
        page.goto(template_url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)

    fill_story_text(page, story_text)
    click_generate(page)
    rename_video(page, video_name)
    click_submit(page)

def submit_one(page, template_url: str, story_text: str, video_name: str):
    # Step 1: Go to home so login UI loads cleanly
    # page.goto("https://app.heygen.com/home", wait_until="domcontentloaded")
    # page.goto("https://www.google.com/")
    page.goto("https://app.heygen.com/home")
    
    print("👉 Please log in to HeyGen in the opened browser.")
    print("👉 Once you see the HeyGen dashboard, press ENTER here.")
    input()   # <-- safer than sleep

    # Step 2: Open the template
    # page.goto(template_url, wait_until="domcontentloaded")

    print("👉 Waiting for template editor to fully load.")
    print("👉 Once the editor is visible, press ENTER here.")
    input()

    # Step 3: Continue automation
    fill_story_text(page, story_text)
    click_generate(page)
    rename_video(page, video_name)
    click_submit(page)

# ================== MAIN ==================

def main():
    if not os.path.exists(EXCEL_FILE):
        print(f"❌ Excel file not found: {EXCEL_FILE}")
        return

    if is_excel_file_locked(EXCEL_FILE):
        print(f"❌ Please close '{EXCEL_FILE}' before running this script.")
        return

    wb = load_workbook(EXCEL_FILE)
    if SHEET_NAME not in wb.sheetnames:
        print(f"❌ Sheet '{SHEET_NAME}' not found in {EXCEL_FILE}")
        return
    ws = wb[SHEET_NAME]

    required_headers = [COL_URL, COL_TEXT, COL_NAME, COL_STATUS, COL_MESSAGE, COL_SUBMITTED_AT]
    colmap, changed = ensure_columns(ws, required_headers)
    if changed:
        wb.save(EXCEL_FILE)

    # Collect pending rows
    pending = []
    for r in range(2, ws.max_row + 1):
        url = norm(ws.cell(r, colmap[COL_URL]).value)
        story = ws.cell(r, colmap[COL_TEXT]).value
        name = norm(ws.cell(r, colmap[COL_NAME]).value)
        status = norm(ws.cell(r, colmap[COL_STATUS]).value).lower()

        if not url or not name or not norm(story):
            continue

        if status in ("success", "done"):
            continue

        pending.append((r, url, str(story), name))

    if not pending:
        print("✅ No pending rows found (everything is already Success/Done or incomplete).")
        return

    print(f"Loaded {len(pending)} pending rows from {EXCEL_FILE}")

    STORAGE_STATE = "heygen_state.json"
    CHROME_EXECUTABLE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, executable_path=CHROME_EXECUTABLE)
        context = browser.new_context()  # <-- incognito-style (fresh)
        page = context.new_page()

        page.goto("https://app.heygen.com/home", wait_until="domcontentloaded")
        print("Login manually, complete any verification, then press ENTER here...")
        input()

        # Save cookies/localStorage
        context.storage_state(path=STORAGE_STATE)
        print("Saved:", STORAGE_STATE)

        browser.close()
        return

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            PROFILE_DIR,
            headless=HEADLESS,
            executable_path=CHROME_EXECUTABLE,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ],
        )

        page = context.new_page()
        page.set_default_timeout(UI_TIMEOUT)

        # Hide automation fingerprint (same idea as your Pinterest script) :contentReference[oaicite:2]{index=2}
        page.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        for (row_idx, url, story_text, video_name) in pending:
            print(f"\n--- Row {row_idx}: {video_name} ---")
            try:
                set_row_status(ws, colmap, row_idx, "processing", "")
                wb.save(EXCEL_FILE)

                submit_one(page, url, story_text, video_name)

                set_row_status(ws, colmap, row_idx, "Success", "Submitted")
                wb.save(EXCEL_FILE)
                print(f"✅ Success: {video_name}")

                # Gentle pacing to reduce bot detection / UI race conditions
                time.sleep(2)

            except PWTimeoutError as te:
                msg = f"Timeout: {str(te)[:300]}"
                set_row_status(ws, colmap, row_idx, "Error", msg)
                wb.save(EXCEL_FILE)
                print(f"❌ {msg}")

            except Exception as e:
                msg = str(e)[:300]
                set_row_status(ws, colmap, row_idx, "Error", msg)
                wb.save(EXCEL_FILE)
                print(f"❌ Error: {msg}")

        context.close()

    print("\nAll done.")


if __name__ == "__main__":
    main()
