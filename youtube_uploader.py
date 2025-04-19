import json
import csv
import os
import time
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

UPLOAD_URL = "https://studio.youtube.com"

PROFILE_DIR = "C:\\Users\\mail2\\AppData\\Local\\Google\\Chrome\\User Data\\Profile 1"
CHROME_EXECUTABLE = "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"

INPUT_JSON = "upload_config.json"
UPLOAD_LOG = "upload_log.csv"


def load_videos():
    with open(INPUT_JSON, 'r', encoding='utf-8') as f:
        return json.load(f)


def init_csv():
    if not os.path.exists(UPLOAD_LOG):
        with open(UPLOAD_LOG, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['title', 'channel_name', 'video_url', 'status'])


def log_upload(title, channel_name, video_url, status):
    with open(UPLOAD_LOG, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([title, channel_name, video_url, status])


def switch_channel(page, target_channel):
    try:
        page.locator('img#img[alt*="Avatar image"]').wait_for(timeout=10000)
        page.locator('img#img[alt*="Avatar image"]').click()
        time.sleep(1)

        found = False
        for _ in range(5):
            accounts_popup = page.locator('yt-multi-page-menu-section-renderer')
            if accounts_popup.locator(f'tp-yt-paper-item:has-text("{target_channel}")').count() > 0:
                accounts_popup.locator(f'tp-yt-paper-item:has-text("{target_channel}")').click()
                found = True
                break
            page.mouse.wheel(0, 300)
            time.sleep(1)

        if not found:
            raise Exception(f"Channel '{target_channel}' not found for switching.")
        
        time.sleep(3)  # Let the channel switch fully
    except Exception as e:
        print(f"Error switching channel: {e}")
        raise


def upload_video(page, video_info):
    page.goto(UPLOAD_URL)
    page.wait_for_load_state("networkidle")
    time.sleep(2)

    switch_channel(page, video_info["channel_name"])

    page.locator('ytcp-button#create-icon').click()
    page.locator('tp-yt-paper-item[role="option"]:has-text("Upload videos")').wait_for(state="visible", timeout=10000)
    page.locator('tp-yt-paper-item[role="option"]:has-text("Upload videos")').click()

    # Upload video file
    file_input = page.locator('input[type="file"]')
    file_input.set_input_files(os.path.abspath(video_info["video_path"]))

    # Fill Title
    page.locator('textarea#title-textarea').wait_for(timeout=15000)
    page.locator('textarea#title-textarea').fill(video_info["title"])

    # Fill Description
    page.locator('textarea#description-textarea').fill(video_info["description"])

    # Made for kids
    kids_flag = video_info.get("made_for_kids", False)
    if kids_flag:
        page.locator('tp-yt-paper-radio-button[name="made_for_kids"]').click()
    else:
        page.locator('tp-yt-paper-radio-button[name="not_for_kids"]').click()

    # Show More
    page.locator('ytcp-button:has-text("Show more")').click()
    time.sleep(1)

    # Add Tags
    tags = video_info.get("tags", [])
    if tags:
        tags_input = page.locator('input[placeholder="Add tags"]')
        tags_input.fill(",".join(tags))

    # Add Thumbnail if available
    if "thumbnail_path" in video_info and video_info["thumbnail_path"]:
        thumbnail_input = page.locator('input#file-loader')
        thumbnail_input.set_input_files(os.path.abspath(video_info["thumbnail_path"]))
        time.sleep(1)

    # Add to Playlist
    if "playlist_name" in video_info and video_info["playlist_name"]:
        page.locator('ytcp-button:has-text("Select playlist")').click()
        page.locator(f'div[role="checkbox"]:has-text("{video_info["playlist_name"]}")').click()
        page.locator('ytcp-button:has-text("Done")').click()

    # Next Steps
    for _ in range(3):
        page.locator('ytcp-button:has-text("Next")').click()
        time.sleep(1)

    # Schedule or Publish
    if "schedule_date" in video_info and video_info["schedule_date"]:
        page.locator('tp-yt-paper-radio-button[name="PRIVATE"]').click()
        page.locator('ytcp-button:has-text("Schedule")').click()
        date_input = page.locator('input[label="Date"]')
        date_input.fill(video_info["schedule_date"])
        page.locator('ytcp-button:has-text("Schedule")').click()
    else:
        page.locator('tp-yt-paper-radio-button[name="PUBLIC"]').click()
        page.locator('ytcp-button:has-text("Publish")').click()

    # Get video URL
    time.sleep(5)
    try:
        video_link = page.locator('a.ytcp-video-info').get_attribute('href')
        if video_link:
            full_url = f"https://www.youtube.com{video_link}"
            return full_url
    except:
        pass

    return "Unknown"


def main():
    videos = load_videos()
    init_csv()

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            PROFILE_DIR,
            headless=False,
            executable_path=CHROME_EXECUTABLE,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = browser.new_page()
        #page.set_viewport_size({"width": 1920, "height": 1080})

        # Hide automation fingerprint
        page.add_init_script("""Object.defineProperty(navigator, 'webdriver', {get: () => undefined})""")

        for video in videos:
            try:
                print(f"\n=== Uploading: {video['title']} to {video['channel_name']} ===")
                video_url = upload_video(page, video)
                print(f"Uploaded successfully: {video_url}")
                log_upload(video["title"], video["channel_name"], video_url, "Success")
            except Exception as e:
                print(f"Error uploading {video['title']}: {e}")
                log_upload(video["title"], video["channel_name"], "", "Failed")

        browser.close()


if __name__ == "__main__":
    main()
