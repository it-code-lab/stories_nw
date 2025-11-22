import os
import time
import json
import requests
import pandas as pd
from bs4 import BeautifulSoup

from gemini_pool import GeminiPool  # your existing helper

# ==============================
# CONFIG
# ==============================

INPUT_EXCEL  = "pages_input.xlsx"          # your input file
OUTPUT_EXCEL = "pages_with_meta.xlsx"      # output with meta columns
URL_COLUMN   = "url"                       # column name in Excel
TITLE_COLUMN = "title"                     # column name in Excel (optional but recommended)

# Model & generation settings
DEFAULT_MODEL        = "gemini-2.0-flash"    # or whatever you use
DEFAULT_TEMPERATURE  = 0.2
DEFAULT_MAX_TOKENS   = 512

# Optional: set your Gemini API key here or via env var
# os.environ["GEMINI_API_KEY"] = "YOUR_KEY_HERE"

# GEM_STATE = ".gemini_pool_state.json"
# gemini_pool = GeminiPool(
#     api_keys=None,          # let GeminiPool load from env or its own config
#     per_key_rpm=25,
#     state_path=GEM_STATE,
#     autosave_every=3,
# )

SEO_SYSTEM_INSTRUCTION = """
You are an SEO assistant for a children's story / reading website (readernook.com).

Your job: given page content, generate SEO metadata.

Rules:
- meta_title: max 60 characters; include the main topic; engaging but not clickbait.
- meta_description: 140–155 characters; clear, natural sentence; highlight the main benefit of reading this page.
- meta_keywords: 5–10 short phrases, no duplicates, no keyword stuffing.
- og_title: similar to meta_title but can be slightly more emotional or curiosity-driven.
- og_description: similar to meta_description, but can be a bit warmer and more conversational.

Return STRICTLY valid JSON with this schema:

{
  "meta_title": "string",
  "meta_description": "string",
  "meta_keywords": ["kw1", "kw2", "kw3"],
  "og_title": "string",
  "og_description": "string"
}

Do not include any explanations, comments, or text outside the JSON.
"""

# ==============================
# HELPERS
# ==============================

def fetch_page_text(url: str) -> tuple[str, str]:
    """
    Fetch the page and return (title, text_snippet).
    text_snippet is truncated for token safety.
    """
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
    except Exception as e:
        print(f"[WARN] Failed to fetch {url}: {e}")
        return (None, "")

    soup = BeautifulSoup(resp.text, "html.parser")

    # Try HTML <title> as fallback
    html_title = None
    if soup.title and soup.title.string:
        html_title = soup.title.string.strip()

    # Very simple body text extraction – you can refine as needed
    paragraphs = [p.get_text(" ", strip=True) for p in soup.find_all("p")]
    body_text = " ".join(paragraphs)
    body_text = body_text.replace("\n", " ").strip()
    # Truncate to avoid super-long inputs
    body_text = body_text[:4000]

    return (html_title, body_text)


def build_page_prompt(url: str, title: str, content: str) -> str:
    return f"""
PAGE URL: {url}
PAGE TITLE: {title}

PAGE CONTENT (truncated):
{content}
"""


def call_gemini_for_meta(url: str, title: str, content: str) -> dict | None:
    """
    Use your GeminiPool.generate_text to get SEO meta.
    Returns dict or None if failed.
    """
    snippet = (content or "")[:4000]

    # Put SEO instructions inside the prompt instead of system_instruction
    prompt = f"""{SEO_SYSTEM_INSTRUCTION}

PAGE URL: {url}
PAGE TITLE: {title}

PAGE CONTENT (truncated):
{snippet}
"""

    try:
        raw = gemini_pool.generate_text(
            prompt=prompt,
            model=DEFAULT_MODEL,
            temperature=DEFAULT_TEMPERATURE,
            max_output_tokens=DEFAULT_MAX_TOKENS,
            # extra={}  # you can add config here if needed, but no system_instruction
        )
    except Exception as e:
        print(f"[ERROR] Gemini call failed for {url}: {e}")
        return None

    if not raw:
        print(f"[ERROR] Empty response for {url}")
        return None

    raw = raw.strip()

    # Defensive parsing: grab first {...} block, in case anything else sneaks in
    if not raw.startswith("{"):
        first = raw.find("{")
        last = raw.rfind("}")
        if first != -1 and last != -1 and last > first:
            raw = raw[first:last + 1]

    try:
        data = json.loads(raw)
        return data
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON parse failed for {url}: {e}")
        print("Raw response was:\n", raw[:500], "...\n")
        return None



# ==============================
# MAIN
# ==============================

def main():
    print(f"Reading input Excel: {INPUT_EXCEL}")
    df = pd.read_excel(INPUT_EXCEL)

    if URL_COLUMN not in df.columns:
        raise ValueError(f"Expected URL column '{URL_COLUMN}' not found in Excel.")

    # Ensure meta columns exist (will be filled)
    meta_cols = [
        "meta_title",
        "meta_description",
        "meta_keywords",
        "og_title",
        "og_description",
        "meta_error",  # to log errors per row
    ]
    for col in meta_cols:
        if col not in df.columns:
            df[col] = ""

    for idx, row in df.iterrows():
        url = str(row[URL_COLUMN]).strip()
        if not url or url.lower().startswith("nan"):
            print(f"[SKIP] Row {idx}: empty URL")
            continue

        # Skip if meta already exists (so you can re-run safely)
        if row.get("meta_title") and isinstance(row["meta_title"], str) and row["meta_title"].strip():
            print(f"[SKIP] Row {idx}: meta already present for {url}")
            continue

        print(f"\n[PROCESS] Row {idx}: {url}")

        # Title from Excel or fallback later
        excel_title = str(row[TITLE_COLUMN]).strip() if TITLE_COLUMN in df.columns and pd.notna(row[TITLE_COLUMN]) else None

        html_title, page_text = fetch_page_text(url)

        final_title = excel_title or html_title or url
        if not page_text:
            print(f"[WARN] No body text extracted for {url}; still sending title only.")
            page_text = final_title

        meta = call_gemini_for_meta(url, final_title, page_text)
        if not meta:
            df.at[idx, "meta_error"] = "Failed to generate meta"
            continue

        df.at[idx, "meta_title"]       = meta.get("meta_title", "")
        df.at[idx, "meta_description"] = meta.get("meta_description", "")
        # store keywords as comma-separated string
        kws = meta.get("meta_keywords", [])
        if isinstance(kws, list):
            df.at[idx, "meta_keywords"] = ", ".join([str(k).strip() for k in kws])
        else:
            df.at[idx, "meta_keywords"] = str(kws)

        df.at[idx, "og_title"]         = meta.get("og_title", "")
        df.at[idx, "og_description"]   = meta.get("og_description", "")
        df.at[idx, "meta_error"]       = ""

        print(f"[OK] {url}")
        print("      →", df.at[idx, "meta_title"])

        # Optional: tiny sleep to be gentle, GeminiPool already rate-limits
        time.sleep(0.2)

    print(f"\nWriting output Excel: {OUTPUT_EXCEL}")
    df.to_excel(OUTPUT_EXCEL, index=False)
    print("Done.")


if __name__ == "__main__":
    GEM_STATE = ".gemini_pool_state.json"
    # GEM_STATE = str((Path(__file__).resolve().parent / ".gemini_pool_state.json"))
    gemini_pool = GeminiPool(
    api_keys=None,          # let GeminiPool load from env or its own config
    per_key_rpm=25,
    state_path=GEM_STATE,
    autosave_every=3,
    )
    main()
