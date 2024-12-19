import requests
from bs4 import BeautifulSoup

def scrape_page_chatgpt(url):
    """
    Scrapes text and images from a webpage, avoiding duplicates caused by nested 'paragraph2-desc' blocks.

    Args:
        url (str): The webpage URL.

    Returns:
        list of tuples: Extracted text and image URL pairs.
    """    
    print("Received scrape_page Arguments:", locals())
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Failed to fetch page, status code: {response.status_code}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")

    text_image_pairs = []
    current_text = ""
    last_image_url = None
    
    # Track processed blocks by their memory reference
    processed_blocks = set()

    # Extract only top-level content blocks
    content_blocks = soup.select("div.paragraph2-desc")
    print(f"Found {len(content_blocks)} content blocks")

    for block in content_blocks:
        if block in processed_blocks:
            print(f"Skipping already processed block with id {block.get('id', 'No ID')}")
            continue

        processed_blocks.add(block)
        print(f"Processing block with id {block.get('id', 'No ID')}")

        # Collect text and images
        for element in block.descendants:
            if element.name == "p" or isinstance(element, str):
                text_content = element.get_text(strip=True) if element.name == "p" else element.strip()
                if text_content:
                    current_text += " " + text_content
                    print(f"Collected text: {current_text.strip()}")

            elif element.name == "img" and "movieImageCls" in element.get("class", []):
                last_image_url = element["src"]
                print(f"Found image: {last_image_url}")

                # Save pair if text exists
                if current_text.strip():
                    text_image_pairs.append((current_text.strip(), last_image_url))
                    print(f"Pair added: Text: {current_text.strip()} | Image: {last_image_url}")
                    current_text = ""  # Reset text after pairing

    # Handle any remaining text without an image
    if current_text.strip():
        text_image_pairs.append((current_text.strip(), last_image_url))
        print(f"Final pair added: Text: {current_text.strip()} | Image: {last_image_url}")

    print("Completed processing")
    return text_image_pairs

#From Gemini - https://gemini.google.com/app/f86d38e806049040
def scrape_page(url):
    """
    Scrapes text and images from a given webpage URL.

    Args:
        url (str): The webpage URL.

    Returns:
        list of tuples: Each tuple contains extracted text and image URL pairs.
    """
    # Scrape the page
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")

    # Extract text-image pairs
    text_image_pairs = []
    current_text = ""
    last_image_url = None

    # Loop through all elements within "songLyrics" div
    for element in soup.select_one(".songLyrics").descendants:
        # Skip irrelevant elements (script, styles, etc.)
        if element.name in ("script", "style", "p"):
            continue

        # Collect text from text nodes
        if isinstance(element, str) and element.strip():
            current_text += " " + element.strip()

        # Collect images from <img class="movieImageCls">
        elif element.name == "img" and "movieImageCls" in element.get("class", []):
            last_image_url = element["src"]

            # Save text-image pair if text and image exist
            if current_text.strip() and last_image_url:
                text_image_pairs.append((current_text.strip(), last_image_url))
                current_text = ""  # Reset text after pairing

    # Handle remaining text if no image follows
    if current_text.strip():
        text_image_pairs.append((current_text.strip(), last_image_url))

    return text_image_pairs