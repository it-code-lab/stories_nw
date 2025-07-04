import datetime
import os
from text_to_speech_google import synthesize_speech_google
import boto3
from google.cloud import texttospeech_v1beta1 as texttospeech
from pydub import AudioSegment
import re

# Define the maximum character limit for each TTS engine
GOOGLE_MAX_CHARS = 4800
AMAZON_MAX_CHARS = 2000  # Approximate limit

def synthesize_speech_google(text, output_file, language, gender, voice_name, speaking_rate=1.0, pitch=0.0):
    """Synthesizes speech using Google Cloud Text-to-Speech."""
    client = texttospeech.TextToSpeechClient()
    input_text = texttospeech.SynthesisInput(text=text)
    voice = texttospeech.VoiceSelectionParams(
        language_code=language,
        name=voice_name,
    )

    if pitch != 0.0:
        audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=speaking_rate,
        pitch=pitch
        )
    else:
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

def split_text_into_sentences(text, language="english"):
    """Splits text into sentences, handling language-specific punctuation."""
    if language.lower() == "english":
        # More robust English sentence splitting
        sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|!)\s', text)
    else:
        # Hindi or general Unicode-friendly (including `।`)
        sentences = re.split(r'(?<=[।.!?])\s+', text)
    
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

def get_audio_file(text, audio_file_name, tts_engine="google", language="english", gender="Male", type="neural", age_group="adult"):
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

    # For english-india, hi-IN voices pronouce names better so those are used

    voice_configs = {
        "google": {
            "neural": {
                "english": {"Male": "en-US-Chirp3-HD-Orus", "Female": "en-US-Chirp3-HD-Leda"},
                "english-with-pitch": {"Male": "en-US-Wavenet-B", "Female": "en-US-Wavenet-F"},
                "english-india-n": {"Male": "hi-IN-Chirp3-HD-Orus", "Female": "hi-IN-Chirp3-HD-Leda"},
                "english-india": {"Male": "en-IN-Chirp3-HD-Orus", "Female": "en-IN-Chirp3-HD-Leda"},
                "english-india-with-pitch": {"Male": "en-IN-Wavenet-B", "Female": "en-IN-Wavenet-E"},
                "hindi-with-pitch": {"Male": "hi-IN-Wavenet-B", "Female": "hi-IN-Wavenet-E"},
                "hindi": {"Male": "hi-IN-Wavenet-B", "Female": "hi-IN-Wavenet-A"},
            },
            "journey": {
                "english": {"Male": "en-US-Journey-D", "Female": "en-US-Journey-F"},
                "english-with-pitch": {"Male": "en-US-Wavenet-B", "Female": "en-US-Wavenet-F"},
                "english-india-n": {"Male": "hi-IN-Chirp3-HD-Orus", "Female": "hi-IN-Chirp3-HD-Leda"},
                "english-india": {"Male": "en-IN-Chirp3-HD-Orus", "Female": "en-IN-Chirp3-HD-Leda"},
                "english-india-old": {"Male": "en-IN-Chirp-HD-D", "Female": "en-IN-Chirp-HD-F"},
                "english-india-with-pitch": {"Male": "en-IN-Wavenet-B", "Female": "en-IN-Wavenet-E"},
                "hindi": {"Male": "hi-IN-Chirp3-HD-Orus", "Female": "hi-IN-Chirp3-HD-Leda"},
                "hindi-with-pitch": {"Male": "hi-IN-Wavenet-B", "Female": "hi-IN-Wavenet-E"},
                "hindi-old": {"Male": "hi-IN-Wavenet-B", "Female": "hi-IN-Wavenet-A"},
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

    today = datetime.datetime.now().day

    # Choose credentials file based on whether the date is even or odd
    if today % 2 == 0:
        print("Even day, using 173")
        credentials_file = "quantum-conduit-458602-k9-e1f713291583.json"
    else:
        print("Odd day, using mail2")
        credentials_file = "notes-imgtotxt-7b07c59d85c6.json"

    if age_group not in [ "adult"]:
        language = language.__add__("-with-pitch") 
        
    speaking_rate, pitch = get_speaking_rate_and_pitch(age_group)

    # Set Google Application Credentials using a relative path (one level up)
    google_credentials_path = os.path.join(
        os.path.dirname(__file__), os.path.pardir, "tts-secret", credentials_file
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

    print(f"text size: {len(text.encode('utf-8'))} bytes")

    if len(text.encode('utf-8')) <= max_chars:
        if tts_engine == "google":
            return tts_function(
                text=text,
                output_file=audio_file_name,
                language=f"{voice_code[:5]}",
                gender=gender.upper(),
                voice_name=voice_code,
                speaking_rate=speaking_rate,
                pitch=pitch
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
        sentences = split_text_into_sentences(text, language)
        audio_files = []
        current_chunk = ""
        chunk_index = 0
        for sentence in sentences:
            if len((current_chunk + sentence + " ").encode('utf-8')) <= max_chars:  # +1 for potential space
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
                        speaking_rate=speaking_rate,
                        pitch=pitch
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
                    speaking_rate=speaking_rate,
                    pitch=pitch
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

def get_speaking_rate_and_pitch(age_group):
    if age_group == "child":
        return 0.8, 5.0  # faster and higher pitch
    elif age_group == "teen":
        return 1.0, 0.0  # normal
    elif age_group == "adult":
        return 0.9, 0.0  # slightly slower
    elif age_group == "elderly":
        return 0.8, -5.0  # slower and lower pitch
    else:
        return 1.0, 0.0  # default
    
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
    sample_text = "When Abraham Lincoln worked as a store clerk,he once overcharged a customer by just a few cents"


    output_audio_file = "test_audio.mp3"

    generated_file = get_audio_file(sample_text, output_audio_file,language="english", gender="Female", type="neural", age_group="child")

    #generated_file = get_audio_file(sample_text, output_audio_file,language="english", gender="Female", type="neural")
    print(f"Generated audio file: {generated_file}")