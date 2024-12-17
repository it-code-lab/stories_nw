import os
from text_to_speech_google import synthesize_speech_google

# Example Usage
text = "This is an example of using Google's Neural Voice with custom parameters."

# Set Google Application Credentials using a relative path
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(
    os.path.dirname(__file__), "tts-secret", "notes-imgtotxt-7b07c59d85c6.json"
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
