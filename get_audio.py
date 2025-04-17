import os
from text_to_speech_google import synthesize_speech_google
import boto3
from google.cloud import texttospeech_v1beta1 as texttospeech
from pydub import AudioSegment
import re

# Define the maximum character limit for each TTS engine
GOOGLE_MAX_CHARS = 2000
AMAZON_MAX_CHARS = 2000  # Approximate limit

def synthesize_speech_google(text, output_file, language, gender, voice_name, speaking_rate=1.0):
    """Synthesizes speech using Google Cloud Text-to-Speech."""
    client = texttospeech.TextToSpeechClient()
    input_text = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code=language,
        name=voice_name,
    )
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=speaking_rate
    )
    response = client.synthesize_speech(
        request={"input": input_text, "voice": voice, "audio_config": audio_config}
    )
    with open(output_file, "wb") as out:
        out.write(response.audio_content)
    return output_file

def split_text_into_sentences(text):
    """Splits text into sentences while trying to keep paragraphs intact."""
    # Use a more robust sentence splitting that considers abbreviations etc.
    sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|!)\s', text)
    return [s.strip() for s in sentences if s.strip()]

def merge_audio_files(file_paths, output_file):
    """Merges multiple audio files into one."""
    combined_audio = AudioSegment.empty()
    for file_path in file_paths:
        audio = AudioSegment.from_mp3(file_path)
        combined_audio += audio
    combined_audio.export(output_file, format="mp3")
    for file_path in file_paths:
        os.remove(file_path)
    return output_file

def get_audio_file(text, audio_file_name, tts_engine="google", language="english", gender="Male", type="journey"):
    """
    Generate audio using TTS, handling large text by splitting and merging.

    Args:
        text (str): The input text to convert to speech.
        audio_file_name (str): The desired name for the output audio file.
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
                "english-india": {"Male": "en-IN-Chirp-HD-D", "Female": "en-IN-Chirp-HD-F"},
                "hindi": {"Male": "hi-IN-Standard-B", "Female": "hi-IN-Standard-A"},
            },
            "journey": {
                "english": {"Male": "en-US-Journey-D", "Female": "en-US-Journey-F"},
                "english-india": {"Male": "en-IN-Chirp-HD-D", "Female": "en-IN-Chirp-HD-F"},
                "hindi": {"Male": "hi-IN-Standard-B", "Female": "hi-IN-Standard-A"},
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
    google_credentials_path = os.path.join(
        os.path.dirname(__file__), os.path.pardir, "tts-secret", "notes-imgtotxt-7b07c59d85c6.json"
    )
    if os.path.exists(google_credentials_path):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = google_credentials_path
    else:
        print(f"Warning: Google credentials file not found at {google_credentials_path}")

    try:
        voice_code = voice_configs[tts_engine][type][language][gender]
    except KeyError:
        raise ValueError("Invalid TTS configuration.")

    if tts_engine == "google":
        max_chars = GOOGLE_MAX_CHARS
        tts_function = synthesize_speech_google
    elif tts_engine == "amazon":
        max_chars = AMAZON_MAX_CHARS
        tts_function = polly_client.synthesize_speech
    else:
        raise ValueError("Unsupported TTS engine.")

    if len(text) <= max_chars:
        if tts_engine == "google":
            return tts_function(
                text=text,
                output_file=audio_file_name,
                language=f"{voice_code[:5]}",
                gender=gender.upper(),
                voice_name=voice_code,
                speaking_rate=1
            )
        elif tts_engine == "amazon":
            text_type = "ssml" if type == "neural" else "text"
            text_content = f'<speak><prosody rate="90%">{text}</prosody></speak>' if text_type == "ssml" else text
            response = tts_function(
                TextType=text_type,
                Text=text_content,
                OutputFormat="mp3",
                VoiceId=voice_code,
                Engine=type
            )
            with open(audio_file_name, "wb") as file:
                file.write(response['AudioStream'].read())
            return audio_file_name
    else:
        sentences = split_text_into_sentences(text)
        audio_files = []
        current_chunk = ""
        chunk_index = 0
        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 1 <= max_chars:  # +1 for potential space
                current_chunk += (sentence + " ")
            else:
                temp_audio_file = f"{audio_file_name.rsplit('.', 1)[0]}_part_{chunk_index}.mp3"
                if tts_engine == "google":
                    tts_function(
                        text=current_chunk.strip(),
                        output_file=temp_audio_file,
                        language=f"{voice_code[:5]}",
                        gender=gender.upper(),
                        voice_name=voice_code,
                        speaking_rate=1
                    )
                elif tts_engine == "amazon":
                    text_type = "ssml" if type == "neural" else "text"
                    text_content = f'<speak><prosody rate="90%">{current_chunk.strip()}</prosody></speak>' if text_type == "ssml" else current_chunk.strip()
                    response = tts_function(
                        TextType=text_type,
                        Text=text_content,
                        OutputFormat="mp3",
                        VoiceId=voice_code,
                        Engine=type
                    )
                    with open(temp_audio_file, "wb") as file:
                        file.write(response['AudioStream'].read())
                audio_files.append(temp_audio_file)
                current_chunk = sentence + " "
                chunk_index += 1

        # Process the last chunk
        if current_chunk.strip():
            temp_audio_file = f"{audio_file_name.rsplit('.', 1)[0]}_part_{chunk_index}.mp3"
            if tts_engine == "google":
                tts_function(
                    text=current_chunk.strip(),
                    output_file=temp_audio_file,
                    language=f"{voice_code[:5]}",
                    gender=gender.upper(),
                    voice_name=voice_code,
                    speaking_rate=1
                )
            elif tts_engine == "amazon":
                text_type = "ssml" if type == "neural" else "text"
                text_content = f'<speak><prosody rate="90%">{current_chunk.strip()}</prosody></speak>' if text_type == "ssml" else current_chunk.strip()
                response = tts_function(
                    TextType=text_type,
                    Text=text_content,
                    OutputFormat="mp3",
                    VoiceId=voice_code,
                    Engine=type
                )
                with open(temp_audio_file, "wb") as file:
                    file.write(response['AudioStream'].read())
            audio_files.append(temp_audio_file)

        if audio_files:
            return merge_audio_files(audio_files, audio_file_name)
        else:
            return "" # Should not happen, but just in case

    raise ValueError("Unsupported TTS engine.")

# Working DND - Needed enhancement to handle large text inputs
def get_audio_file_Working_DND(text, audio_file_name, tts_engine="google", language="english", gender="Male", type="journey"):
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

if __name__ == "__main__":
    sample_text = "Now that you know how this tool works, you can use it for your own projects—or even customize it further!If you found this tutorial helpful, hit that like button and subscribe for more coding breakdowns!Got any questions or feature requests? Drop them in the comments—I’d love to hear your thoughts!"


    output_audio_file = "test_audio.mp3"
    
    generated_file = get_audio_file(sample_text, output_audio_file)
    print(f"Generated audio file: {generated_file}")