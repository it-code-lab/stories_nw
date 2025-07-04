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
excel_var = StringVar(value="no")
notebooklm_var = StringVar(value="no")

skip_puppeteer_var = StringVar(value="no")
skip_captions_var = StringVar(value="no")
pitch_var = StringVar(value="adult")
disable_subscribe_var = StringVar(value="no")
tts_var = StringVar(value="google")
gender_var = StringVar(value="Female")
voice_var = StringVar(value="Joanna")
size_var = StringVar(value="YouTube Shorts")
music_var = StringVar(value="story-classical-3-710.mp3")
max_words = IntVar(value=4)
fontsize = IntVar(value=90)
y_pos = StringVar(value="bottom")
style_var = StringVar(value="style2")
row_index = 0

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
        max_words.set(4)
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

row_index = row_index + 1
create_dropdown(main_frame, "Audio->WordTimeStamps-Video:", notebooklm_var, ["no", "yes"], row_index)


# Create Layout
row_index = row_index + 1
create_dropdown(main_frame, "Pick video background and story from video_story_input.xlsx:", excel_var, ["no", "yes"], row_index)

row_index = row_index + 1
create_dropdown(main_frame, "Language:", language_var, ["english", "english-india","hindi", "french"], row_index)

row_index = row_index + 1
create_dropdown(main_frame, "Select TTS Engine:", tts_var, tts_engine.keys(), row_index)

row_index = row_index + 1
create_dropdown(main_frame, "Select Voice Gender:", gender_var, voices.keys(), row_index)
# create_dropdown(main_frame, "Select Voice: (not in use)", voice_var, voices["Female"], 4)

row_index = row_index + 1
create_dropdown(main_frame, "Select Video Type:", size_var, sizes.keys(), row_index)

row_index = row_index + 1
create_dropdown(main_frame, "Select Background Music:", music_var, background_music_options.keys(), row_index)


row_index = row_index + 1
# Additional Settings
Label(main_frame, text="Max Words per Caption:").grid(row=row_index, column=0, sticky="w", padx=10, pady=5)
Spinbox(main_frame, from_=1, to=10, textvariable=max_words, width=5).grid(row=row_index, column=1, padx=10, pady=5)

# Label(main_frame, text="Font Size(not in use):").grid(row=8, column=0, sticky="w", padx=10, pady=5)
# Spinbox(main_frame, from_=30, to=150, textvariable=fontsize, width=5).grid(row=8, column=1, padx=10, pady=5)

# create_dropdown(main_frame, "Vertical Position(not in use):", y_pos, ["top", "center", "bottom"], 9)

row_index = row_index + 1
create_dropdown(main_frame, "Select Caption Style:", style_var, font_settings.keys(), row_index)

row_index = row_index + 1
create_dropdown(main_frame, "Skip Puppeteer Call(Should be 'no' for multi-shorts):", skip_puppeteer_var, ["yes", "no"], row_index)

row_index = row_index + 1
create_dropdown(main_frame, "Skip Captions(Select 'yes' for above as well with this):", skip_captions_var, ["yes", "no"], row_index)

row_index = row_index + 1
create_dropdown(main_frame, "Add Sound Pitch:", pitch_var, ["adult", "child", "teen", "elderly"], row_index)

row_index = row_index + 1
create_dropdown(main_frame, "Disable Subscribe Gif:", disable_subscribe_var, ["yes", "no"], row_index)

row_index = row_index + 1
# Process Button
Button(
    main_frame, text="Process",
    command=lambda: scrape_and_process(
        get_urls(), excel_var.get(), size_var.get(), music_var.get(),
        max_words.get(), fontsize.get(), y_pos.get(),
        style_var.get(), voice_var.get(), language_var.get(), gender_var.get(), tts_var.get(),skip_puppeteer_var.get(),skip_captions_var.get(), pitch_var.get()
        ,disable_subscribe_var.get(), notebooklm_var.get()
    ),
    width=20, height=2
).grid(row=row_index, columnspan=2, pady=15)

root.mainloop()
