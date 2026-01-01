import os
import re
import time
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

CHROME_EXECUTABLE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
STORAGE_STATE = "heygen_state.json"
HEADLESS = False

HOME_URL = "https://app.heygen.com/home"
NAV_TIMEOUT = 120_000
UI_TIMEOUT = 30_000

DOWNLOAD_DIR = Path("heygen_downloads").resolve()
MAX_ITEMS_PER_RUN = 80
SLEEP_BETWEEN = 1.2

# --- selectors based on your full card HTML ---
CARD_SEL = "div.tw-cursor-pointer.tw-group.tw-relative"
HOVER_ACTIONS_SEL = "div.tw-pointer-events-auto.tw-absolute.tw-right-2.tw-top-2.tw-z-20"
MENU_BTN_SEL = "button[aria-haspopup='dialog']"
TITLE_SEL = "span.tw-flex-1.tw-min-w-0.tw-overflow-hidden.tw-text-ellipsis"

def safe_filename(name: str) -> str:
    name = (name or "").strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1F]+', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:180] or "heygen_video"

def ensure_logged_in(page, context):
    if "login" in page.url.lower():
        print("\n⚠️ HeyGen login required. Please login in the opened browser.")
        print("After you see HeyGen Home, press ENTER here...")
        input()
        context.storage_state(path=STORAGE_STATE)
        print(f"✅ Updated {STORAGE_STATE}")
        page.goto(HOME_URL, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)

def open_menu_for_card(card, page):
    """
    Hover card to reveal the top-right hover actions, then click menu (3 dots).
    """
    card.scroll_into_view_if_needed()
    card.hover()

    hover_actions = card.locator(HOVER_ACTIONS_SEL).first
    hover_actions.wait_for(state="visible", timeout=5000)

    menu_btn = hover_actions.locator(MENU_BTN_SEL).first
    menu_btn.wait_for(state="visible", timeout=5000)
    menu_btn.click(timeout=UI_TIMEOUT)

def menu_click(page, label: str) -> bool:
    try:
        page.get_by_text(label, exact=True).wait_for(state="visible", timeout=1500)
        page.get_by_text(label, exact=True).click(timeout=UI_TIMEOUT)
        return True
    except Exception:
        return False

def try_download_from_open_menu(page, title_for_logs: str | None = None) -> str | None:
    """
    Returns saved file path if downloadable, else None (likely still processing).
    """
    if not menu_click(page, "Download"):
        return None

    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    try:
        with page.expect_download(timeout=180_000) as dl_info:
            page.get_by_role("button", name="Download").click(timeout=UI_TIMEOUT)

        dl = dl_info.value
        suggested = dl.suggested_filename or "heygen_video.mp4"
        final_path = DOWNLOAD_DIR / safe_filename(suggested)
        dl.save_as(str(final_path))

        # close dialog if present
        try:
            page.get_by_role("button", name="Close").click(timeout=3000)
        except Exception:
            pass

        return str(final_path)
    except PWTimeoutError:
        raise RuntimeError(f"Download event timed out for: {title_for_logs or 'video'}")

def trash_from_open_menu(page):
    if not menu_click(page, "Trash"):
        raise RuntimeError("Trash option not found in menu.")

    # sometimes there's a confirm modal; handle common variations
    for btn_name in ["Trash", "Confirm", "Move to Trash", "Delete"]:
        try:
            b = page.get_by_role("button", name=btn_name)
            b.wait_for(state="visible", timeout=1500)
            b.click(timeout=3000)
            break
        except Exception:
            pass

def main():
    if not os.path.exists(STORAGE_STATE):
        raise FileNotFoundError(
            f"{STORAGE_STATE} not found in current folder.\n"
            "Run the login bootstrap once to create it."
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            executable_path=CHROME_EXECUTABLE,
            args=["--start-maximized"],
        )
        context = browser.new_context(storage_state=STORAGE_STATE, accept_downloads=True)
        page = context.new_page()
        page.set_default_timeout(UI_TIMEOUT)

        page.goto(HOME_URL, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
        ensure_logged_in(page, context)

        # Wait a moment for cards to render
        page.wait_for_timeout(1500)

        downloaded = 0
        skipped = 0
        processed = 0

        # IMPORTANT: re-query each loop because UI updates after trash
        while processed < MAX_ITEMS_PER_RUN:
            cards = page.locator(CARD_SEL)
            total = cards.count()
            if total == 0:
                print("No cards found. Are you on the Home page with Recent creations visible?")
                break

            # process from top each time; after trash, list shifts
            card = cards.nth(0)

            # extract title (for logs only)
            title = None
            try:
                title = card.locator(TITLE_SEL).first.inner_text(timeout=1500).strip()
            except Exception:
                title = "Untitled"

            try:
                open_menu_for_card(card, page)

                saved = try_download_from_open_menu(page, title_for_logs=title)
                if not saved:
                    skipped += 1
                    processed += 1
                    # close menu by clicking outside
                    page.mouse.click(10, 10)
                    # move to next card by scrolling a bit (otherwise we keep hitting same first card)
                    # since first card was not downloadable, skip it by scrolling it away slightly:
                    card.scroll_into_view_if_needed()
                    page.mouse.wheel(0, 350)
                    continue

                downloaded += 1
                processed += 1
                print(f"✅ Downloaded: {saved}  |  {title}")

                # trash it
                open_menu_for_card(card, page)
                trash_from_open_menu(page)
                print("🗑️ Trashed.")

                time.sleep(SLEEP_BETWEEN)

            except Exception as e:
                print(f"❌ Error on card '{title}': {e}")
                processed += 1
                time.sleep(0.8)
                # try to recover by clicking away
                try:
                    page.mouse.click(10, 10)
                except Exception:
                    pass

        print(f"\nDone. Downloaded={downloaded}, Skipped(no Download)={skipped}, Processed={processed}")
        browser.close()

if __name__ == "__main__":
    main()
