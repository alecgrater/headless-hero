"""FFmpeg command-line argument builder for video assembly.

Constructs ffmpeg CLI argument lists for:
- Scene video (image + audio + Ken Burns + text overlay -> MP4)
- Video concat (multiple clips -> one video via concat demuxer)
- Audio concat (multiple MP3s -> one MP3)
- TikTok 9:16 reformat (blurred-background fill)
"""

import os
import tempfile
from pathlib import Path

# Intensity -> zoom speed multiplier for Ken Burns
_KB_SPEED = {"subtle": 0.0003, "moderate": 0.0006, "dramatic": 0.0012}

def _escape_drawtext(text: str) -> str:
    """Escape special characters for FFmpeg drawtext filter."""
    # FFmpeg drawtext needs escaping of : ; ' \ and newlines
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "\u2019")  # replace straight quote with curly
    text = text.replace(":", "\\:")
    text = text.replace(";", "\\;")
    return text

def _ken_burns_filter(
    effect: str,
    intensity: str,
    width: int,
    height: int,
    duration_frames: int,
) -> str:
    """Build a zoompan filter string for Ken Burns effects.

    The zoompan filter works on frames. We start at a zoomed/panned state and
    animate to the target state over the duration.
    """
    speed = _KB_SPEED.get(intensity, _KB_SPEED["moderate"])
    d = duration_frames
    # zoompan expects: z=zoom expression, x=pan-x, y=pan-y, d=total frames, s=output size
    # All expressions use 'on' (output frame number, 0-indexed)
    base = f"d={d}:s={width}x{height}:fps=30"

    if effect == "zoom_in":
        return f"zoompan={base}:z='1+{speed}*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    elif effect == "zoom_out":
        max_z = 1 + speed * d
        return f"zoompan={base}:z='{max_z}-{speed}*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    elif effect == "pan_left":
        return f"zoompan={base}:z='1.1':x='iw*0.1-iw*0.1*on/{d}':y='ih/2-(ih/zoom/2)'"
    elif effect == "pan_right":
        return f"zoompan={base}:z='1.1':x='iw*0.0+iw*0.1*on/{d}':y='ih/2-(ih/zoom/2)'"
    elif effect == "pan_up":
        return f"zoompan={base}:z='1.1':x='iw/2-(iw/zoom/2)':y='ih*0.1-ih*0.1*on/{d}'"
    elif effect == "pan_down":
        return f"zoompan={base}:z='1.1':x='iw/2-(iw/zoom/2)':y='ih*0.0+ih*0.1*on/{d}'"
    else:
        # no motion — still frame
        return f"zoompan={base}:z='1':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"

def _drawtext_filter(
    text: str,
    position: str,
    style: str,
    animation: str,
    show_at: float,
    overlay_duration: float,
    scene_duration: float,
) -> str:
    """Build a drawtext filter string for text overlays."""
    escaped = _escape_drawtext(text)

    # Font size by style
    fontsize = {"default": 36, "bold": 48, "subtitle": 30, "title_card": 64}.get(style, 36)
    fontcolor = "white"
    borderw = 2
    shadowx = 2
    shadowy = 2

    # Position mapping
    if position == "top":
        y_expr = "h*0.08"
    elif position == "center":
        y_expr = "(h-text_h)/2"
    elif position == "bottom":
        y_expr = "h-text_h-h*0.08"
    else:  # lower_third
        y_expr = "h*0.75"

    x_expr = "(w-text_w)/2"

    # Visibility window
    end_at = show_at + overlay_duration if overlay_duration > 0 else scene_duration
    enable = f"between(t,{show_at},{end_at})"

    # Animation
    if animation == "fade_in":
        alpha_expr = f"if(lt(t-{show_at},0.5),(t-{show_at})/0.5,1)"
    elif animation == "slide_up":
        # Slide from 20px below to final position over 0.5s
        slide_offset = f"if(lt(t-{show_at},0.5),20*(1-(t-{show_at})/0.5),0)"
        y_expr = f"{y_expr}+{slide_offset}"
        alpha_expr = "1"
    elif animation == "typewriter":
        # Reveal characters over time — approximate with alpha ramp
        alpha_expr = f"if(lt(t-{show_at},1),(t-{show_at})/1,1)"
    else:
        alpha_expr = "1"

    parts = [
        f"text='{escaped}'",
        f"fontsize={fontsize}",
        f"fontcolor={fontcolor}@{alpha_expr}" if animation in ("fade_in", "typewriter") else f"fontcolor={fontcolor}",
        f"x={x_expr}",
        f"y={y_expr}",
        f"borderw={borderw}",
        f"bordercolor=black",
        f"shadowx={shadowx}",
        f"shadowy={shadowy}",
        f"shadowcolor=black@0.6",
        f"enable='{enable}'",
    ]

    return "drawtext=" + ":".join(parts)

def build_scene_video_cmd(
    image_path: str,
    audio_path: str,
    output_path: str,
    duration: float,
    width: int = 1920,
    height: int = 1080,
    ken_burns_effect: str = "none",
    ken_burns_intensity: str = "moderate",
    text_overlay: str = "",
    overlay_position: str = "lower_third",
    overlay_style: str = "default",
    overlay_animation: str = "fade_in",
    overlay_show_at: float = 0.0,
    overlay_duration: float = 0.0,
    fade_out_duration: float = 0.3,
) -> list[str]:
    """Build FFmpeg command to render a single scene (image + audio -> MP4).

    Returns a list of args suitable for subprocess.run().
    """
    fps = 30
    duration_frames = int(duration * fps)

    filters: list[str] = []

    if ken_burns_effect != "none":
        kb = _ken_burns_filter(ken_burns_effect, ken_burns_intensity, width, height, duration_frames)
        filters.append(kb)
    else:
        # Static image: scale + pad to target resolution
        filters.append(f"zoompan=d={duration_frames}:s={width}x{height}:fps={fps}:z=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'")

    # Ensure correct output size
    filters.append(f"scale={width}:{height}:force_original_aspect_ratio=decrease")
    filters.append(f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black")
    filters.append("setsar=1")

    # Text overlay
    if text_overlay:
        dt = _drawtext_filter(
            text=text_overlay,
            position=overlay_position,
            style=overlay_style,
            animation=overlay_animation,
            show_at=overlay_show_at,
            overlay_duration=overlay_duration,
            scene_duration=duration,
        )
        filters.append(dt)

    # Fade out at end
    if fade_out_duration > 0:
        fade_start = max(0, duration - fade_out_duration)
        filters.append(f"fade=t=out:st={fade_start}:d={fade_out_duration}")

    filter_chain = ",".join(filters)

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-i", audio_path,
        "-filter_complex", f"[0:v]{filter_chain}[vout]",
        "-map", "[vout]",
        "-map", "1:a",
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-t", str(duration),
        "-shortest",
        output_path,
    ]

    return cmd

def build_concat_cmd(
    clip_paths: list[str],
    output_path: str,
) -> tuple[list[str], str]:
    """Build FFmpeg concat demuxer command to join multiple clips.

    Returns (command args, path to temp concat list file).
    The caller should delete the temp file after ffmpeg finishes.
    """
    # Write concat list to a temp file
    fd, list_path = tempfile.mkstemp(suffix=".txt", prefix="ffconcat_")
    with os.fdopen(fd, "w") as f:
        for clip in clip_paths:
            f.write(f"file '{clip}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_path,
        "-c", "copy",
        output_path,
    ]

    return cmd, list_path

def build_audio_concat_cmd(
    audio_paths: list[str],
    output_path: str,
) -> tuple[list[str], str]:
    """Build FFmpeg command to concatenate multiple audio files into one MP3.

    Returns (command args, path to temp concat list file).
    """
    fd, list_path = tempfile.mkstemp(suffix=".txt", prefix="ffaudioconcat_")
    with os.fdopen(fd, "w") as f:
        for path in audio_paths:
            f.write(f"file '{path}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_path,
        "-c:a", "libmp3lame",
        "-b:a", "192k",
        output_path,
    ]

    return cmd, list_path

def build_tiktok_cmd(
    input_path: str,
    output_path: str,
    target_width: int = 1080,
    target_height: int = 1920,
) -> list[str]:
    """Build FFmpeg command to convert 16:9 clip to 9:16 with blurred background fill.

    The approach: scale the original to fill width (blurred), then overlay
    the original scaled to fit within the frame.
    """
    filter_complex = (
        f"[0:v]split[bg][fg];"
        f"[bg]scale={target_width}:{target_height}:force_original_aspect_ratio=increase,"
        f"crop={target_width}:{target_height},boxblur=20:5[bgblur];"
        f"[fg]scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
        f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:color=black@0[fgpad];"
        f"[bgblur][fgpad]overlay=0:0"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-filter_complex", filter_complex,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        output_path,
    ]

    return cmd

def build_thumbnail_composite_cmd(
    image_path: str,
    output_path: str,
    title_text: str,
    bar_color: str = "0x9333EA",
    width: int = 1280,
    height: int = 720,
) -> list[str]:
    """Build FFmpeg command to composite title text + color bar onto a thumbnail image."""
    escaped = _escape_drawtext(title_text)

    filter_complex = (
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
        f"drawbox=x=0:y=ih-80:w=iw:h=80:color=#{bar_color.replace('0x', '')}@0.85:t=fill,"
        f"drawtext=text='{escaped}':fontsize=52:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2:"
        f"borderw=3:bordercolor=black:shadowx=3:shadowy=3:shadowcolor=black@0.7"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", image_path,
        "-vf", filter_complex,
        "-frames:v", "1",
        output_path,
    ]

    return cmd
