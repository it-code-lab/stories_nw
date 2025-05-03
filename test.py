import os
from text_to_speech_google import synthesize_speech_google
import datetime

# Example Usage
text = "This is an example of using Google's Neural Voice with custom parameters."

# Get today's date
today = datetime.datetime.now().day

# Choose credentials file based on whether the date is even or odd
if today % 2 == 0:
    print("Even day, using 173")
    credentials_file = "quantum-conduit-458602-k9-e1f713291583.json"
else:
    print("Odd day, using mail2")
    credentials_file = "notes-imgtotxt-7b07c59d85c6.json"

# Set Google Application Credentials using a relative path (one level up)
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(
    os.path.dirname(__file__), os.path.pardir, "tts-secret", credentials_file
)


# Call the function with all parameters
audio_file = synthesize_speech_google(
    text=text, 
    output_file="neural_audio.mp3", 
    language="en-US", 
    gender="MALE", 
    voice_name="en-US-Neural2-J", 
    speaking_rate=0.9
)
