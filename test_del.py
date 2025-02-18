import aeneas

print(aeneas.__version__) # Print the version

try:
    config = aeneas.Config(audio_file_path="audio.wav", text_file_path="normalized_text.txt", language="en")
    print("Aeneas Config created successfully!")
except Exception as e:
    print(f"Error: {e}")