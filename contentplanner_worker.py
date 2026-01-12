import time
import requests
from pathlib import Path
from openpyxl import Workbook, load_workbook

BASE_URL = "https://contentplanner.readernook.com"  # adjust
TOKEN = "CHANGE_ME_TO_A_LONG_RANDOM_SECRET"

HEADERS = {"X-Worker-Token": TOKEN}

# where to store images locally (your pipeline folder)
OUT_DIR = Path(r"downloads")
OUT_DIR.mkdir(parents=True, exist_ok=True)

EXCEL_FILE = Path("media_jobs.xlsx")
SHEET_NAME = "Jobs"

UPLOADER_MASTER_FILE = "master_shorts_uploader_data.xlsx"
UPLOADER_START_ROW = 80  # write from here

# Columns expected by youtube_uploader.py (must exist)
UPLOADER_REQUIRED_COLS = [
    "media_file", "yt_title", "yt_description", "youtube_status", "youTubeChannel",
    "media_type", "future", "yt_playlist", "yt_schedule_date", "yt_tags",
    # optional but useful for linking back:
    "section_id"
]






HEYGEN_FILE = "heygen_submit_videos.xlsx"
HEYGEN_SHEET = "Sheet1"
HEYGEN_START_ROW = 10  # clear & write from row 10 onward

HEYGEN_REQUIRED_COLS = [
    "HeyGen_Template_url",
    "story_text",
    "video_name",
    "status",
    "message",
    "submitted_at",
]

def fetch_heygen_submit_jobs(topic_id: int, limit: int = 2000):
    r = requests.get(
        f"{BASE_URL}/api/worker_fetch_heygen_submit_jobs.php",
        params={"topic_id": topic_id, "limit": limit},
        headers=HEADERS,
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["items"]

def ensure_headers(ws, required_cols):
    headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
    headers = [h if h is not None else "" for h in headers]
    header_map = {h: i + 1 for i, h in enumerate(headers) if h}

    for col in required_cols:
        if col not in header_map:
            ws.cell(row=1, column=len(headers) + 1, value=col)
            headers.append(col)
            header_map[col] = len(headers)

    return header_map

def clear_rows_from(ws, max_col: int, start_row: int):
    # Clear values only (keep formatting)
    for r in range(start_row, ws.max_row + 1):
        for c in range(1, max_col + 1):
            ws.cell(row=r, column=c).value = None

def populate_heygen_submit_excel_from_db():
    topic_id = int(input("Enter topic_id (YouTube Channel): ").strip())

    items = fetch_heygen_submit_jobs(topic_id=topic_id, limit=5000)
    if not items:
        print("No eligible rows found for HeyGen submission (reviewed + not posted + has text).")
        return

    wb = load_workbook(HEYGEN_FILE)
    ws = wb[HEYGEN_SHEET] if HEYGEN_SHEET in wb.sheetnames else wb.active

    colmap = ensure_headers(ws, HEYGEN_REQUIRED_COLS)
    max_col = max(colmap.values())

    # Clear from row 10 onward
    clear_rows_from(ws, max_col=max_col, start_row=HEYGEN_START_ROW)

    row = HEYGEN_START_ROW
    missing_template = 0

    for it in items:
        template_url = (it.get("template_url") or "").strip()
        text = it.get("section_text") or ""
        name = it.get("image_name") or ""

        if not template_url:
            missing_template += 1

        ws.cell(row=row, column=colmap["HeyGen_Template_url"], value=template_url)
        ws.cell(row=row, column=colmap["story_text"], value=text)
        ws.cell(row=row, column=colmap["video_name"], value=name)

        # Clear these so heygen_submit_videos.py will process
        ws.cell(row=row, column=colmap["status"], value="")
        ws.cell(row=row, column=colmap["message"], value="")
        ws.cell(row=row, column=colmap["submitted_at"], value="")

        row += 1

    wb.save(HEYGEN_FILE)
    print(f"✅ Wrote {len(items)} rows into {HEYGEN_FILE} starting at row {HEYGEN_START_ROW} (cleared old rows from {HEYGEN_START_ROW}+).")

    if missing_template:
        print(f"⚠️ WARNING: {missing_template} row(s) missing template_url.")
        print("   Fix: set default HeyGen avatar on the story (Story Editor) or section override.")







def fetch_scheduled_rows(topic_id: int, only_due_now: bool = False, limit: int = 2000):
    r = requests.get(
        f"{BASE_URL}/api/worker_fetch_upload_jobs.php",
        params={"topic_id": topic_id, "only_due_now": 1 if only_due_now else 0, "limit": limit},
        headers=HEADERS,
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["items"]

def ensure_columns(ws):
    headers = [c.value for c in ws[1]]
    headers = [h if h is not None else "" for h in headers]
    header_map = {h: i + 1 for i, h in enumerate(headers) if h}

    changed = False
    for col in UPLOADER_REQUIRED_COLS:
        if col not in header_map:
            headers.append(col)
            ws.cell(row=1, column=len(headers), value=col)
            header_map[col] = len(headers)
            changed = True

    return header_map, changed

def clear_from_row(ws, header_map, UPLOADER_START_ROW: int):
    # Clear values only (keeps formatting)
    max_row = ws.max_row
    max_col = max(header_map.values()) if header_map else ws.max_column
    for r in range(UPLOADER_START_ROW, max_row + 1):
        for c in range(1, max_col + 1):
            ws.cell(row=r, column=c).value = None

def format_schedule_date(dt_str: str):
    """
    Your uploader tries to parse schedule_date using '%Y-%m-%d' in one path :contentReference[oaicite:2]{index=2}.
    So we return 'YYYY-MM-DD'. If scheduled_at includes time, we cut date part.
    """
    if not dt_str:
        return ""
    # dt_str like "2026-01-15 10:00:00"
    return dt_str[:10]

def pupulate_data_for_uploads():
    topic_id = int(input("Enter topic_id: ").strip())
    # optional_due = input("Only due now? (y/n): ").strip().lower() == "y"
    optional_due = False

    items = fetch_scheduled_rows(topic_id=topic_id, only_due_now=optional_due, limit=5000)
    if not items:
        print("No scheduled rows found in DB for this topic.")
        return

    wb = load_workbook(UPLOADER_MASTER_FILE)
    ws = wb.active

    header_map, changed = ensure_columns(ws)

    # Clear existing data from row 80 onward
    clear_from_row(ws, header_map, UPLOADER_START_ROW)

    row_idx = UPLOADER_START_ROW
    for it in items:
        section_id = it.get("section_id", "")
        media_file = (it.get("final_video_path") or "")  # if you have final_video_path in API later
        if not media_file:
            # fallback: if your final videos are named by image_name:
            img_name = it.get("image_name") or ""
            # If your uploader expects a full path, set your real folder here:
            # media_file = fr"C:\path\to\final_videos\{img_name}.mp4"
            media_file = ""

        story_title = it.get("story_title") or ""
        story_desc = it.get("story_description") or ""
        section_title = it.get("section_title") or ""
        section_desc = it.get("section_description") or ""
        playlist = it.get("youtube_playlist_name") or ""
        scheduled_at = it.get("scheduled_at") or ""

        # YouTube fields
        yt_title = section_title.strip() if section_title.strip() else story_title.strip()
        yt_description = (section_desc.strip() if section_desc.strip() else story_desc.strip())

        # IMPORTANT: youTubeChannel must be filled. Use topic mapping (recommended).
        # For now, you can hardcode or maintain a mapping dict in this script:
        
        # youTubeChannel = input("Enter youTubeChannel name (exact as appears in YouTube switch account): ").strip()
        youTubeChannel = it.get("youtube_channel_name")


        ws.cell(row=row_idx, column=header_map["section_id"], value=section_id)
        ws.cell(row=row_idx, column=header_map["media_type"], value="video")
        ws.cell(row=row_idx, column=header_map["future"], value="")  # leave blank
        ws.cell(row=row_idx, column=header_map["youtube_status"], value="")  # blank => uploader will attempt
        ws.cell(row=row_idx, column=header_map["youTubeChannel"], value=youTubeChannel)

        ws.cell(row=row_idx, column=header_map["media_file"], value=media_file)
        ws.cell(row=row_idx, column=header_map["yt_title"], value=yt_title)
        ws.cell(row=row_idx, column=header_map["yt_description"], value=yt_description)
        ws.cell(row=row_idx, column=header_map["yt_playlist"], value=playlist)
        ws.cell(row=row_idx, column=header_map["yt_schedule_date"], value=format_schedule_date(scheduled_at))
        ws.cell(row=row_idx, column=header_map["yt_tags"], value="")

        row_idx += 1

    wb.save(UPLOADER_MASTER_FILE)
    print(f"✅ Wrote {len(items)} rows into {UPLOADER_MASTER_FILE} starting at row {UPLOADER_START_ROW} (cleared old rows from {UPLOADER_START_ROW}+).")





def fetch_image_jobs(topic_id: int = 0, limit: int = 300):
    r = requests.get(
        f"{BASE_URL}/api/worker_fetch_image_jobs.php",
        params={"topic_id": topic_id, "limit": limit},
        headers=HEADERS,
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["items"]

def write_excel(items):
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_NAME

    # Keep your script’s expected columns + add section_id + image_name
    headers = ["prompt", "account_id", "image_path", "video_cmd", "video_path", "status",
               "account_id_1", "account_id_2", "section_id", "image_name"]
    ws.append(headers)

    for it in items:
        ws.append([
            it.get("image_prompt",""),
            "",   # account_id (let script distribute)
            "",   # image_path blank so script picks it up
            "", "", "", "", "",
            it.get("section_id",""),
            it.get("image_name",""),
        ])

    wb.save(EXCEL_FILE)
    print(f"Wrote {len(items)} jobs to {EXCEL_FILE.resolve()}")

def fetch_db_records_for_image_creation():
    items = fetch_image_jobs(topic_id=0, limit=500)  # topic_id optional
    if not items:
        print("No image jobs found (image_status=generating).")
    else:
        write_excel(items)

def claim_job(job_type: str, topic_id: int = 0):
    r = requests.get(
        f"{BASE_URL}/api/worker_claim_job.php",
        params={"job_type": job_type, "topic_id": topic_id},
        headers=HEADERS,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["job"]

def get_items(job_id: int):
    r = requests.get(
        f"{BASE_URL}/api/worker_job_items.php",
        params={"job_id": job_id},
        headers=HEADERS,
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["items"]

def report_item(job_id: int, section_id: int, ok: bool, image_path: str = "", error: str = ""):
    r = requests.post(
        f"{BASE_URL}/api/worker_report_item.php",
        data={
            "job_id": job_id,
            "section_id": section_id,
            "ok": 1 if ok else 0,
            "image_path": image_path,
            "error": error,
        },
        headers=HEADERS,
        timeout=60,
    )
    r.raise_for_status()

def finish_job(job_id: int, status: str, error: str = ""):
    r = requests.post(
        f"{BASE_URL}/api/worker_finish_job.php",
        data={"job_id": job_id, "status": status, "error": error},
        headers=HEADERS,
        timeout=60,
    )
    r.raise_for_status()

# ---- you will implement this using your existing Playwright logic ----
def generate_image_using_your_script(prompt: str, out_path: Path) -> Path:
    """
    Replace this body by calling your existing Google AI Studio code.
    Must save to out_path and return the final file path.
    """
    # Example placeholder:
    # out_path.write_bytes(b"")  # don't do this; real code writes the image
    raise NotImplementedError

def db_report_image(section_id: int, ok: bool, image_path: str = "", error: str = ""):
    try:
        requests.post(
            f"{BASE_URL}/api/worker_report_item.php",
            data={
                "job_id": 0,  # not used in this bridge approach
                "section_id": section_id,
                "ok": 1 if ok else 0,
                "image_path": image_path,
                "error": error,
            },
            headers=HEADERS,
            timeout=30,
        ).raise_for_status()
    except Exception as e:
        print(f"[DB] Failed to report section_id={section_id}: {e}")


def run_image_job(job):
    job_id = int(job["id"])
    items = get_items(job_id)

    if not items:
        finish_job(job_id, "success", "No items found for job (maybe already processed).")
        return

    any_fail = False

    for it in items:
        section_id = int(it["section_id"])
        prompt = (it.get("image_prompt") or "").strip()
        image_name = (it.get("image_name") or "").strip()

        if not prompt or not image_name:
            any_fail = True
            report_item(job_id, section_id, ok=False, error="Missing image_prompt or image_name")
            continue

        out_path = (OUT_DIR / f"{image_name}.png").resolve()

        try:
            final_path = generate_image_using_your_script(prompt, out_path)
            report_item(job_id, section_id, ok=True, image_path=str(final_path))
        except Exception as e:
            any_fail = True
            report_item(job_id, section_id, ok=False, error=str(e))

    finish_job(job_id, "failed" if any_fail else "success")


def main():
    while True:
        try:
            job = claim_job("image_gen", topic_id=0)  # 0 = any topic
            if job:
                print("Picked job:", job)
                run_image_job(job)
            else:
                time.sleep(10)
        except Exception as e:
            print("Worker error:", e)
            time.sleep(15)

if __name__ == "__main__":
    main()
