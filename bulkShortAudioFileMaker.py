import os
import pandas as pd
from get_audio import get_audio_file  # Replace with your actual module
import re

# Constants
input_excel_file = "bulkShorts_input.xlsx"
audio_output_folder = "generated_audio"

# Ensure output folder exists
os.makedirs(audio_output_folder, exist_ok=True)

# Load input Excel
df = pd.read_excel(input_excel_file)

# Columns expected in Excel: title, text1, text2, ..., text10, subText, ctaText

def prepare_text_for_tts(text):
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
    for short_idx, row in df.iterrows():
        print(f"\nProcessing Short #{short_idx}")

        part_idx = 0

        # Process text1–text10
        for i in range(1, 11):
            text_field = f"text{i}"
            text_value = row.get(text_field)

            if pd.notna(text_value) and str(text_value).strip():
                text_parts = str(text_value).split("^")  # split parts
                for part in text_parts:
                    part = part.strip()
                    if part:
                        output_filename = os.path.join(audio_output_folder, f"short_{short_idx}_{part_idx}.mp3")
                        print(f"Generating audio for part: {part} --> {output_filename}")
                        cleaned_text = prepare_text_for_tts(part)
                        get_audio_file(
                            text=cleaned_text,
                            audio_file_name=output_filename,
                            tts_engine="google",
                            language="english",
                            gender="Male",
                            type="journey"
                        )
                        part_idx += 1

        # SubText and CTA are shown but not spoken — skipping for audio generation
        print(f"Short #{short_idx} completed.")

    print("\n✅ All audio files generated successfully!")

def create_json_file():
    df = pd.read_excel('bulkShorts_input.xlsx')
    df.to_json('bulkShorts_input.json', orient='records', force_ascii=False, indent=2)
    print("\n✅ Json file generated successfully!")
    
if __name__ == "__main__":
    create_audio_files()
    create_json_file()