from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

def add_zoom_effect(image_path, audio_duration, zoom_factor=1.2, start_pos="center", end_pos="center"):
    """
    Adds a zoom-in effect on an image over the audio duration.
    
    Args:
        image_path (str): Path to the image file.
        audio_duration (float): Duration for the zoom effect.
        zoom_factor (float): How much to zoom in or out (default 1.2).
        start_pos (str): Starting position ("center", "top", "bottom", "left", "right").
        end_pos (str): Ending position ("center", "top", "bottom", "left", "right").
        
    Returns:
        VideoClip: A clip with the zoom effect applied.
    """
    clip = ImageClip(image_path, duration=audio_duration)
    zoom_clip = clip.resize(lambda t: 1 + zoom_factor * t / audio_duration)
    return zoom_clip.set_position(("center", "center"))

def add_pan_effect(image_path, audio_duration, start_x=0, end_x=1920, start_y=0, end_y=1080):
    """
    Adds a smooth pan effect to the image.
    
    Args:
        image_path (str): Path to the image file.
        audio_duration (float): Duration for the pan effect.
        start_x (int): Start X position of the pan.
        end_x (int): End X position of the pan.
        start_y (int): Start Y position of the pan.
        end_y (int): End Y position of the pan.
        
    Returns:
        VideoClip: A clip with a pan effect applied.
    """
    clip = ImageClip(image_path, duration=audio_duration)
    pan_clip = clip.set_position(lambda t: (start_x + (end_x - start_x) * t / audio_duration, 
                                            start_y + (end_y - start_y) * t / audio_duration))
    return pan_clip

def add_ken_burns_effect(image_path, audio_duration, start_zoom=1, end_zoom=1.2):
    """
    Adds a Ken Burns effect with pan and zoom to the image.
    """
    clip = ImageClip(image_path, duration=audio_duration)
    zoom_clip = clip.resize(lambda t: start_zoom + (end_zoom - start_zoom) * t / audio_duration)
    return zoom_clip.set_position("center")



def create_stylized_video(image_files, audio_files, output_file="final_video.mp4"):
    video_clips = []
    for idx, (image_file, audio_file) in enumerate(zip(image_files, audio_files)):
        audio_clip = AudioFileClip(audio_file)
        audio_duration = audio_clip.duration

        # Apply Effects
        video_clip = add_ken_burns_effect(image_file, audio_duration)
        video_clip = video_clip.set_audio(audio_clip)

        video_clips.append(video_clip)

    # Export Final Video
    final_video = concatenate_videoclips(video_clips, method="compose")
    final_video.write_videofile(output_file, codec="libx264", audio_codec="aac")
