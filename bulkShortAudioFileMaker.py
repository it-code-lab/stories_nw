import os
import shutil
import pandas as pd
from get_audio import get_audio_file  # Replace with your actual module
import re

# Constants
input_excel_file = "bulkShorts_input.xlsx"
audio_output_folder = "generated_audio"

# Ensure output folder exists
#os.makedirs(audio_output_folder, exist_ok=True)

# Load input Excel
df = pd.read_excel(input_excel_file)

# Columns expected in Excel: title, text1, text2, ..., text10, subText, ctaText

def prepare_text_for_tts(text, language="english"):
    if not text:
        return ""

    # Remove emojis and known special Unicode codes
    emoji_pattern = re.compile(
        "["
        u"\U0001F600-\U0001F64F"  # emoticons
        u"\U0001F300-\U0001F5FF"  # symbols & pictographs
        u"\U0001F680-\U0001F6FF"  # transport & map
        u"\U0001F1E0-\U0001F1FF"  # flags
        u"\u2600-\u26FF"          # miscellaneous symbols (☀️, ⏰)
        u"\u2700-\u27BF"          # dingbats
        u"\U0001F900-\U0001F9FF"  # supplemental symbols
        u"\U0001FA70-\U0001FAFF"  # extended pictographs
        u"\u200d"                 # zero width joiner
        u"\ufe0f"                 # variation selectors
        u"\u23cf"                 # eject symbol
        u"\u23e9"                 # fast forward symbol
        u"\u231a"                 # watch symbol
        u"\u3030"                 # wavy dash
        "]+", flags=re.UNICODE
    )
    cleaned = emoji_pattern.sub(r'', text)

    # Remove leftover non-word junk except basic punctuation
    #cleaned = re.sub(r"[^a-zA-Z0-9.,!?\\-'\"\\s]", '', cleaned)
    #cleaned = re.sub(r"[^a-zA-Z0-9.,!?\\'\"\s-]", '', cleaned)

    # Allow Hindi characters (Devanagari range: \u0900-\u097F) if lang is 'hi'
    if language == 'hindi':
        cleaned = re.sub(r"[^\u0900-\u097Fa-zA-Z0-9.,!?\'\"\s-]", '', cleaned)
    else:
        cleaned = re.sub(r"[^a-zA-Z0-9.,!?\'\"\s-]", '', cleaned)

    # Normalize spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # Add full stop if missing
    if cleaned and cleaned[-1] not in {'.', '!', '?'}:
        cleaned += '.'

    return cleaned

#DND - Not in use - was partially working
def prepare_text_for_tts_old(text):
    # Remove emojis first
    emoji_pattern = re.compile(
        "["  
        u"\U0001F600-\U0001F64F"
        u"\U0001F300-\U0001F5FF"
        u"\U0001F680-\U0001F6FF"
        u"\U0001F1E0-\U0001F1FF"
        u"\U00002500-\U00002BEF"
        u"\U00002702-\U000027B0"
        u"\U00002702-\U000027B0"
        u"\U000024C2-\U0001F251"
        u"\U0001f926-\U0001f937"
        u"\U00010000-\U0010ffff"
        u"\u2640-\u2642"
        u"\u2600-\u2B55"
        u"\u200d"
        u"\u23cf"
        u"\u23e9"
        u"\u231a"
        u"\ufe0f"
        u"\u3030"
        "]+", flags=re.UNICODE)
    
    cleaned = emoji_pattern.sub(r'', text).strip()
    
    # Add full stop if missing
    if cleaned and cleaned[-1] not in {'.', '!', '?'}:
        cleaned += '.'
    
    return cleaned


def create_audio_files():

    # delete existing audio files in the output folder
    shutil.rmtree(audio_output_folder, ignore_errors=True)
    os.makedirs(audio_output_folder, exist_ok=True)
    
    for short_idx, row in df.iterrows():
        print(f"\nProcessing Short #{short_idx}")

        part_idx = 0
        title = row.get("title")
        description = row.get("description")
        tags = row.get("tags")
        language = row.get("language")
        status = row.get("status")
        gender = row.get("gender")

        # DND- This will not work as JavaScript reads data from Json file
        # if status == "success":
        #     print(f"Skipping Short #{short_idx} due to status: {status}")
        #     continue

        # Process text1–text10
        for i in range(1, 15):
            text_field = f"text{i}"
            text_value = row.get(text_field)

            if pd.notna(text_value) and str(text_value).strip():
                text_parts = str(text_value).split("^")  # split parts
                for part in text_parts:
                    part = part.strip()
                    if part:
                        output_filename = os.path.join(audio_output_folder, f"short_{short_idx}_{part_idx}.mp3")
                        print(f"Generating audio for part: {part} --> {output_filename}")
                        cleaned_text = prepare_text_for_tts(part, language)
                        get_audio_file(
                            text=cleaned_text,
                            audio_file_name=output_filename,
                            tts_engine="google",
                            language=language, # english/hindi/english-india
                            gender=gender, # Male/Female
                            type="neural"
                        )
                        part_idx += 1

        # SubText and CTA are shown but not spoken — skipping for audio generation
        print(f"Short #{short_idx} completed.")

    print("\n✅ All audio files generated successfully!")

def create_json_file_Old():
    df = pd.read_excel('bulkShorts_input.xlsx')
    if 'schedule_date' in df.columns:
        df['schedule_date'] = df['schedule_date'].dt.strftime('%Y-%m-%d')

    df.to_json('bulkShorts_input.json', orient='records', force_ascii=False, indent=2)
    print("\n✅ Json file generated successfully!")

def create_json_file():
    df = pd.read_excel('bulkShorts_input.xlsx')

    if 'schedule_date' in df.columns:
        # Safely convert to datetime, errors='coerce' converts invalid dates to NaT
        df['schedule_date'] = pd.to_datetime(df['schedule_date'], errors='coerce')
        # Format only non-null dates
        df['schedule_date'] = df['schedule_date'].apply(lambda x: x.strftime('%Y-%m-%d') if pd.notnull(x) else '')

    df.to_json('bulkShorts_input.json', orient='records', force_ascii=False, indent=2)
    print("\n✅ Json file generated successfully!")

def create_adhoc_audio_file(cleaned_text, filename):
    output_filename = os.path.join(audio_output_folder, filename)   

    get_audio_file(
        text=cleaned_text,
        audio_file_name=output_filename,
        tts_engine="google",
        language="english",
        gender="Male",
        type="journey"
    )
if __name__ == "__main__":
    create_audio_files()
    create_json_file()
    # create_adhoc_audio_file("Keep going.", "short_4_2b.mp3")