import json
import os
import time
from playwright.sync_api import sync_playwright

UPLOAD_URL = "https://studio.youtube.com"

# Helper: Convert "Yes"/"No" to True/False
def parse_kids_field(value):
    return str(value).strip().lower() == "yes"

# Helper: Login once manually and reuse the session
PROFILE_DIR = "C:\\Users\\mail2\\AppData\\Local\\Google\\Chrome\\User Data\\Profile 1"

def main():
    # Load videos
    with open('upload-config.json', 'r', encoding='utf-8') as f:
        videos = json.load(f)

    with sync_playwright() as p:
        # Persistent browser context
        #browser = p.chromium.launch_persistent_context(PROFILE_DIR, headless=False)
        browser = p.chromium.launch_persistent_context(
            PROFILE_DIR,
            headless=False,
            executable_path="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",  # <-- your real Chrome path
            args=[
                "--disable-blink-features=AutomationControlled",
            ]
        )
        page = browser.new_page()
        #page.set_viewport_size({"width": 1920, "height": 1080})
        # Override navigator.webdriver to false
        page.add_init_script(
            """Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"""
        )

        for video in videos:
            try:
                print(f"\n=== Uploading: {video['title']} to {video['channelName']} ===")
                page.goto(UPLOAD_URL)
                page.wait_for_load_state("networkidle")
                time.sleep(2)

                # Switch Channel
                switch_channel(page, video["channelName"])

                # Go to Upload
                time.sleep(2)
                # Click "Create" Button
                page.locator('ytcp-button#create-icon').click()

                # Wait for dropdown menu to appear fully
                upload_option = page.locator('tp-yt-paper-item[role="option"]:has-text("Upload videos")')

                upload_option.wait_for(state="visible", timeout=10000)  # Wait up to 10s until Upload videos is ready

                # Now click Upload videos
                upload_option.click()

                # Upload video
                time.sleep(2)
                file_input = page.locator('input[type="file"]')
                file_input.set_input_files(os.path.abspath(video["videoPath"]))

                # Fill Title and Description
                page.locator('textarea#title-textarea').fill(video["title"])
                page.locator('textarea#description-textarea').fill(video["description"])

                # Add Tags
                if video.get("tags"):
                    more_options = page.locator('tp-yt-paper-radio-button[name="not_for_kids"]')
                    more_options.scroll_into_view_if_needed()
                    page.locator('tp-yt-paper-radio-button[name="not_for_kids"]').click()
                    page.locator('ytcp-button:has-text("Show more")').click()
                    tags_input = page.locator('input[placeholder="Add tags"]')
                    tags_input.fill(",".join(video["tags"]))

                # Made for kids
                kids = parse_kids_field(video.get("made for kids", "No"))
                if kids:
                    page.locator('tp-yt-paper-radio-button[name="made_for_kids"]').click()
                else:
                    page.locator('tp-yt-paper-radio-button[name="not_for_kids"]').click()

                # Add to Playlist
                if video.get("Playlist"):
                    page.locator('ytcp-button:has-text("Select playlist")').click()
                    page.locator(f'div[role="checkbox"]:has-text("{video["Playlist"]}")').click()
                    page.locator('ytcp-button:has-text("Done")').click()

                # Next Steps
                for _ in range(3):
                    page.locator('ytcp-button:has-text("Next")').click()
                    time.sleep(1)

                # Schedule or Publish
                if video.get("Schedule date"):
                    page.locator('tp-yt-paper-radio-button[name="PRIVATE"]').click()
                    page.locator('ytcp-button:has-text("Schedule")').click()
                    date_input = page.locator('input[label="Date"]')
                    date_input.fill(video["Schedule date"])
                    page.locator('ytcp-button:has-text("Schedule")').click()
                else:
                    page.locator('tp-yt-paper-radio-button[name="PUBLIC"]').click()
                    page.locator('ytcp-button:has-text("Publish")').click()

                # Wait for Video link
                print("Waiting for video link...")
                time.sleep(5)
                video_link = None
                try:
                    video_link = page.locator('a.ytcp-video-info').get_attribute('href')
                except:
                    pass

                if video_link:
                    print("Uploaded successfully:", video_link)
                    log_upload(video["title"], video_link)
                else:
                    print("Upload done but video link not found.")
                    log_upload(video["title"], "Link not captured.")

                # Small pause before next upload
                time.sleep(5)

            except Exception as e:
                print(f"Error uploading {video['title']}: {e}")
                log_upload(video["title"], "Upload Failed")

        browser.close()

def switch_channel(page, target_channel):
    try:
        page.locator('img#img[alt*="Account profile photo"]').click()
        time.sleep(2)

        accounts_popup = page.locator('yt-multi-page-menu-section-renderer')
        # Scroll down to find the target channel
        found = False
        for _ in range(5):
            if accounts_popup.locator(f'tp-yt-paper-item:has-text("{target_channel}")').count() > 0:
                accounts_popup.locator(f'tp-yt-paper-item:has-text("{target_channel}")').click()
                found = True
                break
            page.mouse.wheel(0, 200)  # Scroll down
            time.sleep(1)
        if not found:
            raise Exception(f"Channel {target_channel} not found during switching.")
        time.sleep(3)
    except Exception as e:
        print(f"Failed to switch channel: {e}")

def log_upload(title, link):
    with open('upload_log.txt', 'a', encoding='utf-8') as f:
        f.write(f"{title} --> {link}\n")

if __name__ == "__main__":
    main()
