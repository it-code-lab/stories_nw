import os
from get_audio import get_audio_file  # Import your function

# Create output folder
output_folder = "generated_audio"
os.makedirs(output_folder, exist_ok=True)

# Example short texts
shorts = [
    ["Octopuses have three hearts", "Two hearts pump blood to the gills"],
    ["Success is not final", "Failure is not fatal", "It is the courage to continue that counts"]
]

for short_index, parts in enumerate(shorts):
    for part_index, text in enumerate(parts):
        audio_file_name = os.path.join(output_folder, f"short_{short_index}_{part_index}.mp3")
        print(f"Generating audio: {audio_file_name}")
        get_audio_file(
            text=text,
            audio_file_name=audio_file_name,
            tts_engine="google",  # or "amazon"
            language="english",
            gender="Female",
            type="journey"  # or "neural"
        )
