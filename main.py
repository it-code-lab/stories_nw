from tkinter import Tk, Label, Button, Text, StringVar, IntVar, Spinbox, OptionMenu, Frame, Scrollbar, RIGHT, Y

from scraper import scrape_and_process
from settings import sizes, background_music_options, font_settings, voices, tts_engine

# Initialize UI
root = Tk()
root.title("Content Processor")
root.geometry("700x800")

# Create Main Frame
main_frame = Frame(root)
main_frame.pack(padx=20, pady=20, fill="both", expand=True)

# Field Variables # DEFAULT VALUES CAN BE CHANGED HERE
language_var = StringVar(value="english")
skip_puppeteer_var = StringVar(value="yes")
tts_var = StringVar(value="google")
gender_var = StringVar(value="Female")
voice_var = StringVar(value="Joanna")
size_var = StringVar(value="Regular YouTube Video")
music_var = StringVar(value="story-classical-3-710.mp3")
max_words = IntVar(value=5)
fontsize = IntVar(value=90)
y_pos = StringVar(value="bottom")
style_var = StringVar(value="style2")

# Functions
def get_urls():
    """Fetch URLs from the multi-line Text widget."""
    return url_input_text.get("1.0", "end").strip()

def update_voice_menu(*args):
    selected_gender = gender_var.get()
    voice_var.set(voices[selected_gender][0])
    voice_menu["menu"].delete(0, "end")
    for voice in voices[selected_gender]:
        voice_menu["menu"].add_command(label=voice, command=lambda v=voice: voice_var.set(v))

def update_ui_based_on_video_type(*args):
    selected_type = size_var.get()
    if selected_type == "YouTube Shorts":
        max_words.set(3)
        y_pos.set("center")
        style_var.set("style2")
        fontsize.set(90)
    elif selected_type == "Regular YouTube Video":
        max_words.set(5)
        y_pos.set("center")
        style_var.set("style2")
        fontsize.set(90)

size_var.trace("w", update_ui_based_on_video_type)
#gender_var.trace("w", update_voice_menu)

# Create Labeled Inputs
def create_dropdown(frame, label_text, variable, options, row, col=0):
    Label(frame, text=label_text).grid(row=row, column=col, sticky="w", padx=10, pady=5)
    OptionMenu(frame, variable, *options).grid(row=row, column=col+1, padx=10, pady=5)

# URL Input Field with Scrollbar
Label(main_frame, text="Enter Website URLs (semicolon-separated):").grid(row=0, column=0, sticky="w", padx=10, pady=5)
url_input_text = Text(main_frame, width=70, height=6, wrap="word")
url_input_text.grid(row=0, column=1, padx=10, pady=5)
scrollbar = Scrollbar(main_frame, command=url_input_text.yview)
scrollbar.grid(row=0, column=2, sticky="ns")
url_input_text["yscrollcommand"] = scrollbar.set

# Create Layout
create_dropdown(main_frame, "Language:", language_var, ["english", "english-india","hindi", "french"], 1)
create_dropdown(main_frame, "Select TTS Engine:", tts_var, tts_engine.keys(), 2)
create_dropdown(main_frame, "Select Voice Gender:", gender_var, voices.keys(), 3)
# create_dropdown(main_frame, "Select Voice: (not in use)", voice_var, voices["Female"], 4)
create_dropdown(main_frame, "Select Video Type:", size_var, sizes.keys(), 5)
create_dropdown(main_frame, "Select Background Music:", music_var, background_music_options.keys(), 6)



# Additional Settings
Label(main_frame, text="Max Words per Caption:").grid(row=7, column=0, sticky="w", padx=10, pady=5)
Spinbox(main_frame, from_=1, to=10, textvariable=max_words, width=5).grid(row=7, column=1, padx=10, pady=5)

# Label(main_frame, text="Font Size(not in use):").grid(row=8, column=0, sticky="w", padx=10, pady=5)
# Spinbox(main_frame, from_=30, to=150, textvariable=fontsize, width=5).grid(row=8, column=1, padx=10, pady=5)

# create_dropdown(main_frame, "Vertical Position(not in use):", y_pos, ["top", "center", "bottom"], 9)
create_dropdown(main_frame, "Select Caption Style:", style_var, font_settings.keys(), 8)
create_dropdown(main_frame, "Skip Puppeteer Call:", skip_puppeteer_var, ["yes", "no"], 9)
# Process Button
Button(
    main_frame, text="Process",
    command=lambda: scrape_and_process(
        get_urls(), size_var.get(), music_var.get(),
        max_words.get(), fontsize.get(), y_pos.get(),
        style_var.get(), voice_var.get(), language_var.get(), gender_var.get(), tts_var.get(),skip_puppeteer_var.get()
    ),
    width=20, height=2
).grid(row=10, columnspan=2, pady=15)

root.mainloop()
