from moviepy.editor import VideoFileClip
from call_to_action import add_call_to_action_to_video, add_gif_to_video

# # Load your main video
# video_clip = VideoFileClip("main_video.mp4")

# # Apply the enhanced CTA overlay
# final_video = add_call_to_action_to_video(
#     video_clip,
#     message=" ",
#     icon_path="like_icon.gif"  # Replace with your actual icon file
# )

# # Export the final video
# final_video.write_videofile("output_video_with_cta.mp4", codec="libx264", audio_codec="aac", fps=24)


# video_clip = VideoFileClip("main_video.mp4")

# # Apply GIF overlay
# final_video = add_gif_to_video(
#     video_clip, 5, icon_path="subscribe.gif"
# )

# # Export the final video
# final_video.write_videofile(
#     "output_video_with_gif.mp4", codec="libx264", audio_codec="aac", fps=24
# )

video_clip = VideoFileClip("output_video.mp4")

final_video = add_gif_to_video(
    video_clip, 5, icon_path="subscribe.gif"
)

final_video.write_videofile(
    "output_video_with_gif.mp4", codec="libx264", audio_codec="aac", fps=24
)