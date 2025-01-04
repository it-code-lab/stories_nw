import requests
from bs4 import BeautifulSoup
import unittest
from effects import add_ken_burns_effect, add_ken_burns_effect_DND, add_zoom_effect
from model_scraper import scrape_page, scrape_story_page_with_soundeffect, scrape_page_sm, generate_audio, scrape_page_with_camera_frame, create_video_from_elements
#from scraper import scrape_page


#results = scrape_page("https://readernook.com/topics/amazing-short-stories/bruce-and-the-spider")
#results = scrape_page("https://readernook.com/topics/amazing-short-stories/pineo-and-the-miracle-of-wood")

#DND - Working
# results = scrape_page("https://readernook.com/topics/amazing-short-stories/the-greedy-dog-and-his-bone-test​​")
# for idx, (text, img) in enumerate(results):
#     print(f"Text{idx}: {text}\nImage: {img}\n")


#DND - Working
# url = "https://readernook.com/topics/amazing-short-stories/the-greedy-dog-and-his-bone-test"
# results = scrape_story_page_with_soundeffect(url)

# # Print results
# for idx, item in enumerate(results):
#     print(f"Element {idx + 1}:")
#     print(item)
#     print("-" * 50)

#DND - Working
# url = "https://readernook.com/topics/amazing-short-stories/the-greedy-dog-and-his-bone-test"
# results = scrape_page_sm(url)
# # Print results
# for idx, item in enumerate(results):
#     print(f"Element {idx + 1}:")
#     print(item)
#     print("-" * 50)

#DND - Working
# url = "https://readernook.com/topics/amazing-short-stories/the-greedy-dog-and-his-bone-test"
# results = scrape_page_sm(url)
# generate_audio(results, "final_output.mp3")

#DND - Working
# url = "https://readernook.com/topics/amazing-short-stories/the-greedy-dog-and-his-bone"
# results = scrape_page_sm(url)
# generate_audio(results, "final_output.mp3")

#DND - Working
# url = "https://readernook.com/topics/amazing-short-stories/the-greedy-dog-and-his-bone-test"
# results = scrape_page_with_camera_frame(url)
# # Print results
# for idx, item in enumerate(results):
#     print(f"Element {idx + 1}:")
#     print(item)
#     print("-" * 50)

#DND - Working
url = "https://readernook.com/topics/amazing-short-stories/The-Deceitful-Dog-and-the-Loyal-Fox-vid-reg"
results = scrape_page_with_camera_frame(url)
for idx, item in enumerate(results):
    print(f"Element {idx + 1}:")
    print(item)
    print("-" * 50)
create_video_from_elements(results, "final_output.mp4")


#DND - Working
#video_clip = add_ken_burns_effect_DND("cropped_frame.png", 10, 1.2, 1)
#video_clip.write_videofile("test.mp4", fps=24)