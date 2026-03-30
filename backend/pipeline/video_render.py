"""Video rendering pipeline — orchestrates FFmpeg to produce scene clips and full videos."""

import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable

from config import DATA_DIR
from models.script import KenBurnsConfig, Scene, ScriptContent, TextOverlayConfig
from pipeline.ffmpeg_builder import (
    build_animated_scene_video_cmd,
    build_audio_concat_cmd,
    build_concat_cmd,
    build_concat_with_transitions_cmd,
    build_multiframe_scene_video_cmd,
    build_scene_video_cmd,
    build_title_card_zoom_cmd,
    build_tiktok_cmd,
)

log = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str], None] | None

def _run_ffmpeg(cmd: list[str]) -> None:
    """Run an FFmpeg command, raising on failure."""
    log.info("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        log.error("FFmpeg stderr: %s", result.stderr)
        raise RuntimeError(f"FFmpeg failed (exit {result.returncode}): {result.stderr[-500:]}")

def _sanitize_filename(name: str) -> str:
    """Strip unsafe filesystem characters and truncate to 80 chars."""
    clean = re.sub(r'[<>:"/\\|?*]', "", name).strip()
    return clean[:80] if clean else "Untitled"

def copy_to_downloads(title: str, src_path: str, dest_name: str) -> str:
    """Copy a rendered file to the downloads directory.

    Returns the destination path.
    """
    base = os.environ.get("DOWNLOADS_DIR", "") or str(Path.home() / "Downloads")
    folder = Path(base) / _sanitize_filename(title)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / dest_name
    shutil.copy2(src_path, dest)
    log.info("Copied to downloads: %s", dest)
    return str(dest)

def _scene_image_path(script_id: str, scene_id: str, image_url: str | None = None) -> str:
    """Resolve local filesystem path for a scene image.

    If image_url is provided (e.g. from a modifier), resolves the local path from the
    /static/projects/... URL. Otherwise checks for {scene_id}.png, then falls back to
    {scene_id}_f0.png (the first frame) for multi-frame naming.
    """
    base = DATA_DIR / "projects" / script_id / "images"

    # If a custom image_url was set (e.g. composite title card), resolve it
    if image_url:
        # image_url format: /static/projects/{script_id}/images/{filename}
        filename = image_url.rsplit("/", 1)[-1]
        custom = base / filename
        if custom.exists():
            return str(custom)

    plain = base / f"{scene_id}.png"
    if plain.exists():
        return str(plain)
    f0 = base / f"{scene_id}_f0.png"
    if f0.exists():
        return str(f0)
    # Return plain path (will trigger FileNotFoundError downstream)
    return str(plain)

def _scene_audio_path(script_id: str, scene_id: str) -> str:
    """Resolve local filesystem path for a scene audio file."""
    return str(DATA_DIR / "projects" / script_id / "audio" / f"{scene_id}.mp3")

def _renders_dir(script_id: str) -> Path:
    d = DATA_DIR / "projects" / script_id / "renders"
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
    speed: float = 1.0,
    modifier_ids: list[str] | None = None,
    brand: dict | None = None,
) -> str:
    """Render a single scene to MP4 and return the web-relative path.

    Requires the scene's image and audio to already exist on disk.
    If force=False and the output is newer than source assets, skips re-render.
    """
    # Run modifier pre-render hooks (e.g. generate title card images)
    if modifier_ids:
        import pipeline.modifiers  # noqa: F401
        from pipeline.modifiers.registry import get_active

        brand_dict = brand or {}
        for mod in get_active(modifier_ids):
            scene = mod.modify_scene_pre_render(scene, script_id, brand_dict)

    # Check for modifier render overrides (e.g. gameplay clips)
    renders = _renders_dir(script_id)
    scenes_dir = renders / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    speed_suffix = f"_{speed}x" if speed != 1.0 else ""
    filename = f"{scene.id}{speed_suffix}.mp4"
    output_path = str(scenes_dir / filename)

    if modifier_ids:
        from pipeline.modifiers.registry import get_active

        for mod in get_active(modifier_ids):
            override_cmd = mod.get_render_override(
                scene, script_id,
                width=width, height=height, fade_out=fade_out, speed=speed,
                output_path=output_path,
                font_family="",
            )
            if override_cmd is not None:
                _run_ffmpeg(override_cmd)
                return f"/static/projects/{script_id}/renders/scenes/{filename}"

    image_path = _scene_image_path(script_id, scene.id, getattr(scene, "image_url", None))
    audio_path = _scene_audio_path(script_id, scene.id)

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio not found: {audio_path}")

    # Multi-frame path: scene has frame_urls with >1 entry
    has_frames = bool(getattr(scene, "frame_urls", None)) and len(scene.frame_urls) > 1
    if has_frames:
        frame_local_paths = []
        for i in range(len(scene.frame_urls)):
            fp = str(DATA_DIR / "projects" / script_id / "images" / f"{scene.id}_f{i}.png")
            if os.path.exists(fp):
                frame_local_paths.append(fp)
        if len(frame_local_paths) > 1:
            # Cache check: output mtime vs ALL frame images + audio
            if not force and os.path.exists(output_path):
                out_mtime = os.path.getmtime(output_path)
                source_mtimes = [os.path.getmtime(fp) for fp in frame_local_paths]
                source_mtimes.append(os.path.getmtime(audio_path))
                if all(out_mtime > m for m in source_mtimes):
                    return f"/static/projects/{script_id}/renders/scenes/{filename}"

            duration = scene.audio_duration_seconds if scene.audio_duration_seconds > 0 else scene.duration_estimate_seconds
            kb = scene.ken_burns or KenBurnsConfig()
            toc = scene.text_overlay_config or TextOverlayConfig()
            brand_dict = brand or {}
            font_family = ""

            cmd = build_multiframe_scene_video_cmd(
                frame_paths=frame_local_paths,
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
                speed=speed,
                font_family=font_family,
            )
            _run_ffmpeg(cmd)
            return f"/static/projects/{script_id}/renders/scenes/{filename}"

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    # Resolve B image for animated scenes
    is_animated = getattr(scene, "is_animated", False)
    image_path_b = str(DATA_DIR / "projects" / script_id / "images" / f"{scene.id}_b.png") if is_animated else None
    if is_animated and (not image_path_b or not os.path.exists(image_path_b)):
        # Fall back to non-animated if B image missing
        is_animated = False
        image_path_b = None

    # Cache check: skip if output exists and is newer than all source assets
    if not force and os.path.exists(output_path):
        out_mtime = os.path.getmtime(output_path)
        img_mtime = os.path.getmtime(image_path)
        aud_mtime = os.path.getmtime(audio_path)
        source_mtimes = [img_mtime, aud_mtime]
        if is_animated and image_path_b:
            source_mtimes.append(os.path.getmtime(image_path_b))
        if all(out_mtime > m for m in source_mtimes):
            web_path = f"/static/projects/{script_id}/renders/scenes/{filename}"
            return web_path

    # Use audio duration if available, otherwise estimate
    duration = scene.audio_duration_seconds if scene.audio_duration_seconds > 0 else scene.duration_estimate_seconds

    # Title card zoom rendering — use composite card + zoompan
    if scene.is_title_card and scene.title_card_zoom_target:
        zoom = scene.title_card_zoom_target
        composite_path = str(DATA_DIR / "projects" / script_id / "images" / "composite_title_card.png")
        if os.path.exists(composite_path) and os.path.exists(audio_path):
            cmd = build_title_card_zoom_cmd(
                image_path=composite_path,
                audio_path=audio_path,
                output_path=output_path,
                duration=duration,
                target_x=zoom["x"],
                target_y=zoom["y"],
                target_radius=zoom["radius"],
                width=width,
                height=height,
                fade_out_duration=fade_out,
            )
            _run_ffmpeg(cmd)
            return f"/static/projects/{script_id}/renders/scenes/{filename}"

    kb = scene.ken_burns or KenBurnsConfig()
    toc = scene.text_overlay_config or TextOverlayConfig()
    brand_dict = brand or {}
    font_family = ""

    if is_animated and image_path_b:
        cmd = build_animated_scene_video_cmd(
            image_path_a=image_path,
            image_path_b=image_path_b,
            audio_path=audio_path,
            output_path=output_path,
            duration=duration,
            width=width,
            height=height,
            text_overlay=scene.text_overlay,
            overlay_position=toc.position,
            overlay_style=toc.style,
            overlay_animation=toc.animation,
            overlay_show_at=toc.show_at,
            overlay_duration=toc.duration,
            fade_out_duration=fade_out,
            speed=speed,
            font_family=font_family,
        )
    else:
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
            speed=speed,
            font_family=font_family,
        )

    _run_ffmpeg(cmd)

    web_path = f"/static/projects/{script_id}/renders/scenes/{filename}"
    return web_path

def render_full_video(
    script_id: str,
    content: ScriptContent,
    width: int = 1920,
    height: int = 1080,
    fade_out: float = 0.3,
    on_progress: ProgressCallback = None,
    title: str = "",
    speed: float = 1.0,
    modifier_ids: list[str] | None = None,
    brand: dict | None = None,
) -> str:
    """Render all scenes then concatenate into a full YouTube video.

    Returns the web-relative path to the final MP4.
    """
    scenes = _all_scenes(content)
    total = len(scenes)
    clip_paths: list[str] = []
    scene_transitions: list[str] = []

    speed_suffix = f"_{speed}x" if speed != 1.0 else ""

    for i, scene in enumerate(scenes):
        if on_progress:
            on_progress(i / total, f"Rendering scene {i + 1}/{total}")

        clip_path = render_scene_video(scene, script_id, width, height, fade_out, speed=speed, modifier_ids=modifier_ids, brand=brand)
        # Convert web path to local path for concat
        filename = f"{scene.id}{speed_suffix}.mp4"
        local_clip = str(DATA_DIR / "projects" / script_id / "renders" / "scenes" / filename)
        clip_paths.append(local_clip)
        scene_transitions.append(getattr(scene, "scene_transition", "") or "")

    if on_progress:
        on_progress(0.9, "Concatenating clips...")

    renders = _renders_dir(script_id)
    output_filename = f"full_youtube{speed_suffix}.mp4"
    output_path = str(renders / output_filename)

    # Use transitions if any non-empty scene_transition values exist
    has_transitions = any(t and t != "" for t in scene_transitions)
    if has_transitions:
        cmd, list_file = build_concat_with_transitions_cmd(clip_paths, scene_transitions, output_path)
    else:
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

    web_path = f"/static/projects/{script_id}/renders/{output_filename}"

    if title:
        try:
            speed_label = f" ({speed}x)" if speed != 1.0 else ""
            copy_to_downloads(title, output_path, f"{_sanitize_filename(title)} - YouTube{speed_label}.mp4")
        except Exception:
            log.warning("Failed to copy to downloads", exc_info=True)

    return web_path

def render_segment_video(
    script_id: str,
    segment_idx: int,
    content: ScriptContent,
    width: int = 1080,
    height: int = 1920,
    on_progress: ProgressCallback = None,
    speed: float = 1.0,
    modifier_ids: list[str] | None = None,
    brand: dict | None = None,
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

        render_scene_video(scene, script_id, 1920, 1080, speed=speed, modifier_ids=modifier_ids, brand=brand)
        speed_suffix = f"_{speed}x" if speed != 1.0 else ""
        local_clip = str(DATA_DIR / "projects" / script_id / "renders" / "scenes" / f"{scene.id}{speed_suffix}.mp4")
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
    title: str = "",
    speed: float = 1.0,
    modifier_ids: list[str] | None = None,
    brand: dict | None = None,
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

        path = render_segment_video(script_id, idx, content, width, height, seg_progress, speed=speed, modifier_ids=modifier_ids, brand=brand)
        results.append(path)

    if on_progress:
        on_progress(1.0, "All segments complete")

    if title:
        speed_label = f" ({speed}x)" if speed != 1.0 else ""
        for idx, web_path in enumerate(results):
            try:
                local = str(DATA_DIR / "projects" / script_id / "renders" / "tiktok" / f"{idx}.mp4")
                copy_to_downloads(title, local, f"{_sanitize_filename(title)} - TikTok Segment {idx + 1}{speed_label}.mp4")
            except Exception:
                log.warning("Failed to copy segment %d to downloads", idx, exc_info=True)

    return results

def export_full_audio(
    script_id: str,
    content: ScriptContent,
    title: str = "",
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

    web_path = f"/static/projects/{script_id}/renders/full_audio.mp3"

    if title:
        try:
            copy_to_downloads(title, output_path, f"{_sanitize_filename(title)} - Audio.mp3")
        except Exception:
            log.warning("Failed to copy audio to downloads", exc_info=True)

    return web_path
