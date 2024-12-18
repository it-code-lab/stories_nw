import os
from get_audio import get_audio_file

def test_get_audio():
    # test_cases = [
    #     {"text": "Hello world", "audio_file_name": "test_google_neural_english_female.mp3", "tts_engine": "google", "language": "english", "gender": "Female", "type": "neural"},
    #     {"text": "Namaste duniya", "audio_file_name": "test_google_journey_hindi_male.mp3", "tts_engine": "google", "language": "hindi", "gender": "Male", "type": "journey"},
    #     {"text": "Welcome to Amazon Polly", "audio_file_name": "test_amazon_neural_english_female.mp3", "tts_engine": "amazon", "language": "english", "gender": "Female", "type": "neural"},
    #     {"text": "Amazon Polly Hindi", "audio_file_name": "test_amazon_generative_hindi_female.mp3", "tts_engine": "amazon", "language": "hindi", "gender": "Female", "type": "generative"},
    #     {"text": "Amazon Polly English", "audio_file_name": "test_amazon_generative_english_female.mp3", "tts_engine": "amazon", "language": "english", "gender": "Female", "type": "generative"},
    #     {"text": "Amazon Polly English", "audio_file_name": "test_amazon_generative_english_male.mp3", "tts_engine": "amazon", "language": "english", "gender": "Male", "type": "generative"},
    # ]
    test_cases = [
        {"text": "Hi, I’m Ruth. I can read any text for you. Test it out!", "audio_file_name": "test_google_journey_english_female.mp3", "tts_engine": "google", "language": "english", "gender": "Female", "type": "journey"},
        {"text": "Hi, I’m Ruth. I can read any text for you. Test it out!", "audio_file_name": "test_amazon_generative_english_female.mp3", "tts_engine": "amazon", "language": "english", "gender": "Female", "type": "generative"},
    ]
    for case in test_cases:
        try:
            result = get_audio_file(
                text=case["text"],
                audio_file_name=case["audio_file_name"],
                tts_engine=case["tts_engine"],
                language=case["language"],
                gender=case["gender"],
                type=case["type"]
            )

            assert os.path.exists(result), f"Audio file {result} not created."
            print(f"Test passed: {case['audio_file_name']}")
        except Exception as e:
            print(f"Test failed for {case['audio_file_name']} - {str(e)}")

if __name__ == "__main__":
    test_get_audio()
