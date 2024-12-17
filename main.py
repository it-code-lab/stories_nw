from tkinter import Tk, Label, Button, Entry, StringVar, IntVar, Spinbox, OptionMenu, Frame

from scraper import scrape_and_process
from settings import sizes, background_music_options, font_settings, voices

# Initialize UI
root = Tk()
root.title("Content Processor")
root.geometry("600x700")

# Create Main Frame
main_frame = Frame(root)
main_frame.pack(padx=20, pady=20, fill="both", expand=True)

# Field Variables
url_input = StringVar()
language_var = StringVar(value="english")
gender_var = StringVar(value="Female")
voice_var = StringVar(value="Joanna")
size_var = StringVar(value="YouTube Shorts")
music_var = StringVar(value="Scary Stories")
max_words = IntVar(value=3)
fontsize = IntVar(value=90)
y_pos = StringVar(value="center")
style_var = StringVar(value="Style 27")

# Functions
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
        style_var.set("Style 27")
        fontsize.set(90)
    elif selected_type == "Regular YouTube Video":
        max_words.set(5)
        y_pos.set("bottom")
        style_var.set("Style 4")
        fontsize.set(90)

size_var.trace("w", update_ui_based_on_video_type)
gender_var.trace("w", update_voice_menu)

# Create Labeled Inputs
def create_label_entry(frame, label_text, variable, row, col=0, width=50):
    Label(frame, text=label_text).grid(row=row, column=col, sticky="w", padx=10, pady=5)
    Entry(frame, textvariable=variable, width=width).grid(row=row, column=col+1, padx=10, pady=5)

def create_dropdown(frame, label_text, variable, options, row, col=0):
    Label(frame, text=label_text).grid(row=row, column=col, sticky="w", padx=10, pady=5)
    OptionMenu(frame, variable, *options).grid(row=row, column=col+1, padx=10, pady=5)

# Layout
create_label_entry(main_frame, "Enter Website URL:", url_input, 0)
create_dropdown(main_frame, "Language:", language_var, ["english", "hindi", "french"], 1)
create_dropdown(main_frame, "Select Voice Gender:", gender_var, voices.keys(), 2)
create_dropdown(main_frame, "Select Voice:", voice_var, voices["Female"], 3)
create_dropdown(main_frame, "Select Video Type:", size_var, sizes.keys(), 4)
create_dropdown(main_frame, "Select Background Music:", music_var, background_music_options.keys(), 5)

# Additional Settings
Label(main_frame, text="Max Words per Caption:").grid(row=6, column=0, sticky="w", padx=10, pady=5)
Spinbox(main_frame, from_=1, to=10, textvariable=max_words, width=5).grid(row=6, column=1, padx=10, pady=5)

Label(main_frame, text="Font Size:").grid(row=7, column=0, sticky="w", padx=10, pady=5)
Spinbox(main_frame, from_=30, to=150, textvariable=fontsize, width=5).grid(row=7, column=1, padx=10, pady=5)

create_dropdown(main_frame, "Vertical Position:", y_pos, ["top", "center", "bottom"], 8)
create_dropdown(main_frame, "Select Caption Style:", style_var, font_settings.keys(), 9)

# Process Button
Button(
    main_frame, text="Process",
    command=lambda: scrape_and_process(
        url_input.get(), size_var.get(), music_var.get(),
        max_words.get(), fontsize.get(), y_pos.get(),
        style_var.get(), voice_var.get(), language_var.get(), gender_var.get()
    ),
    width=20, height=2
).grid(row=10, columnspan=2, pady=15)

root.mainloop()
