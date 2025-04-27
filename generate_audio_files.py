# generate_audio_files.py
from dia import Dia
import os

dia = Dia()

texts = [
    "Octopuses have three hearts",
    "Two hearts pump blood to the gills",
    "One heart pumps blood to the body",
    "Success is not final, failure is not fatal",
    "It is the courage to continue that counts",
    # add all parts
]

output_folder = "generated_audio"

os.makedirs(output_folder, exist_ok=True)

for idx, text in enumerate(texts):
    audio = dia.tts(text)
    output_path = os.path.join(output_folder, f"part_{idx}.wav")
    audio.save(output_path)
    print(f"Saved: {output_path}")
