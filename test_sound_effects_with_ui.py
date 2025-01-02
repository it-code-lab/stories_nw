# Enhanced Video Creation with Sound Effect Customization and UI
import os
import json
from tkinter import Tk, Label, Button, Listbox, StringVar, IntVar, Text, Scrollbar, END, filedialog
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from audio_video_processor import resize_and_crop_image
from get_audio import get_audio_file
from settings import sizes, background_music_options

# Load stopwords for keyword extraction
try:
    stop_words = set(stopwords.words("english"))
except:
    import nltk
    nltk.download('stopwords')
    stop_words = set(stopwords.words("english"))


def simple_tokenize(text):
    import string
    text = text.lower()
    return [word.strip(string.punctuation) for word in text.split()]

# Extract keywords from text
def extract_keywords(text):
    tokens = simple_tokenize(text)
    keywords = [word for word in tokens if word not in stop_words and word.isalnum()]
    return keywords

# Save configurations to a JSON file
def save_configurations(configurations, file_path="sfx_config.json"):
    with open(file_path, "w") as f:
        json.dump(configurations, f, indent=4)

# Load configurations from a JSON file
def load_configurations(file_path="sfx_config.json"):
    with open(file_path, "r") as f:
        return json.load(f)

# Apply custom SFX to video clip
def apply_custom_sfx(video_clip, configurations):
    audio_clips = [video_clip.audio]
    for config in configurations:
        if config["sfx"]:
            sfx_clip = (
                AudioFileClip(config["sfx"])
                .subclip(0, config["duration"])
                .set_start(config["start_time"])
            )
            audio_clips.append(sfx_clip)
    final_audio = CompositeAudioClip(audio_clips)
    return video_clip.set_audio(final_audio)

# Main UI class
class SFXCustomizerUI:
    def __init__(self, root, sentences, sfx_mapping):
        self.root = root
        self.sentences = sentences
        self.sfx_mapping = sfx_mapping
        self.configurations = []
        self.current_index = 0

        # UI Components
        self.keyword_label = Label(root, text="Keywords:", font=("Arial", 12))
        self.keyword_label.pack()

        self.keyword_list = Listbox(root, selectmode="single", width=50, height=5)
        self.keyword_list.pack()

        self.sentence_label = Label(root, text="Sentence:", font=("Arial", 12))
        self.sentence_label.pack()

        self.sentence_text = Text(root, height=5, wrap="word")
        self.sentence_text.pack()

        self.sfx_label = Label(root, text="Available Sound Effects:", font=("Arial", 12))
        self.sfx_label.pack()

        self.sfx_list = Listbox(root, selectmode="single", width=50, height=5)
        self.sfx_list.pack()
        for sfx in sfx_mapping.keys():
            self.sfx_list.insert(END, sfx)

        self.start_label = Label(root, text="Start Time (seconds):")
        self.start_label.pack()
        self.start_time = IntVar()
        self.start_time_entry = Text(root, height=1, width=10)
        self.start_time_entry.pack()

        self.duration_label = Label(root, text="Duration (seconds):")
        self.duration_label.pack()
        self.duration = IntVar()
        self.duration_entry = Text(root, height=1, width=10)
        self.duration_entry.pack()

        self.add_button = Button(root, text="Add Configuration", command=self.add_configuration)
        self.add_button.pack()

        self.next_button = Button(root, text="Next Sentence", command=self.next_sentence)
        self.next_button.pack()

        self.save_button = Button(root, text="Save Configurations", command=self.save_configurations)
        self.save_button.pack()

        self.load_sentence()

    def load_sentence(self):
        """Load the current sentence and highlight keywords."""
        if self.current_index < len(self.sentences):
            sentence = self.sentences[self.current_index]
            keywords = extract_keywords(sentence)

            # Display sentence and keywords
            self.sentence_text.delete("1.0", END)
            self.sentence_text.insert(END, sentence)

            self.keyword_list.delete(0, END)
            for keyword in keywords:
                self.keyword_list.insert(END, keyword)

    def add_configuration(self):
        """Add the current configuration to the list."""
        sentence = self.sentences[self.current_index]
        selected_sfx = self.sfx_list.get(self.sfx_list.curselection())
        start_time = float(self.start_time_entry.get("1.0", END).strip())
        duration = float(self.duration_entry.get("1.0", END).strip())

        self.configurations.append({
            "sentence": sentence,
            "sfx": self.sfx_mapping[selected_sfx],
            "start_time": start_time,
            "duration": duration
        })
        print(f"Added configuration: {self.configurations[-1]}")

    def next_sentence(self):
        """Move to the next sentence."""
        self.current_index += 1
        if self.current_index < len(self.sentences):
            self.load_sentence()
        else:
            print("All sentences reviewed.")

    def save_configurations(self):
        """Save configurations to a JSON file."""
        save_path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON files", "*.json")])
        if save_path:
            save_configurations(self.configurations, save_path)
            print(f"Configurations saved to {save_path}")

if __name__ == "__main__":
    # Example sentences and SFX mapping
    sentences = [
        "Once upon a time, in a land far away...",
        "A brave knight set out on an adventure.",
        "And they all lived happily ever after.",
    ]
    sfx_mapping = {
        "rain": "sounds/rain.mp3",
        "bird": "sounds/birds.mp3",
        "thunder": "sounds/thunder.mp3",
        "knock": "sounds/knock.mp3",
        "laugh": "sounds/laugh.mp3",
    }

    root = Tk()
    root.title("SFX Customizer")
    ui = SFXCustomizerUI(root, sentences, sfx_mapping)
    root.mainloop()
