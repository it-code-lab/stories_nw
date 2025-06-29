from google.cloud import texttospeech

def synthesize_speech_google(
    text, 
    output_file="output.mp3", 
    language="en-US", 
    gender="FEMALE", 
    voice_name="en-US-Neural2-F", 
    speaking_rate=1.0,
    pitch=0.0,
):
    """
    Generate speech using Google Text-to-Speech API with specified parameters.
    
    Parameters:
        text (str): The text to be converted to speech.
        output_file (str): The file path for the generated audio.
        language (str): The language code (default: "en-US").
        gender (str): The voice gender ("MALE", "FEMALE", "NEUTRAL").
        voice_name (str): Specific voice name from Google's API.
        speaking_rate (float): Speed of the voice (default: 1.0).
        
    Returns:
        str: The path to the generated audio file or None on error.
    """
    try:
        #print("Received google tts Arguments:", locals())
        client = texttospeech.TextToSpeechClient()

        # Set the text input
        synthesis_input = texttospeech.SynthesisInput(text=text)

        # Configure voice parameters
        voice = texttospeech.VoiceSelectionParams(
            language_code=language,
            ssml_gender=texttospeech.SsmlVoiceGender[gender.upper()],
            name=voice_name
        )

        # Audio config for synthesis
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=speaking_rate,
            pitch=pitch
        )

        # Synthesize the speech
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )

        # Save the audio file
        with open(output_file, "wb") as out:
            out.write(response.audio_content)
            print(f"Audio content written to {output_file}")

        return output_file

    except Exception as e:
        print(f"Error generating speech: {e}")
        return None
