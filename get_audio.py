import os
from text_to_speech_google import synthesize_speech_google
import boto3

def get_audio_file(text, audio_file_name, tts_engine="google", language="english", gender="Female", type="journey"):
    """
    Generate audio using TTS.

    Args:
        tts_engine (str): TTS engine to use ('google' or 'amazon').
        language (str): Language for TTS ('english' or 'hindi').
        gender (str): Gender of the voice ('Male' or 'Female').
        type (str): Voice type ('neural', 'journey', or 'generative').

    Returns:
        str: Path to the generated audio file.
    """
    voice_configs = {
        "google": {
            "neural": {
                "english": {"Male": "en-US-Neural2-J", "Female": "en-US-Neural2-F"},
                "hindi": {"Male": "hi-IN-Neural2-B", "Female": "hi-IN-Neural2-A"},
            },
            "journey": {
                "english": {"Male": "en-US-Journey-D", "Female": "en-US-Journey-F"},
                "hindi": {"Male": "en-US-Journey-D", "Female": "en-US-Journey-F"},
            },
        },
        "amazon": {
            "neural": {
                "english": {"Male": "Matthew", "Female": "Joanna"},
                "hindi": {"Male": "Matthew", "Female": "Kajal"},
            },
            "generative": {
                "english": {"Male": "Matthew", "Female": "Joanna"},
                "hindi": {"Male": "Matthew", "Female": "Kajal"},
            },
        },
    }

    # Initialize Amazon Polly
    polly_client = boto3.client('polly', region_name='us-east-1')

    # Set Google Application Credentials using a relative path (one level up)
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.path.join(
        os.path.dirname(__file__), os.path.pardir, "tts-secret", "notes-imgtotxt-7b07c59d85c6.json"
    )

    try:
        voice_code = voice_configs[tts_engine][type][language][gender]
    except KeyError:
        raise ValueError("Invalid TTS configuration.")

    if tts_engine == "google":
        return synthesize_speech_google(
            text=text,
            output_file=audio_file_name,
            language=f"{voice_code[:5]}",
            gender=gender.upper(),
            voice_name=voice_code,
            speaking_rate=1
        )

    elif tts_engine == "amazonX": # Disabled for now
        text_type = "ssml" if type == "neural" else "text"
        text_content = f'<speak><prosody rate="90%">{text}</prosody></speak>' if text_type == "ssml" else text

        response = polly_client.synthesize_speech(
            TextType=text_type,
            Text=text_content,
            OutputFormat="mp3",
            VoiceId=voice_code,
            Engine=type
        )

        with open(audio_file_name, "wb") as file:
            file.write(response['AudioStream'].read())
        return audio_file_name

    raise ValueError("Unsupported TTS engine.")
