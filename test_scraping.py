import requests
from bs4 import BeautifulSoup
import unittest
from model_scraper import scrape_page


#results = scrape_page("https://readernook.com/topics/amazing-short-stories/bruce-and-the-spider")
#results = scrape_page("https://readernook.com/topics/amazing-short-stories/pineo-and-the-miracle-of-wood")
results = scrape_page("https://readernook.com/topics/amazing-short-stories/mr-bear-and-honey​​")
for idx, (text, img) in enumerate(results):
    print(f"Text{idx}: {text}\nImage: {img}\n")


