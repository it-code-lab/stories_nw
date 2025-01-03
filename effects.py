from moviepy.editor import *
from PIL import Image
import numpy as np  # Import numpy
import cv2
import numpy as np
from scipy.interpolate import CubicSpline
import requests
from io import BytesIO
import os

def add_zoom_effect(image_path, audio_duration, zoom_factor=0.9, start_pos="center", end_pos="center"):
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

def load_image(image_path):
    """
    Loads an image from a local path or URL.

    Args:
        image_path: Path to the image file or a URL.

    Returns:
        The loaded image (as a NumPy array).
    """
    if image_path.startswith("http://") or image_path.startswith("https://"):
        # Handle URL
        try:
            response = requests.get(image_path, stream=True)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content))
            return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
        except requests.exceptions.RequestException as e:
            print(f"Failed to load image from URL: {e}")
            return None
    else:
        # Handle local path
        return cv2.imread(image_path)
    
def create_camera_movement_video(image_path, 
                                 start_frame, 
                                 end_frame, 
                                 output_path='output.mp4', 
                                 duration=5, 
                                 fps=30):
    """
    Creates a video with camera movement between two frames within an image.

    Args:
        image_path: Path to the input image.
        start_frame: Dictionary containing 'width', 'height', 'left', 'top' 
                     of the starting camera frame.
        end_frame: Dictionary containing 'width', 'height', 'left', 'top' 
                   of the ending camera frame.
        output_path: Path to save the output video.
        duration: Duration of the video in seconds.
        fps: Frames per second for the video.

    Returns:
        None
    """

    # Load the image
    #img = cv2.imread(image_path)
    # Load the image
    img = load_image(image_path)
    if img is None:
        print("Failed to load image. Exiting.")
        return
    # Calculate image dimensions
    img_height, img_width, _ = img.shape

    # Calculate the aspect ratio from the start frame
    start_aspect_ratio = start_frame['width'] / start_frame['height']
    video_width = 1920  # Base width for output video
    video_height = int(video_width / start_aspect_ratio)

    # Define camera movement path (linear interpolation)
    def get_frame_at_time(t):
        progress = t / duration
        width = np.interp(progress, [0, 1], [start_frame['width'], end_frame['width']])
        height = width / start_aspect_ratio  # Ensure consistent aspect ratio
        left = np.interp(progress, [0, 1], [start_frame['left'], end_frame['left']])
        top = np.interp(progress, [0, 1], [start_frame['top'], end_frame['top']])
        return int(width), int(height), int(left), int(top)

    # Create VideoWriter object
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')  # Codec for MP4
    out = cv2.VideoWriter(output_path, fourcc, fps, (video_width, video_height))

    # Generate frames for the video
    for i in range(int(duration * fps)):
        t = i / fps
        width, height, left, top = get_frame_at_time(t)

        # Adjust for out-of-bounds cropping
        x1 = max(0, left)
        y1 = max(0, top)
        x2 = min(x1 + width, img_width)
        y2 = min(y1 + height, img_height)

        frame = img[y1:y2, x1:x2]

        # Ensure the cropped region matches the start frame's aspect ratio
        frame_height, frame_width, _ = frame.shape
        frame_aspect_ratio = frame_width / frame_height
        if frame_aspect_ratio != start_aspect_ratio:
            if frame_aspect_ratio > start_aspect_ratio:  # Too wide
                new_width = int(frame_height * start_aspect_ratio)
                offset = (frame_width - new_width) // 2
                frame = frame[:, offset:offset + new_width]
            else:  # Too tall
                new_height = int(frame_width / start_aspect_ratio)
                offset = (frame_height - new_height) // 2
                frame = frame[offset:offset + new_height, :]

        # Resize the frame to the output video dimensions
        frame = cv2.resize(frame, (video_width, video_height))

        # Write the frame to the video
        out.write(frame)

    # Release the VideoWriter object
    out.release()    

#working on Dell latitude and woring on precision  
def add_ken_burns_effect_DND(image_path, audio_duration, start_zoom=1, end_zoom=1.2):
    """Adds a Ken Burns effect with smooth pan and zoom."""
    clip = ImageClip(image_path, duration=audio_duration)

    def resize_frame(get_frame, t):
        frame = get_frame(t)
        img = Image.fromarray(frame)

        # Calculate smooth zoom factor
        zoom_factor = start_zoom + (end_zoom - start_zoom) * (t / audio_duration)
        
        # Ensure integer scaling
        new_width = round(img.width * zoom_factor)
        new_height = round(img.height * zoom_factor)

        # Resize with LANCZOS for better quality
        resized_img = img.resize((new_width, new_height), resample=Image.Resampling.LANCZOS)

        # Calculate centered crop
        left = (new_width - clip.w) // 2
        top = (new_height - clip.h) // 2
        right = left + clip.w
        bottom = top + clip.h

        # Crop image to center
        cropped_img = resized_img.crop((left, top, right, bottom))
        return np.array(cropped_img)

    try:
        zoom_clip = clip.fl(resize_frame, apply_to=['image'])
    except Exception as e:
        print(f"Error during resize: {e}")
        raise

    return zoom_clip.set_position("center")

# Not working on Dell latitude but woring on precision  - smooth motion  
def add_ken_burns_effect(image_path, audio_duration, start_zoom=1.2, end_zoom=1):
    """
    Adds a Ken Burns effect with pan and zoom to the image.
    """
    try:
        clip = ImageClip(image_path, duration=audio_duration)
        zoom_clip = clip.resize(lambda t: start_zoom + (end_zoom - start_zoom) * t / audio_duration)
        return zoom_clip.set_position("center")
    except Exception as e:
        clip = ImageClip(image_path, duration=audio_duration)

        def resize_frame(get_frame, t):
            frame = get_frame(t)
            img = Image.fromarray(frame)

            # Calculate smooth zoom factor
            zoom_factor = start_zoom + (end_zoom - start_zoom) * (t / audio_duration)
            
            # Ensure integer scaling
            new_width = round(img.width * zoom_factor)
            new_height = round(img.height * zoom_factor)

            # Resize with LANCZOS for better quality
            resized_img = img.resize((new_width, new_height), resample=Image.Resampling.LANCZOS)

            # Calculate centered crop
            left = (new_width - clip.w) // 2
            top = (new_height - clip.h) // 2
            right = left + clip.w
            bottom = top + clip.h

            # Crop image to center
            cropped_img = resized_img.crop((left, top, right, bottom))
            return np.array(cropped_img)

        try:
            zoom_clip = clip.fl(resize_frame, apply_to=['image'])
        except Exception as e:
            print(f"Error during resize: {e}")
            raise

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
