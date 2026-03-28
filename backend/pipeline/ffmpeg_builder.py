"""FFmpeg command-line argument builder for video assembly.

Constructs ffmpeg CLI argument lists for:
- Scene video (image + audio + Ken Burns + text overlay -> MP4)
- Video concat (multiple clips -> one video via concat demuxer)
- Audio concat (multiple MP3s -> one MP3)
- TikTok 9:16 reformat (blurred-background fill)
"""

import logging
import os
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

# Detect drawtext filter availability once at import time
def _has_drawtext() -> bool:
    try:
        result = subprocess.run(
            ["ffmpeg", "-filters"],
            capture_output=True, text=True, timeout=5,
        )
        return "drawtext" in result.stdout
    except Exception:
        return False

_DRAWTEXT_AVAILABLE = _has_drawtext()
if not _DRAWTEXT_AVAILABLE:
    logger.warning("FFmpeg drawtext filter not available — text overlays will be skipped. "
                    "Install FFmpeg with libfreetype to enable text overlays.")

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
        f"fontcolor='{fontcolor}@{alpha_expr}'" if animation in ("fade_in", "typewriter") else f"fontcolor={fontcolor}",
        f"x='{x_expr}'",
        f"y='{y_expr}'",
        f"borderw={borderw}",
        f"bordercolor=black",
        f"shadowx={shadowx}",
        f"shadowy={shadowy}",
        f"shadowcolor='black@0.6'",
        f"enable='{enable}'",
    ]

    return "drawtext=" + ":".join(parts)

def _build_atempo_chain(speed: float) -> str:
    """Build chained atempo filters for pitch-corrected speed change.

    Each atempo instance handles 0.5-2.0x, so we chain for wider ranges.
    """
    filters: list[str] = []
    remaining = speed
    while remaining > 2.0:
        filters.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5:
        filters.append("atempo=0.5")
        remaining /= 0.5
    filters.append(f"atempo={remaining:.4f}")
    return ",".join(filters)

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
    speed: float = 1.0,
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

    # Text overlay (requires drawtext filter / libfreetype)
    if text_overlay and _DRAWTEXT_AVAILABLE:
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

    # Speed adjustment for video
    if speed != 1.0:
        filters.append(f"setpts=PTS/{speed}")

    # Fade out at end
    effective_duration = duration / speed if speed != 1.0 else duration
    if fade_out_duration > 0:
        fade_start = max(0, effective_duration - fade_out_duration)
        filters.append(f"fade=t=out:st={fade_start}:d={fade_out_duration}")

    filter_chain = ",".join(filters)

    # Build audio mapping — with speed adjustment if needed
    if speed != 1.0:
        atempo_chain = _build_atempo_chain(speed)
        filter_complex = f"[0:v]{filter_chain}[vout];[1:a]{atempo_chain}[aout]"
        audio_map = ["[aout]"]
    else:
        filter_complex = f"[0:v]{filter_chain}[vout]"
        audio_map = ["1:a"]

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-i", audio_path,
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", *audio_map,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-t", str(effective_duration),
        "-shortest",
        output_path,
    ]

    return cmd

def build_video_clip_scene_cmd(
    clip_path: str,
    audio_path: str,
    output_path: str,
    duration: float,
    width: int = 1920,
    height: int = 1080,
    text_overlay: str = "",
    overlay_position: str = "lower_third",
    overlay_style: str = "default",
    overlay_animation: str = "fade_in",
    overlay_show_at: float = 0.0,
    overlay_duration: float = 0.0,
    fade_out_duration: float = 0.3,
    speed: float = 1.0,
    gameplay_volume: float = 0.15,
) -> list[str]:
    """Build FFmpeg command for a video clip scene (gameplay + narration audio mix).

    Unlike build_scene_video_cmd(), the input is a video file (not a looped image),
    so there's no zoompan/Ken Burns — the real video provides its own motion.
    Gameplay audio is mixed at low volume underneath full-volume narration.
    """
    effective_duration = duration / speed if speed != 1.0 else duration

    # Video filters: scale + pad to target resolution
    vfilters: list[str] = [
        f"scale={width}:{height}:force_original_aspect_ratio=decrease",
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black",
        "setsar=1",
    ]

    # Text overlay
    if text_overlay and _DRAWTEXT_AVAILABLE:
        dt = _drawtext_filter(
            text=text_overlay,
            position=overlay_position,
            style=overlay_style,
            animation=overlay_animation,
            show_at=overlay_show_at,
            overlay_duration=overlay_duration,
            scene_duration=duration,
        )
        vfilters.append(dt)

    # Speed adjustment for video
    if speed != 1.0:
        vfilters.append(f"setpts=PTS/{speed}")

    # Fade out at end
    if fade_out_duration > 0:
        fade_start = max(0, effective_duration - fade_out_duration)
        vfilters.append(f"fade=t=out:st={fade_start}:d={fade_out_duration}")

    v_chain = ",".join(vfilters)

    # Audio: mix gameplay audio (low volume) with narration (full volume)
    # [0:a] = gameplay audio, [1:a] = narration audio
    # amix with volume weighting
    if speed != 1.0:
        atempo_chain = _build_atempo_chain(speed)
        filter_complex = (
            f"[0:v]{v_chain}[vout];"
            f"[0:a]volume={gameplay_volume},{atempo_chain}[gaud];"
            f"[1:a]{atempo_chain}[naud];"
            f"[gaud][naud]amix=inputs=2:duration=shortest[aout]"
        )
        audio_map = ["[aout]"]
    else:
        filter_complex = (
            f"[0:v]{v_chain}[vout];"
            f"[0:a]volume={gameplay_volume}[gaud];"
            f"[gaud][1:a]amix=inputs=2:duration=shortest[aout]"
        )
        audio_map = ["[aout]"]

    cmd = [
        "ffmpeg", "-y",
        "-i", clip_path,
        "-i", audio_path,
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", *audio_map,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-t", str(effective_duration),
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

def build_animated_scene_video_cmd(
    image_path_a: str,
    image_path_b: str,
    audio_path: str,
    output_path: str,
    duration: float,
    width: int = 1920,
    height: int = 1080,
    flip_interval: float = 0.7,
    text_overlay: str = "",
    overlay_position: str = "lower_third",
    overlay_style: str = "default",
    overlay_animation: str = "fade_in",
    overlay_show_at: float = 0.0,
    overlay_duration: float = 0.0,
    fade_out_duration: float = 0.3,
    speed: float = 1.0,
) -> list[str]:
    """Build FFmpeg command for an animated A/B flip scene (two images alternating).

    Uses blend filter with conditional expression to alternate between image A and B
    at the specified flip_interval. No Ken Burns — the alternation IS the motion.
    """
    fps = 30
    frames_per_flip = int(flip_interval * fps)

    # Build filter: loop both images, then use blend to alternate
    # [0:v] = image A, [1:v] = image B, [2:a] = audio
    filters_a = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,loop=loop=-1:size=1:start=0,fps={fps}"
    filters_b = f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,setsar=1,loop=loop=-1:size=1:start=0,fps={fps}"

    # blend filter: use 'if(lt(mod(n,2*F),F),1,0)' to toggle weight between A and B
    # When weight=1.0, output=A; when weight=0.0, output=B
    blend_expr = f"if(lt(mod(n\\,{2*frames_per_flip})\\,{frames_per_flip})\\,1\\,0)"
    blend_filter = f"blend=all_expr='{blend_expr}*A+(1-{blend_expr})*B'"

    post_filters: list[str] = []

    # Text overlay
    if text_overlay and _DRAWTEXT_AVAILABLE:
        dt = _drawtext_filter(
            text=text_overlay,
            position=overlay_position,
            style=overlay_style,
            animation=overlay_animation,
            show_at=overlay_show_at,
            overlay_duration=overlay_duration,
            scene_duration=duration,
        )
        post_filters.append(dt)

    # Speed adjustment
    if speed != 1.0:
        post_filters.append(f"setpts=PTS/{speed}")

    # Fade out
    effective_duration = duration / speed if speed != 1.0 else duration
    if fade_out_duration > 0:
        fade_start = max(0, effective_duration - fade_out_duration)
        post_filters.append(f"fade=t=out:st={fade_start}:d={fade_out_duration}")

    post_chain = ("," + ",".join(post_filters)) if post_filters else ""

    if speed != 1.0:
        atempo_chain = _build_atempo_chain(speed)
        filter_complex = (
            f"[0:v]{filters_a}[va];"
            f"[1:v]{filters_b}[vb];"
            f"[va][vb]{blend_filter}{post_chain}[vout];"
            f"[2:a]{atempo_chain}[aout]"
        )
        audio_map = ["[aout]"]
    else:
        filter_complex = (
            f"[0:v]{filters_a}[va];"
            f"[1:v]{filters_b}[vb];"
            f"[va][vb]{blend_filter}{post_chain}[vout]"
        )
        audio_map = ["2:a"]

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", image_path_a,
        "-loop", "1", "-i", image_path_b,
        "-i", audio_path,
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", *audio_map,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-t", str(effective_duration),
        "-shortest",
        output_path,
    ]

    return cmd


def build_title_card_image_cmd(
    output_path: str,
    title_text: str,
    color_primary: str = "#1a1a2e",
    color_secondary: str = "#16213e",
    width: int = 1920,
    height: int = 1080,
) -> list[str]:
    """Build FFmpeg command to generate a title card PNG (solid color + centered text).

    Returns a list of args suitable for subprocess.run().
    """
    # Strip '#' for FFmpeg color format
    bg_color = color_primary.lstrip("#")

    escaped = _escape_drawtext(title_text)

    vf = (
        f"drawtext=text='{escaped}'"
        f":fontsize=72:fontcolor=white"
        f":x='(w-text_w)/2':y='(h-text_h)/2'"
        f":borderw=3:bordercolor=black"
        f":shadowx=3:shadowy=3:shadowcolor='black@0.6'"
    ) if _DRAWTEXT_AVAILABLE else ""

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c=0x{bg_color}:s={width}x{height}:d=1",
    ]

    if vf:
        cmd += ["-vf", vf]

    cmd += [
        "-frames:v", "1",
        output_path,
    ]

    return cmd


def build_shortform_scene_cmd(
    image_path: str,
    audio_path: str,
    output_path: str,
    duration: float,
    word_timestamps: list[dict] | None = None,
    speed: float = 1.0,
    width: int = 1080,
    height: int = 1920,
) -> list[str]:
    """Build FFmpeg command for a short-form scene (9:16 with word-synced subtitles).

    Features:
    - Subtle zoom motion (zoompan)
    - Word-synced subtitle overlay (3-word chunks)
    - Hard cuts (no fade-out)
    - Speed adjustment via atempo
    """
    fps = 30
    effective_duration = duration / speed if speed != 1.0 else duration
    duration_frames = int(effective_duration * fps)

    filters: list[str] = []

    # Subtle zoom motion
    filters.append(
        f"zoompan=z='min(zoom+0.001,1.05)':d={duration_frames}:s={width}x{height}:fps={fps}"
        f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    )

    # Ensure correct output size for any input aspect ratio
    filters.append(f"scale={width}:{height}:force_original_aspect_ratio=decrease")
    filters.append(f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black")
    filters.append("setsar=1")

    # Speed adjustment for video
    if speed != 1.0:
        filters.append(f"setpts=PTS/{speed}")

    # Word-synced subtitles (3-word chunks)
    if word_timestamps and _DRAWTEXT_AVAILABLE:
        # Group words into chunks of 3
        chunks: list[dict] = []
        for i in range(0, len(word_timestamps), 3):
            chunk_words = word_timestamps[i : i + 3]
            text = " ".join(w["word"] for w in chunk_words)
            start_s = chunk_words[0]["start_ms"] / 1000.0
            end_s = chunk_words[-1]["end_ms"] / 1000.0
            if speed != 1.0:
                start_s /= speed
                end_s /= speed
            chunks.append({"text": text, "start": start_s, "end": end_s})

        for chunk in chunks:
            escaped = _escape_drawtext(chunk["text"].upper())
            dt = (
                f"drawtext=text='{escaped}'"
                f":fontsize=80:fontcolor=white"
                f":x='(w-text_w)/2':y='h*0.80'"
                f":borderw=4:bordercolor=black"
                f":shadowx=2:shadowy=2:shadowcolor='black@0.7'"
                f":enable='between(t,{chunk['start']},{chunk['end']})'"
            )
            filters.append(dt)
    elif not word_timestamps and _DRAWTEXT_AVAILABLE:
        # Fallback: no timestamps available — skip subtitles
        pass

    filter_chain = ",".join(filters)

    # Audio mapping
    if speed != 1.0:
        atempo_chain = _build_atempo_chain(speed)
        filter_complex = f"[0:v]{filter_chain}[vout];[1:a]{atempo_chain}[aout]"
        audio_map = ["[aout]"]
    else:
        filter_complex = f"[0:v]{filter_chain}[vout]"
        audio_map = ["1:a"]

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-i", audio_path,
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", *audio_map,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-t", str(effective_duration),
        "-shortest",
        output_path,
    ]

    return cmd


def build_shortform_clip_scene_cmd(
    clip_path: str,
    audio_path: str,
    output_path: str,
    duration: float,
    width: int = 1080,
    height: int = 1920,
    speed: float = 1.0,
) -> list[str]:
    """Build FFmpeg command for a gameplay clip in shortform (9:16) format.

    Center-crops the 16:9 source clip to fill the 9:16 portrait frame.
    """
    effective_duration = duration / speed if speed > 0 else duration

    # Center-crop: scale to fit height, then crop to width
    # For a 16:9 source going to 9:16: scale so height matches, crop center
    vf_parts = [
        f"scale=-1:{height}",
        f"crop={width}:{height}",
    ]

    if speed != 1.0:
        vf_parts.append(f"setpts={1.0 / speed}*PTS")

    vf = ",".join(vf_parts)

    # Audio
    af_parts: list[str] = []
    if speed != 1.0:
        af_parts.append(_build_atempo_chain(speed))

    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", clip_path,
        "-i", audio_path,
        "-filter_complex",
        f"[0:v]{vf}[v];[1:a]{''.join(f'{f},' for f in af_parts).rstrip(',')}aformat=sample_rates=44100:channel_layouts=stereo[a]"
        if af_parts else
        f"[0:v]{vf}[v];[1:a]aformat=sample_rates=44100:channel_layouts=stereo[a]",
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-r", "30",
        "-pix_fmt", "yuv420p",
        "-t", str(effective_duration),
        "-shortest",
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
    filter_complex = (
        f"[0:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black,"
        f"drawbox=x=0:y=ih-80:w=iw:h=80:color=#{bar_color.replace('0x', '')}@0.85:t=fill"
    )

    if _DRAWTEXT_AVAILABLE:
        escaped = _escape_drawtext(title_text)
        filter_complex += (
            f",drawtext=text='{escaped}':fontsize=52:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2:"
            f"borderw=3:bordercolor=black:shadowx=3:shadowy=3:shadowcolor='black@0.7'"
        )

    cmd = [
        "ffmpeg", "-y",
        "-i", image_path,
        "-vf", filter_complex,
        "-frames:v", "1",
        output_path,
    ]

    return cmd


def _build_animated_drawtext(phrase: dict, speed: float) -> str | None:
    """Build an animated drawtext filter for a key-moment text pop."""
    words = phrase.get("words", [])
    start_ms = phrase.get("start_ms", 0)
    end_ms = phrase.get("end_ms", 0)
    animation = phrase.get("animation", "pop")
    uppercase = phrase.get("uppercase", True)

    if not words:
        return None

    phrase_text = " ".join(words)
    if uppercase:
        phrase_text = phrase_text.upper()
    escaped = _escape_drawtext(phrase_text)

    show_at = (start_ms / 1000.0) / speed if speed != 1.0 else start_ms / 1000.0
    hide_at = (end_ms / 1000.0) / speed if speed != 1.0 else end_ms / 1000.0
    dur = hide_at - show_at

    # Animation-specific fontsize expression using local time (t - show_at)
    base_size = 72
    if animation == "pop":
        # 0→110%→100% over 300ms with overshoot settle
        fs = (
            f"if(lt(t-{show_at},0.15),"
            f"{base_size}*1.1*(t-{show_at})/0.15,"
            f"if(lt(t-{show_at},0.3),"
            f"{base_size}*(1.1-0.1*(t-{show_at}-0.15)/0.15),"
            f"{base_size}))"
        )
    elif animation == "slam":
        # Instant full size — the abruptness IS the effect
        fs = str(base_size)
    elif animation == "scale_up":
        # Grow from 50% to 100% over phrase duration
        fs = (
            f"if(lt(t-{show_at},{dur}),"
            f"{base_size}*(0.5+0.5*(t-{show_at})/{dur}),"
            f"{base_size})"
        )
    elif animation == "fade_in":
        # Full size throughout (alpha handles the animation)
        fs = str(base_size)
    else:
        fs = str(base_size)

    # Alpha expression for fade_in animation
    if animation == "fade_in":
        alpha = f"if(lt(t-{show_at},0.3),(t-{show_at})/0.3,1)"
        color_expr = f"fontcolor_expr='white@{{{alpha}}}'"
    else:
        color_expr = "fontcolor=white"

    dt = (
        f"drawtext=text='{escaped}'"
        f":fontsize='{fs}'"
        f":{color_expr}"
        f":x='(w-text_w)/2':y='h*0.75'"
        f":box=1:boxcolor='black@0.65':boxborderw=14"
        f":enable='between(t,{show_at},{hide_at})'"
    )
    return dt


def build_auto_edit_scene_cmd(
    image_path: str,
    audio_path: str,
    output_path: str,
    duration: float,
    motion_profile: str = "slow_zoom_in",
    text_phrases: list[dict] | None = None,
    accent_color: str = "#00FFFF",
    width: int = 1920,
    height: int = 1080,
    speed: float = 1.0,
) -> list[str]:
    """Build FFmpeg command for an auto-edited scene with motion + word-synced text overlays.

    Args:
        motion_profile: slow_zoom_in | slow_zoom_out | slow_pan
        text_phrases: [{words, start_ms, end_ms, highlight_color}]
        accent_color: hex color for word highlighting
        speed: playback speed multiplier (1.0 = normal)
    """
    fps = 30
    effective_duration = duration / speed if speed != 1.0 else duration
    duration_frames = int(effective_duration * fps)

    filters: list[str] = []

    # Motion profile — maps to Ken Burns effect
    if motion_profile == "slow_zoom_in":
        zoom_speed = 0.0004
        filters.append(
            f"zoompan=d={duration_frames}:s={width}x{height}:fps={fps}"
            f":z='1+{zoom_speed}*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        )
    elif motion_profile == "slow_zoom_out":
        zoom_speed = 0.0004
        max_z = 1 + zoom_speed * duration_frames
        filters.append(
            f"zoompan=d={duration_frames}:s={width}x{height}:fps={fps}"
            f":z='{max_z}-{zoom_speed}*on':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        )
    elif motion_profile == "slow_pan":
        filters.append(
            f"zoompan=d={duration_frames}:s={width}x{height}:fps={fps}"
            f":z='1.08':x='iw*0.04*on/{duration_frames}':y='ih/2-(ih/zoom/2)'"
        )
    else:
        filters.append(
            f"zoompan=d={duration_frames}:s={width}x{height}:fps={fps}"
            f":z='1':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        )

    # Apply video speed adjustment
    if speed != 1.0:
        filters.append(f"setpts=PTS/{speed}")

    filters.append(f"scale={width}:{height}:force_original_aspect_ratio=decrease")
    filters.append(f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black")
    filters.append("setsar=1")

    # Animated text pops at key moments (adjust timing for speed)
    if text_phrases and _DRAWTEXT_AVAILABLE:
        for phrase in text_phrases:
            dt = _build_animated_drawtext(phrase, speed)
            if dt:
                filters.append(dt)

    filter_chain = ",".join(filters)
    filter_complex = f"[0:v]{filter_chain}[vout]"

    # Build audio mapping — with speed adjustment if needed
    if speed != 1.0:
        atempo_chain = _build_atempo_chain(speed)
        audio_filter = f"[1:a]{atempo_chain}[aout]"
        filter_complex = f"{filter_complex};{audio_filter}"
        audio_map = "[aout]"
    else:
        audio_map = "1:a"

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", image_path,
        "-i", audio_path,
        "-filter_complex", filter_complex,
        "-map", "[vout]",
        "-map", audio_map,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-t", str(effective_duration),
        "-shortest",
        output_path,
    ]

    return cmd


def build_concat_with_transitions_cmd(
    clip_paths: list[str],
    transitions: list[str],
    output_path: str,
    dip_duration: float = 0.3,
) -> tuple[list[str], str]:
    """Build FFmpeg command to concatenate clips with optional dip-to-black transitions.

    Args:
        clip_paths: list of input MP4 paths
        transitions: list of transition types per scene (same length as clip_paths).
                     "dip_to_black" inserts a brief black frame between this clip and the previous.
                     "hard_cut" uses simple concat.
        dip_duration: total dip-to-black duration in seconds
        output_path: final output MP4 path

    If all transitions are hard_cut, falls back to simple concat demuxer.
    Returns (command args, path to temp concat list file).
    """
    has_dips = any(t == "dip_to_black" for t in transitions)

    if not has_dips:
        fd, list_path = tempfile.mkstemp(suffix=".txt", prefix="ffconcat_auto_")
        with os.fdopen(fd, "w") as f:
            for clip in clip_paths:
                f.write(f"file '{clip}'\n")
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", list_path,
            "-c", "copy",
            output_path,
        ]
        return cmd, list_path

    # Insert short black video clips at dip_to_black transition points
    black_path = tempfile.mktemp(suffix=".mp4", prefix="ffblack_")
    black_cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"color=black:s=1920x1080:d={dip_duration}:r=30",
        "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=stereo:d={dip_duration}",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        black_path,
    ]
    subprocess.run(black_cmd, capture_output=True, timeout=30)

    fd, list_path = tempfile.mkstemp(suffix=".txt", prefix="ffconcat_auto_")
    with os.fdopen(fd, "w") as f:
        for i, clip in enumerate(clip_paths):
            if i > 0 and i < len(transitions) and transitions[i] == "dip_to_black":
                f.write(f"file '{black_path}'\n")
            f.write(f"file '{clip}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", list_path,
        "-c", "copy",
        output_path,
    ]

    return cmd, list_path
