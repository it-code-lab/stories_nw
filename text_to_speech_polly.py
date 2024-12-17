import boto3

def synthesize_speech_polly(
    text, 
    output_file="output.mp3", 
    language="en-US", 
    voice_id="Joanna", 
    engine="neural", 
    speaking_rate="1.0"
):
    """
    Generate speech using Amazon Polly API with specified parameters.
    
    Parameters:
        text (str): The text to be converted to speech.
        output_file (str): The file path for the generated audio.
        language (str): Language code (default: "en-US").
        voice_id (str): Voice ID from Amazon Polly (default: "Joanna").
        engine (str): Engine type ("standard" or "neural").
        speaking_rate (str): Speed of the voice (default: "1.0").
        
    Returns:
        str: The path to the generated audio file or None on error.
    """
    try:
        # Initialize Polly client
        polly_client = boto3.client('polly', region_name='us-east-1')

        # Build the SSML for custom speaking rate
        ssml_text = f"""
        <speak>
            <prosody rate="{speaking_rate}">
                {text}
            </prosody>
        </speak>
        """

        # Synthesize speech request
        response = polly_client.synthesize_speech(
            Text=ssml_text,
            OutputFormat="mp3",
            VoiceId=voice_id,
            LanguageCode=language,
            Engine=engine,
            TextType="ssml"
        )

        # Save the audio content
        with open(output_file, "wb") as file:
            file.write(response['AudioStream'].read())
            print(f"Audio content written to {output_file}")

        return output_file

    except Exception as e:
        print(f"Error generating speech: {e}")
        return None
