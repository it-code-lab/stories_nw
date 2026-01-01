import os
import re
import time
from pathlib import Path
from datetime import datetime

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeoutError

# ---------- CONFIG ----------
CHROME_EXECUTABLE = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
STORAGE_STATE = "heygen_state.json"
HEADLESS = False

HOME_URL = "https://app.heygen.com/home"
NAV_TIMEOUT = 120_000
UI_TIMEOUT = 30_000

DOWNLOAD_DIR = Path("heygen_downloads").resolve()
MAX_ITEMS_PER_RUN = 80
SLEEP_BETWEEN = 1.0

# Home card selector (from your HTML earlier)
# CARD_SEL = "div.tw-cursor-pointer.tw-group.tw-relative"
# CARD_SEL = "div.tw-pointer-events-none.tw-absolute"
# CARD_SEL = "div[class*='ProjectCard_container']"
# CARD_SEL = "div.tw-group.tw-cursor-pointer"
# CARD_SEL = "div.tw-relative.tw-min-w-\\[280px\\]"
# CARD_SEL = 'div[class*="tw-min-w-[280px]"]'


CARD_SEL = "img.tw-size-full.tw-object-contain"
# CARD_SEL = "a[href*='/share/']"

# Landing page actions (from your recording)
DOWNLOAD_BTN_ROLE = ("button", "Download")
CLOSE_BTN_ROLE = ("button", "Close")

# The “More” button you recorded: getByRole('button').filter({ hasText: /^$/ }).nth(1)
# We'll use a safer heuristic: a top-right icon-only button in the action bar.
ICON_ONLY_BUTTONS_SEL = "button:has(svg)"

# Trash menu item
TRASH_TEXT = "Trash"


# ---------- HELPERS ----------
def safe_filename(name: str) -> str:
    name = (name or "").strip()
    name = re.sub(r'[<>:"/\\|?*\x00-\x1F]+', "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:180] or "heygen_video"


def ensure_logged_in(page, context):
    if "login" in page.url.lower():
        print("\n⚠️ Session expired. Please login in the opened browser.")
        print("After you reach HeyGen Home, press ENTER here...")
        input()
        context.storage_state(path=STORAGE_STATE)
        print(f"✅ Updated storage_state: {STORAGE_STATE}")
        page.goto(HOME_URL, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)

def click_card_and_wait_for_navigation(page, card, home_url: str) -> bool:
    try:
        # 1. Get the title of the video before clicking (for logging)
        title_element = card.locator("span.tw-truncate.tw-text-textTitle").first
        title = title_element.inner_text() if title_element.is_visible() else "Unknown Video"
        print(f"🎬 Attempting to open: {title}")

        # 2. Click the card using the middle area to avoid clicking the 'Edit' or 'More' icons
        card.scroll_into_view_if_needed()
        card.click(force=True, position={'x': 100, 'y': 100}) 

        # 3. Wait for the URL to change away from home
        page.wait_for_url(lambda url: "home" not in url.lower(), timeout=10000)
        return True
    except Exception as e:
        print(f"❌ Failed to navigate: {e}")
        return False
    
def click_card_and_wait_for_navigation_old2(page, card, home_url: str) -> bool:
    before = page.url
    
    # Ensure the card is in the viewport and stable
    card.scroll_into_view_if_needed()
    page.wait_for_timeout(500) 
    
    # force=True bypasses the "intercepts pointer events" check
    # that caused your specific TimeoutError
    card.click(force=True)

    try:
        # Give the SPA a moment to change the URL
        for _ in range(15):
            if page.url != before and "home" not in page.url.lower():
                return True
            page.wait_for_timeout(200)
        return False
    except Exception:
        return False

def click_card_and_wait_for_navigation_old(page, card, home_url: str) -> bool:
    """
    Click a card.
    If it navigates away from home (landing page), return True.
    If it stays on home (likely still processing), return False.
    """
    before = page.url
    card.scroll_into_view_if_needed()
    # card.click()

    # Add force=True to bypass the "intercepts pointer events" error
    card.click(force=True)

    # Wait briefly for URL change or some navigation
    try:
        page.wait_for_timeout(700)
        # Give SPA a moment to update route
        for _ in range(10):
            if page.url != before and "home" not in page.url.lower():
                return True
            page.wait_for_timeout(150)
        # If still home, treat as not navigated
        return False
    except Exception:
        return False
    
def scroll_to_bottom(page):
    print("📜 Scrolling to load all videos...")
    last_height = page.evaluate("document.body.scrollHeight")
    while True:
        page.mouse.wheel(0, 2000) # Scroll down
        page.wait_for_timeout(1000) # Wait for lazy load
        new_height = page.evaluate("document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
    print("✅ All videos loaded.")

def landing_download(page) -> str:
    """
    Click Download on landing page and save file.
    Uses browser download event.
    """
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # Click Download (your recording: getByRole('button', { name: 'Download' }))
    # page.get_by_role(*DOWNLOAD_BTN_ROLE).click(timeout=UI_TIMEOUT)

    role, name = DOWNLOAD_BTN_ROLE
    download_btn = page.get_by_role(role, name=re.compile(name, re.I))    

    download_btn.click(timeout=UI_TIMEOUT)


    # In some UIs, clicking Download immediately triggers download; in others there's a dialog.
    # We'll wait for download event around a "Download" button click if it appears, otherwise
    # we just wait for download.
    try:
        # If a dialog appears with another Download button, click it while expecting download
        dl_btn = page.get_by_role("button", name="Download")
        with page.expect_download(timeout=180_000) as dl_info:
            dl_btn.click(timeout=UI_TIMEOUT)
        dl = dl_info.value
    except Exception:
        # Otherwise, just expect a download without the second click
        with page.expect_download(timeout=180_000) as dl_info:
            # Some flows trigger download already after first click
            page.wait_for_timeout(500)
        dl = dl_info.value

    suggested = dl.suggested_filename or "heygen_video.mp4"
    final_path = DOWNLOAD_DIR / safe_filename(suggested)
    dl.save_as(str(final_path))

    # Close dialog (your recording has Close)
    print("Closing download dialog...")
    try:
        page.get_by_role("button", name="Close").click(timeout=5000)
    except Exception:
        print("⚠️ Close button not found; continuing...")
        pass

    return str(final_path)

def open_more_menu_and_trash(page):
    print("🔘 Opening 'More' menu...")
    
    # 1. Target the button via its data attribute
    more_btn = page.locator('button[data-more-btn="true"]').first
    more_btn.scroll_into_view_if_needed()
    more_btn.click(force=True)
    
    # 2. Wait for the menu to appear in the DOM
    # We wait for the 'data-state' to change to 'open'
    try:
        page.wait_for_selector('button[data-state="open"]', timeout=3000)
    except:
        # Fallback: simple timeout if the state attribute doesn't update immediately
        page.wait_for_timeout(500)

    # 3. Find and click Trash
    # We use a filter to ensure we get the visible menu item
    trash_item = page.get_by_text("Trash", exact=True).first
    trash_item.wait_for(state="visible", timeout=5000)
    trash_item.click()

    # 4. Handle the Confirmation Dialog
    # Usually, a secondary "Trash" or "Confirm" button appears in a modal
    # confirm_btn = page.get_by_role("button", name=re.compile("Trash|Confirm|Delete", re.I))
    # confirm_btn.wait_for(state="visible", timeout=5000)
    # confirm_btn.click(force=True)
    
    print("🗑️ Item moved to trash.")

def open_more_menu_and_trash_old3(page):
    # Use the specific icon name found in your HTML [cite: 20, 21]
    more_btn = page.locator("button:has(iconpark-icon[name='more-level'])").first
    more_btn.click(force=True)
    
    # Wait for the menu to actually appear in the DOM
    page.wait_for_selector("div[role='menu'], div[data-state='open']", timeout=5000)

    # Use a more reliable way to find 'Download' and 'Trash'
    # Download first
    # try:
    #     page.get_by_text("Download", exact=False).click(timeout=3000)
    #     print("✅ Download started")
    #     # Wait for download to trigger before trashing
    #     page.wait_for_timeout(2000) 
    # except:
    #     print("⚠️ Download button not found")

    # Re-open menu for Trash if it closed
    if not page.get_by_text("Trash", exact=False).is_visible():
        more_btn.click(force=True)

    page.get_by_text("Trash", exact=False).click(force=True)
    
    # Confirm deletion
    confirm_btn = page.get_by_role("button", name=re.compile("Trash|Confirm|Delete", re.I))
    confirm_btn.click(force=True)
    print("🗑️ Moved to trash")

def open_more_menu_and_trash_old2(page):
    # This specifically targets the "three dots" icon button based on your HTML
    try:
        # Target the button containing the 'more-level' icon
        more_btn = page.locator("button:has(iconpark-icon[name='more-level'])").first
        more_btn.click(timeout=UI_TIMEOUT, force=True)
    except Exception:
        # Fallback to your existing logic if the specific selector fails
        btn = page.get_by_role("button").filter(has_text=re.compile(r"^$")).nth(1)
        btn.click(timeout=UI_TIMEOUT, force=True)

    # Click Trash in the opened menu
    page.get_by_text(TRASH_TEXT, exact=True).click(timeout=UI_TIMEOUT)

    # Confirm Trash
    for btn_name in ["Trash", "Confirm", "Move to Trash", "Delete"]:
        try:
            # Added force=True here as well to avoid interception
            b = page.get_by_role("button", name=btn_name)
            b.wait_for(state="visible", timeout=1500)
            b.click(timeout=3000, force=True)
            break
        except Exception:
            pass

def open_more_menu_and_trash_old(page):
    """
    Open the more/options menu on landing page and click Trash.
    Recording:
      - click icon-only role button nth(1)
      - click Trash text
    We'll pick an icon-only button in the top action area.
    """
    # Try to click the 2nd icon-only button as in your recording
    try:
        btn = page.get_by_role("button").filter(has_text=re.compile(r"^$")).nth(1)
        btn.click(timeout=UI_TIMEOUT)
    except Exception:
        # Fallback: click a likely "more" icon button (one of the svg buttons)
        svg_btns = page.locator(ICON_ONLY_BUTTONS_SEL)
        if svg_btns.count() == 0:
            raise RuntimeError("Could not find any icon-only buttons for the menu.")
        # Often the more menu is near the top-right; nth(1) is a decent heuristic
        svg_btns.nth(1 if svg_btns.count() > 1 else 0).click(timeout=UI_TIMEOUT)

    # Click Trash in the opened menu
    # Your recording: locator('div').filter({ hasText: /^Trash$/ }).first().click();
    # We'll do exact text click.
    page.get_by_text(TRASH_TEXT, exact=True).click(timeout=UI_TIMEOUT)

    # Optional confirm
    for btn_name in ["Trash", "Confirm", "Move to Trash", "Delete"]:
        try:
            b = page.get_by_role("button", name=btn_name)
            b.wait_for(state="visible", timeout=1500)
            b.click(timeout=3000)
            break
        except Exception:
            pass


def wait_back_to_home(page):
    # After trash, HeyGen often redirects to home.
    try:
        page.wait_for_url(re.compile(r".*/home.*"), timeout=30_000)
    except Exception:
        # fallback: try navigating home
        page.goto(HOME_URL, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)


def main():
    if not os.path.exists(STORAGE_STATE):
        raise FileNotFoundError(
            f"{STORAGE_STATE} not found.\n"
            "Create it once via your login bootstrap method."
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

        

        downloaded = 0
        skipped_processing = 0
        errors = 0
        processed = 0

        # wait for locator(CARD_SEL) to be visible
        # page.locator(CARD_SEL).first.wait_for(state="visible", timeout=UI_TIMEOUT)

        # In main() before the while loop
        # Wait for the main content to load by waiting for the cards themselves

        while processed < MAX_ITEMS_PER_RUN:

            page.goto(HOME_URL, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)

            try:
                page.locator(CARD_SEL).first.wait_for(state="visible", timeout=UI_TIMEOUT)
            except Exception:
                print("⚠️  Warning: Cards did not appear within 15s, proceeding anyway...")
                break

            # page.wait_for_timeout(2000) # Give the UI a moment to settle
            # scroll_to_bottom(page)

            # Re-query cards every loop because list changes after deletion
            # cards = page.locator(CARD_SEL)
            # cards = page.locator(CARD_SEL).all()

            # if not cards:
            #         print("🏁 No more videos found.")
            #         break
                    
            # Always process the FIRST card because the previous one was deleted
            # card = cards[0]

            card = page.locator(CARD_SEL).first

            # total = cards.count()
            # if total == 0:
            #     print("No video cards found on Home.")
            #     break
            # else:
            #     print(f"\n🏷️  Processing item {processed + 1} of max {MAX_ITEMS_PER_RUN} "
            #           f"(cards available: {total})")

            # # Work from the top card each time
            # card = cards.nth(0)

            # Try open landing page; if not navigated, skip and move down
            navigated = click_card_and_wait_for_navigation(page, card, HOME_URL)
            if not navigated:
                skipped_processing += 1
                processed += 1
                # Scroll down a bit to avoid hitting same processing card repeatedly
                page.mouse.wheel(0, 420)
                continue

            ensure_logged_in(page, context)

            try:
                print("Navigated to video page. ⬇️ Downloading video...")
                saved = landing_download(page)
                print(f"✅ Downloaded: {saved}")
                downloaded += 1

                open_more_menu_and_trash(page)
                print("🗑️ Trashed from landing page.")

                # wait_back_to_home(page)
                # ensure_logged_in(page, context)

                processed += 1
                time.sleep(SLEEP_BETWEEN)

            except Exception as e:
                errors += 1
                print(f"❌ Error on landing page: {e}")
                # Try to go back home to recover
                try:
                    page.goto(HOME_URL, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
                    ensure_logged_in(page, context)
                except Exception:
                    pass
                processed += 1
                time.sleep(0.8)

        print(
            f"\nDone. Downloaded={downloaded}, "
            f"Skipped(processing/not-openable)={skipped_processing}, "
            f"Errors={errors}, Processed={processed}"
        )
        browser.close()


if __name__ == "__main__":
    main()
