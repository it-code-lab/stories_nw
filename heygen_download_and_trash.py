import os
import re
import time
from pathlib import Path
from datetime import datetime

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

# ---------------- CONFIG ----------------
CHROME_EXECUTABLE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
STORAGE_STATE = "heygen_state.json"  # keep this in same folder or make absolute
HEADLESS = False

HOME_URL = "https://app.heygen.com/home"
NAV_TIMEOUT = 120_000
UI_TIMEOUT = 30_000

DOWNLOAD_DIR = Path("heygen_downloads").resolve()
MAX_ITEMS_PER_RUN = 50   # safety cap, change as you like
SLEEP_BETWEEN = 1.5      # gentle pacing


# ---------------- HELPERS ----------------

def safe_filename(name: str) -> str:
    name = (name or "").strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1F]+', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:160] or "heygen_video"


def ensure_logged_in(page, context):
    # If session expired, you will be redirected to login.
    if "login" in page.url.lower():
        print("\n⚠️ Login required. Please login in the opened browser window.")
        print("👉 After you land on HeyGen home/dashboard, press ENTER here...")
        input()
        context.storage_state(path=STORAGE_STATE)
        print(f"✅ Updated storage_state saved to: {STORAGE_STATE}")
        page.goto(HOME_URL, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)


def open_card_menu(card):
    """
    Each video card has a 3-dots menu button:
    <button ...><iconpark-icon name="more-level" ...></iconpark-icon></button>
    We'll hover the card to reveal it, then click it.
    """
    card.scroll_into_view_if_needed()
    card.hover()

    menu_btn = card.locator("button:has(iconpark-icon[name='more-level'])").first
    menu_btn.wait_for(state="visible", timeout=UI_TIMEOUT)
    menu_btn.click(timeout=UI_TIMEOUT)


def click_menu_item(page, label: str, timeout=UI_TIMEOUT) -> bool:
    """
    Click a menu item by visible text (Download/Trash/etc).
    Returns True if clicked, False if not found.
    """
    item = page.get_by_text(label, exact=True)
    try:
        item.wait_for(state="visible", timeout=1500)
        item.click(timeout=timeout)
        return True
    except Exception:
        return False


def try_download_from_open_menu(page, download_dir: Path) -> str | None:
    """
    Assumes menu is already open.
    If Download exists: click it -> click Download confirm -> save file.
    Returns saved file path, or None if Download not available.
    """
    # If processing, "Download" won't be there.
    if not click_menu_item(page, "Download"):
        return None

    # A dialog opens with a Download button
    # We expect a real browser download.
    try:
        download_dir.mkdir(parents=True, exist_ok=True)

        with page.expect_download(timeout=120_000) as dl_info:
            page.get_by_role("button", name="Download").click(timeout=UI_TIMEOUT)

        download = dl_info.value

        # Build a nice filename
        # suggested = download.suggested_filename or "heygen_video.mp4"
        # base = Path(suggested).stem
        # ext = Path(suggested).suffix or ".mp4"
        # ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        # final_name = f"{safe_filename(base)}_{ts}{ext}"
        # final_path = download_dir / final_name

        suggested = download.suggested_filename or "heygen_video.mp4"
        final_path = download_dir / safe_filename(suggested)


        download.save_as(str(final_path))

        # Close dialog (if present)
        try:
            page.get_by_role("button", name="Close").click(timeout=3000)
        except Exception:
            # sometimes dialog closes automatically after saving
            pass

        return str(final_path)

    except PWTimeoutError:
        raise RuntimeError("Download timed out (no download event).")
    except Exception as e:
        raise RuntimeError(f"Download failed: {e}")


def trash_from_open_menu(page):
    """
    Assumes menu is open. Click Trash. Some accounts show a confirm step;
    we handle both cases.
    """
    if not click_menu_item(page, "Trash"):
        raise RuntimeError("Trash option not found after download.")

    # Optional confirm
    # (If HeyGen shows a confirmation modal, one of these usually exists.)
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
            f"Storage state not found: {STORAGE_STATE}\n"
            "Create it once via your login bootstrap (storage_state)."
        )

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=HEADLESS,
            executable_path=CHROME_EXECUTABLE,
            args=["--start-maximized"],
        )

        context = browser.new_context(
            storage_state=STORAGE_STATE,
            accept_downloads=True,   # IMPORTANT
        )

        page = context.new_page()
        page.set_default_timeout(UI_TIMEOUT)
        
        page.goto(HOME_URL, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
        ensure_logged_in(page, context)

        # wait for UI to load
        page.wait_for_selector("button:has(iconpark-icon[name='more-level'])", timeout=NAV_TIMEOUT)

        # Heuristic: video cards commonly have the 3-dots menu icon inside.
        # We'll iterate over cards by finding menu buttons, then walking up to a reasonable container.
        menu_buttons = page.locator("button:has(iconpark-icon[name='more-level'])")
        count = menu_buttons.count()

        if count == 0:
            print("No menu buttons found on Home. UI may have changed or content not loaded.")
            browser.close()
            return

        print(f"Found {count} video menu buttons (cards). Will process up to {MAX_ITEMS_PER_RUN}.")

        processed = 0
        downloaded = 0
        skipped = 0

        # We re-query each time because UI changes after trashing.
        i = 0
        while processed < MAX_ITEMS_PER_RUN:
            menu_buttons = page.locator("button:has(iconpark-icon[name='more-level'])")
            count = menu_buttons.count()
            if i >= count:
                break

            btn = menu_buttons.nth(i)

            # pick a container “card” around the button
            # closest clickable container varies; we take a few parents up.
            card = btn.locator("xpath=ancestor::div[contains(@class,'tw-rounded')][1]")
            if card.count() == 0:
                # fallback: just use the button's parent card-ish div
                card = btn.locator("xpath=ancestor::div[1]")

            try:
                open_card_menu(card)

                saved_path = try_download_from_open_menu(page, DOWNLOAD_DIR)
                if not saved_path:
                    skipped += 1
                    processed += 1
                    i += 1
                    # close menu by clicking outside
                    page.mouse.click(10, 10)
                    continue

                downloaded += 1
                print(f"✅ Downloaded: {saved_path}")

                # After download dialog closes, open menu again and trash
                open_card_menu(card)
                trash_from_open_menu(page)
                print("🗑️ Trashed the video.")

                processed += 1

                # UI may reflow; do NOT increment i aggressively after trash
                # Re-start scanning from same index.
                time.sleep(SLEEP_BETWEEN)

            except Exception as e:
                print(f"❌ Error on item {i+1}: {e}")
                processed += 1
                i += 1
                time.sleep(1.0)

        print(f"\nDone. Downloaded={downloaded}, Skipped(processing/no-download)={skipped}, Processed={processed}")
        browser.close()


if __name__ == "__main__":
    main()
