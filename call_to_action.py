from moviepy.editor import TextClip, CompositeVideoClip, ImageClip, ColorClip, VideoFileClip
from moviepy.video.fx.fadein import fadein
from moviepy.video.fx.fadeout import fadeout
from moviepy.video.fx.resize import resize

def create_gif_call_to_action(
    icon_path="like_icon.gif",  # GIF file path
    video_duration=10,
    position=("center", "top"),
    fade_duration=1,
    scale_factor = 0.8
):
    """
    Creates an animated call-to-action overlay with only a GIF.

    Args:
        icon_path: Path to the GIF file.
        video_duration: Duration the GIF should be visible.
        position: Position of the GIF on the screen.
        fade_duration: Duration for fade-in/out animation.

    Returns:
        A VideoFileClip with the GIF animation.
    """

    # Use VideoFileClip for the GIF
    icon_clip = (
        VideoFileClip(icon_path, has_mask=True)
        .set_duration(video_duration)
        .resize(scale_factor)
        .set_opacity(0.9)
        .fadein(fade_duration)
        .fadeout(fade_duration)
    )

    # Composite the GIF in the specified position
    call_to_action = CompositeVideoClip(
        [
            icon_clip.set_position(position),
        ],
        size=(icon_clip.size[0], icon_clip.size[1] + 150),
    )

    return call_to_action

def add_gif_to_video(
    video_clip, show_gif_for_duration, icon_path="like_icon.gif"
):
    """
    Adds a GIF overlay to the main video at specific timestamps.

    Args:
        video_clip: The main video clip.
        show_gif_for_duration: Duration the GIF should be visible.
        icon_path: Path to the GIF file.

    Returns:
        Video clip with GIF overlays at specific times.
    """
    video_duration = video_clip.duration

    # Calculate timestamps
    timestamps = []
    if video_duration > 60:
        timestamps.append(video_duration - 60)  # 1 minute before end

    timestamps.append(video_duration - 10)  # 10 seconds before end

    # Create GIF overlays at specified timestamps
    overlays = [
        create_gif_call_to_action(
            icon_path=icon_path,
            video_duration=show_gif_for_duration,
        ).set_start(t)
        for t in timestamps
    ]

    # Composite all overlays with the main video
    final_video = CompositeVideoClip([video_clip, *overlays])

    return final_video

def add_gif_to_video_Old(
    video_clip, show_at_seconds_from_end, show_gif_duration, icon_path="like_icon.gif"
):
    """
    Adds a GIF overlay to the main video.

    Args:
        video_clip: The main video clip.
        icon_path: Path to the GIF file.

    Returns:
        Video clip with GIF overlay.
    """

    # Create the GIF overlay
    gif_overlay = create_gif_call_to_action(
        icon_path=icon_path,
        video_duration=show_gif_duration,
    )

    # Add GIF to the main video at the end
    final_video = CompositeVideoClip(
        [video_clip, gif_overlay.set_start(video_clip.duration - show_at_seconds_from_end)]
    )

    return final_video

def create_call_to_action(
    message="",
    icon_path="like_icon.gif",  # GIF file path
    video_duration=5,
    position=("center", "bottom"),
    fade_duration=1
):
    """
    Creates an animated call-to-action overlay with text and icon.
    """
    # Create the CTA text
    cta_text = (
        TextClip(
            message,
            fontsize=80,
            color="white",
            font="Arial-Bold",
            stroke_color="black",
            stroke_width=3
        )
        .set_duration(video_duration)
        .fadein(fade_duration)
        .fadeout(fade_duration)
    )

    # Use VideoFileClip for the GIF
    icon_clip = (
        VideoFileClip(icon_path, has_mask=True)
        .set_duration(video_duration)
        .resize(height=100)
        .set_opacity(0.8)
        .fadein(fade_duration)
        .fadeout(fade_duration)
    )

    # Composite the text and icon side by side
    call_to_action = CompositeVideoClip(
        [
            icon_clip.set_position((position[0], position[1])),
            cta_text.set_position((position[0], (position[1][1] - 120) if isinstance(position[1], tuple) else position[1])),
        ],
        size=(cta_text.size[0], cta_text.size[1] + 150),
    )

    return call_to_action

#Working for png. DO Not Delete
def create_call_to_action_DND(
    message="Like, Share & Subscribe!",
    icon_path="like_icon.png",  # Replace with your icon file path
    video_duration=5,
    position=("center", "bottom"),
    fade_duration=1
):
    """
    Creates an animated call-to-action overlay with text and icon.
    """
    # Create the CTA text
    cta_text = (
        TextClip(
            message,
            fontsize=80,
            color="white",
            font="Arial-Bold",
            stroke_color="black",
            stroke_width=3
        )
        .set_duration(video_duration)
        .fadein(fade_duration)
        .fadeout(fade_duration)
    )

    # Create the icon clip
    icon_clip = (
        ImageClip(icon_path)
        .set_duration(video_duration)
        .resize(height=100)
        .set_opacity(0.8)
        .fadein(fade_duration)
        .fadeout(fade_duration)
    )

    # Composite the text and icon side by side
    call_to_action = CompositeVideoClip(
        [
            icon_clip.set_position((position[0], position[1])),
            cta_text.set_position((position[0], (position[1][1] - 120) if isinstance(position[1], tuple) else position[1])),
        ],
        size=(cta_text.size[0], cta_text.size[1] + 150),
    )

    return call_to_action


def add_call_to_action_to_video(
    video_clip, message="Like, Share & Subscribe!", icon_path="like_icon.png"
):
    """
    Adds the animated CTA overlay to the main video.
    
    Args:
        video_clip: The main video clip.
        message: CTA message to display.
        icon_path: Path to the icon file.

    Returns:
        Video clip with CTA overlay.
    """

    # Create the CTA overlay
    cta_overlay = create_call_to_action(
        message=message,
        icon_path=icon_path,
        video_duration=5,
    )

    # Add CTA to the main video at the end
    final_video = CompositeVideoClip([video_clip, cta_overlay.set_start(video_clip.duration - 5)])
    
    return final_video
