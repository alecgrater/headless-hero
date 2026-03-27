"""Video rendering pipeline — orchestrates FFmpeg to produce scene clips and full videos."""

import logging
import os
import subprocess
from pathlib import Path
from typing import Callable

from models.script import KenBurnsConfig, Scene, ScriptContent, TextOverlayConfig
from pipeline.ffmpeg_builder import (
    build_audio_concat_cmd,
    build_concat_cmd,
    build_scene_video_cmd,
    build_tiktok_cmd,
)

log = logging.getLogger(__name__)

_data_dir = Path(os.environ.get("YAM_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))

ProgressCallback = Callable[[float, str], None] | None

def _run_ffmpeg(cmd: list[str]) -> None:
    """Run an FFmpeg command, raising on failure."""
    log.info("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        log.error("FFmpeg stderr: %s", result.stderr)
        raise RuntimeError(f"FFmpeg failed (exit {result.returncode}): {result.stderr[-500:]}")

def _scene_image_path(script_id: str, scene_id: str) -> str:
    """Resolve local filesystem path for a scene image."""
    return str(_data_dir / "projects" / script_id / "images" / f"{scene_id}.png")

def _scene_audio_path(script_id: str, scene_id: str) -> str:
    """Resolve local filesystem path for a scene audio file."""
    return str(_data_dir / "projects" / script_id / "audio" / f"{scene_id}.mp3")

def _renders_dir(script_id: str) -> Path:
    d = _data_dir / "projects" / script_id / "renders"
    d.mkdir(parents=True, exist_ok=True)
    return d

def _all_scenes(content: ScriptContent) -> list[Scene]:
    """Flatten all scenes from all segments in order."""
    scenes: list[Scene] = []
    for seg in content.segments:
        for sc in seg.scenes:
            scenes.append(sc)
    return scenes

def render_scene_video(
    scene: Scene,
    script_id: str,
    width: int = 1920,
    height: int = 1080,
    fade_out: float = 0.3,
    force: bool = False,
) -> str:
    """Render a single scene to MP4 and return the web-relative path.

    Requires the scene's image and audio to already exist on disk.
    If force=False and the output is newer than source assets, skips re-render.
    """
    image_path = _scene_image_path(script_id, scene.id)
    audio_path = _scene_audio_path(script_id, scene.id)

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio not found: {audio_path}")

    renders = _renders_dir(script_id)
    scenes_dir = renders / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(scenes_dir / f"{scene.id}.mp4")

    # Cache check: skip if output exists and is newer than both source assets
    if not force and os.path.exists(output_path):
        out_mtime = os.path.getmtime(output_path)
        img_mtime = os.path.getmtime(image_path)
        aud_mtime = os.path.getmtime(audio_path)
        if out_mtime > img_mtime and out_mtime > aud_mtime:
            web_path = f"/static/projects/{script_id}/renders/scenes/{scene.id}.mp4"
            return web_path

    # Use audio duration if available, otherwise estimate
    duration = scene.audio_duration_seconds if scene.audio_duration_seconds > 0 else scene.duration_estimate_seconds

    kb = scene.ken_burns or KenBurnsConfig()
    toc = scene.text_overlay_config or TextOverlayConfig()

    cmd = build_scene_video_cmd(
        image_path=image_path,
        audio_path=audio_path,
        output_path=output_path,
        duration=duration,
        width=width,
        height=height,
        ken_burns_effect=kb.effect,
        ken_burns_intensity=kb.intensity,
        text_overlay=scene.text_overlay,
        overlay_position=toc.position,
        overlay_style=toc.style,
        overlay_animation=toc.animation,
        overlay_show_at=toc.show_at,
        overlay_duration=toc.duration,
        fade_out_duration=fade_out,
    )

    _run_ffmpeg(cmd)

    web_path = f"/static/projects/{script_id}/renders/scenes/{scene.id}.mp4"
    return web_path

def render_full_video(
    script_id: str,
    content: ScriptContent,
    width: int = 1920,
    height: int = 1080,
    fade_out: float = 0.3,
    on_progress: ProgressCallback = None,
) -> str:
    """Render all scenes then concatenate into a full YouTube video.

    Returns the web-relative path to the final MP4.
    """
    scenes = _all_scenes(content)
    total = len(scenes)
    clip_paths: list[str] = []

    for i, scene in enumerate(scenes):
        if on_progress:
            on_progress(i / total, f"Rendering scene {i + 1}/{total}")

        clip_path = render_scene_video(scene, script_id, width, height, fade_out)
        # Convert web path to local path for concat
        local_clip = str(_data_dir / "projects" / script_id / "renders" / "scenes" / f"{scene.id}.mp4")
        clip_paths.append(local_clip)

    if on_progress:
        on_progress(0.9, "Concatenating clips...")

    renders = _renders_dir(script_id)
    output_path = str(renders / "full_youtube.mp4")

    cmd, list_file = build_concat_cmd(clip_paths, output_path)
    try:
        _run_ffmpeg(cmd)
    finally:
        try:
            os.unlink(list_file)
        except OSError:
            pass

    if on_progress:
        on_progress(1.0, "Complete")

    return f"/static/projects/{script_id}/renders/full_youtube.mp4"

def render_segment_video(
    script_id: str,
    segment_idx: int,
    content: ScriptContent,
    width: int = 1080,
    height: int = 1920,
    on_progress: ProgressCallback = None,
) -> str:
    """Render a single segment as a 9:16 TikTok clip.

    First renders each scene in 16:9, then converts to 9:16 with blurred bg.
    Returns the web-relative path.
    """
    segment = content.segments[segment_idx]
    scenes = segment.scenes
    total = len(scenes)

    # First render each scene at 16:9
    clip_16_9_paths: list[str] = []
    for i, scene in enumerate(scenes):
        if on_progress:
            on_progress(i / (total + 2), f"Rendering scene {i + 1}/{total}")

        render_scene_video(scene, script_id, 1920, 1080)
        local_clip = str(_data_dir / "projects" / script_id / "renders" / "scenes" / f"{scene.id}.mp4")
        clip_16_9_paths.append(local_clip)

    # Concat if multiple scenes
    renders = _renders_dir(script_id)
    tiktok_dir = renders / "tiktok"
    tiktok_dir.mkdir(parents=True, exist_ok=True)

    if len(clip_16_9_paths) == 1:
        concat_path = clip_16_9_paths[0]
    else:
        concat_path = str(tiktok_dir / f"_temp_concat_{segment_idx}.mp4")
        cmd, list_file = build_concat_cmd(clip_16_9_paths, concat_path)
        try:
            _run_ffmpeg(cmd)
        finally:
            try:
                os.unlink(list_file)
            except OSError:
                pass

    if on_progress:
        on_progress(0.85, "Converting to 9:16...")

    # Convert to 9:16
    output_path = str(tiktok_dir / f"{segment_idx}.mp4")
    cmd = build_tiktok_cmd(concat_path, output_path, width, height)
    _run_ffmpeg(cmd)

    # Clean up temp concat if we created one
    if len(clip_16_9_paths) > 1:
        try:
            os.unlink(concat_path)
        except OSError:
            pass

    if on_progress:
        on_progress(1.0, "Complete")

    return f"/static/projects/{script_id}/renders/tiktok/{segment_idx}.mp4"

def render_all_segments(
    script_id: str,
    content: ScriptContent,
    width: int = 1080,
    height: int = 1920,
    on_progress: ProgressCallback = None,
) -> list[str]:
    """Render all segments as TikTok 9:16 clips. Returns list of web paths."""
    total = len(content.segments)
    results: list[str] = []
    for idx in range(total):
        if on_progress:
            on_progress(idx / total, f"Rendering segment {idx + 1}/{total}")

        def seg_progress(p: float, msg: str) -> None:
            if on_progress:
                overall = (idx + p) / total
                on_progress(overall, msg)

        path = render_segment_video(script_id, idx, content, width, height, seg_progress)
        results.append(path)

    if on_progress:
        on_progress(1.0, "All segments complete")

    return results

def export_full_audio(
    script_id: str,
    content: ScriptContent,
) -> str:
    """Concatenate all scene audio files into a single MP3.

    Returns the web-relative path to the output.
    """
    scenes = _all_scenes(content)
    audio_paths: list[str] = []
    for scene in scenes:
        path = _scene_audio_path(script_id, scene.id)
        if os.path.exists(path):
            audio_paths.append(path)

    if not audio_paths:
        raise FileNotFoundError("No audio files found for this script")

    renders = _renders_dir(script_id)
    output_path = str(renders / "full_audio.mp3")

    cmd, list_file = build_audio_concat_cmd(audio_paths, output_path)
    try:
        _run_ffmpeg(cmd)
    finally:
        try:
            os.unlink(list_file)
        except OSError:
            pass

    return f"/static/projects/{script_id}/renders/full_audio.mp3"
