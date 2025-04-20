import json
import csv
import os
import time
from pathlib import Path
from datetime import datetime
from playwright.sync_api import sync_playwright

# DND - To Run
# python youtube_uploader.py

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
        # page.locator('img#img[alt*="Avatar image"]').wait_for(timeout=10000)
        # page.locator('img#img[alt*="Avatar image"]').click()

        print("Waiting for avatar button...")
        page.locator('#avatar-btn').wait_for(timeout=10000)
        page.locator('#avatar-btn').click()
        print("Avatar button clicked.")
        time.sleep(1)

        # Locate the element containing the text "Switch account" and click it
        print("Waiting for 'Switch account' text...")
        page.get_by_text("Switch account").click()
        print("'Switch account' clicked.")
        time.sleep(1)

        # Construct a CSS selector to find the channel title
        channel_selector = f"#contents ytd-account-item-renderer tp-yt-paper-icon-item yt-formatted-string#channel-title:has-text('{target_channel}')"

        print(f"Waiting for channel title element with selector: '{channel_selector}'")
        page.wait_for_selector(channel_selector, timeout=10000)
        channel_title_element = page.locator(channel_selector)
        print("Channel title element found.")

        # Get the parent tp-yt-paper-icon-item (the clickable area)
        channel_item = channel_title_element.locator("xpath=ancestor::tp-yt-paper-icon-item")

        # Scroll the parent element into view if necessary and then click
        print("Scrolling channel item into view...")
        channel_item.scroll_into_view_if_needed()
        print("Clicking channel item...")
        channel_item.click()
        print(f"Clicked on channel: {target_channel}")


        # found = False
        # for _ in range(5):
        #     accounts_popup = page.locator('yt-multi-page-menu-section-renderer')
        #     if accounts_popup.locator(f'tp-yt-paper-item:has-text("{target_channel}")').count() > 0:
        #         accounts_popup.locator(f'tp-yt-paper-item:has-text("{target_channel}")').click()
        #         found = True
        #         break
        #     page.mouse.wheel(0, 300)
        #     time.sleep(1)

        # if not found:
        #     raise Exception(f"Channel '{target_channel}' not found for switching.")
        
        time.sleep(3)  # Let the channel switch fully
    except Exception as e:
        print(f"Error switching channel: {e}")
        raise


def upload_video(page, video_info):
    page.goto(UPLOAD_URL)
    page.wait_for_load_state("networkidle")
    time.sleep(2)
    print("Calling switch_channel")
    switch_channel(page, video_info["channel_name"])

    page.locator('ytcp-button#create-icon').click()

    page.get_by_text("Upload video").click()

    # page.locator('#endpoint').wait_for(timeout=10000)
    # page.locator("#endpoint").click()


    # page.locator('tp-yt-paper-item[role="option"]:has-text("Upload videos")').wait_for(state="visible", timeout=10000)
    # page.locator('tp-yt-paper-item[role="option"]:has-text("Upload videos")').click()

    # Upload video file
    file_input = page.locator('input[type="file"]')
    file_input.set_input_files(os.path.abspath(video_info["video_path"]))

    # Fill Title
    # page.locator('textarea#title-textarea').wait_for(timeout=15000)
    # page.locator('textarea#title-textarea').fill(video_info["title"])


    page.get_by_label("Add a title that describes your video (type @ to mention a channel)").fill(video_info["title"])
    print("Title Entered")

    page.get_by_label("Tell viewers about your video (type @ to mention a channel)").fill(video_info["description"])
    print("Description Entered")

    time.sleep(2)
    # Add to Playlist
    if "playlist_name" in video_info and video_info["playlist_name"]:
        #page.locator('ytcp-button:has-text("Select playlist")').click()
        
        #page.locator('button:has-text("Select")').click()
        page.locator(".right-container.style-scope.ytcp-dropdown-trigger").click()
        time.sleep(2)
        page.get_by_text(video_info["playlist_name"]).locator("xpath=ancestor::label").click()
        #page.locator(f'div[role="checkbox"]:has-text("{video_info["playlist_name"]}")').click()
        page.locator('ytcp-button:has-text("Done")').click()
        print("Playlist selected")

    # Fill Description
    #page.locator('textarea#description-textarea').fill(video_info["description"])

    # Made for kids
    kids_flag = video_info.get("made_for_kids", False)
    if kids_flag:
        page.locator('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_MFK"]').click()
        #page.locator('tp-yt-paper-radio-button[name="made_for_kids"]').click()
        #page.get_by_role("radio", name="VIDEO_MADE_FOR_KIDS_MFK").click()
    else:
        page.locator('tp-yt-paper-radio-button[name="VIDEO_MADE_FOR_KIDS_NOT_MFK"]').click()
        #page.locator('tp-yt-paper-radio-button[name="not_for_kids"]').click()
        #page.get_by_role("radio", name="VIDEO_MADE_FOR_KIDS_NOT_MFK").click()

    print("Kids option entered")



    # Show More
    #page.locator('ytcp-button:has-text("Show more")').click()
    page.locator('button:has-text("Show more")').click()

    time.sleep(1)

    #page.get_by_role("radio", name="VIDEO_HAS_ALTERED_CONTENT_NO").click()
    page.locator('tp-yt-paper-radio-button[name="VIDEO_HAS_ALTERED_CONTENT_NO"]').click()
    print("Altered content option entered")

    # Add Tags
    tags = video_info.get("tags", [])
    if tags:
        tags_input = page.locator('input[placeholder="Add tag"]')
        # tags_input.fill(",".join(tags))
        truncated_tags = []
        current_length = 0

        for tag in tags:
            if current_length + len(tag) + (1 if truncated_tags else 0) <= 500:
                truncated_tags.append(tag)
                current_length += len(tag) + (1 if truncated_tags else 0)
            else:
                break  # Stop adding tags if the limit is reached

        if truncated_tags:
            tags_input.fill(",".join(truncated_tags))
            print(f"Entered {len(truncated_tags)} tags (limited to 500 characters).")
        else:
            print("No tags could be added within the 500 character limit.")

    # Add Thumbnail if available
    if "thumbnail_path" in video_info and video_info["thumbnail_path"]:
        thumbnail_input = page.locator('input#file-loader')
        thumbnail_input.set_input_files(os.path.abspath(video_info["thumbnail_path"]))
        time.sleep(1)


    # Next Steps
    for _ in range(3):
        page.locator('button:has-text("Next")').click()
        time.sleep(1)

    # Schedule or Publish
    if "schedule_date" in video_info and video_info["schedule_date"]:
        #page.locator('tp-yt-paper-radio-button[name="PRIVATE"]').click()
        
        #page.locator('ytcp-button:has-text("Schedule")').click()
        page.locator('#visibility-title:has-text("Schedule")').click()
        #page.locator(':contains-text("Select a date")').click()
        time.sleep(1)

        page.locator('ytcp-dropdown-trigger').click()

        #date_input = page.locator('input[label="Date"]')
        #date_input = page.locator('input.style-scope.tp-yt-paper-input')

        #date_input = page.locator('input[aria-labelledby="paper-input-label-5"]')
        #date_input.fill(video_info["schedule_date"])

        page.get_by_label('Enter date').get_by_label('').press('Control+a')
        page.get_by_label('Enter date').get_by_label('').fill(video_info["schedule_date"])

        page.locator('tp-yt-iron-overlay-backdrop').nth(2).click();

        page.locator('ytcp-button:has-text("Schedule")').click()
    else:
        page.locator('tp-yt-paper-radio-button[name="PUBLIC"]').click()
        page.locator('ytcp-button:has-text("Publish")').click()

    # Get video URL
    time.sleep(5)
    try:
        video_link = page.locator('a.ytcp-video-info').get_attribute('href')
        if video_link:
            #full_url = f"https://www.youtube.com{video_link}"
            return video_link
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
            args=["--disable-blink-features=AutomationControlled", "--start-maximized"],
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
