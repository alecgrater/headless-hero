"""Short-form video rendering pipeline — produces 1080x1920 vertical videos with subtitles."""

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Callable

from models.script import Scene, ScriptContent
from pipeline.ass_builder import generate_ass_for_scene
from pipeline.ffmpeg_builder import build_concat_cmd, build_shortform_scene_cmd
from pipeline.video_render import _run_ffmpeg, _sanitize_filename, copy_to_downloads

log = logging.getLogger(__name__)

_data_dir = Path(os.environ.get("HH_DATA_DIR", os.environ.get("YAM_DATA_DIR", Path(__file__).resolve().parents[2] / "data")))

ProgressCallback = Callable[[float, str], None] | None


def _scene_image_path(script_id: str, scene_id: str) -> str:
    return str(_data_dir / "projects" / script_id / "images" / f"{scene_id}.png")


def _scene_audio_path(script_id: str, scene_id: str) -> str:
    return str(_data_dir / "projects" / script_id / "audio" / f"{scene_id}.mp3")


def _renders_dir(script_id: str) -> Path:
    d = _data_dir / "projects" / script_id / "renders"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _all_scenes(content: ScriptContent) -> list[Scene]:
    return [sc for seg in content.segments for sc in seg.scenes]


def render_shortform_scene(
    scene: Scene,
    script_id: str,
    speed: float = 1.0,
    modifier_ids: list[str] | None = None,
    brand: dict | None = None,
    accent_color: str = "#FFFF00",
) -> str:
    """Render a single shortform scene to MP4 at 1080x1920.

    Returns local filesystem path to the rendered scene.
    """
    width, height = 1080, 1920

    # Run modifier pre-render hooks
    if modifier_ids:
        import pipeline.modifiers  # noqa: F401
        from pipeline.modifiers.registry import get_active

        brand_dict = brand or {}
        for mod in get_active(modifier_ids):
            scene = mod.modify_scene_pre_render(scene, script_id, brand_dict)

    renders = _renders_dir(script_id)
    scenes_dir = renders / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    speed_suffix = f"_{speed}x" if speed != 1.0 else ""
    filename = f"{scene.id}_sf{speed_suffix}.mp4"
    output_path = str(scenes_dir / filename)

    # Check for modifier render overrides
    if modifier_ids:
        from pipeline.modifiers.registry import get_active

        for mod in get_active(modifier_ids):
            override_cmd = mod.get_render_override(
                scene, script_id,
                width=width, height=height, fade_out=0, speed=speed,
                output_path=output_path,
                font_family=(brand or {}).get("font", ""),
            )
            if override_cmd is not None:
                _run_ffmpeg(override_cmd)
                return output_path

    image_path = _scene_image_path(script_id, scene.id)
    audio_path = _scene_audio_path(script_id, scene.id)

    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio not found: {audio_path}")

    duration = scene.audio_duration_seconds if scene.audio_duration_seconds > 0 else scene.duration_estimate_seconds

    # Generate ASS subtitles from word timestamps
    renders = _renders_dir(script_id)
    ass_path = None
    brand_dict = brand or {}
    if scene.word_timestamps:
        ass_path = generate_ass_for_scene(
            word_timestamps=scene.word_timestamps,
            duration=duration,
            width=width,
            height=height,
            accent_color=accent_color,
            mode="portrait",
            renders_dir=str(renders),
            scene_id=scene.id,
            speed=speed,
            font_name=brand_dict.get("font", ""),
        )

    cmd = build_shortform_scene_cmd(
        image_path=image_path,
        audio_path=audio_path,
        output_path=output_path,
        duration=duration,
        word_timestamps=scene.word_timestamps,
        speed=speed,
        width=width,
        height=height,
        ass_path=ass_path,
    )

    _run_ffmpeg(cmd)
    return output_path


def render_shortform_video(
    script_id: str,
    content: ScriptContent,
    on_progress: ProgressCallback = None,
    title: str = "",
    speed: float = 1.0,
    modifier_ids: list[str] | None = None,
    brand: dict | None = None,
) -> str:
    """Render all scenes and concatenate into a single shortform video.

    Returns the web-relative path to the final 1080x1920 MP4.
    """
    scenes = _all_scenes(content)
    total = len(scenes)
    clip_paths: list[str] = []

    # Extract accent color from brand color palette (first color), fallback yellow
    accent_color = "#FFFF00"
    if brand and brand.get("color_palette"):
        palette = brand["color_palette"].split(",")
        if palette and palette[0].strip():
            accent_color = palette[0].strip()

    for i, scene in enumerate(scenes):
        if on_progress:
            on_progress(i / total, f"Rendering scene {i + 1}/{total}")

        local_path = render_shortform_scene(
            scene, script_id, speed=speed,
            modifier_ids=modifier_ids, brand=brand,
            accent_color=accent_color,
        )
        clip_paths.append(local_path)

    if on_progress:
        on_progress(0.9, "Concatenating clips...")

    renders = _renders_dir(script_id)
    speed_suffix = f"_{speed}x" if speed != 1.0 else ""
    output_filename = f"shortform{speed_suffix}.mp4"
    output_path = str(renders / output_filename)

    cmd, list_file = build_concat_cmd(clip_paths, output_path)
    try:
        _run_ffmpeg(cmd)
    finally:
        try:
            os.unlink(list_file)
        except OSError:
            pass

    # Copy to platform-named files (all use same 1080x1920 spec)
    platforms = []
    try:
        record_path = _data_dir / "projects" / script_id
        # Try to determine platforms from script DB record
        # For now, just create standard copies
        platforms = ["youtube_shorts", "tiktok", "instagram_reels"]
    except Exception:
        pass

    for platform in platforms:
        platform_path = str(renders / f"shortform_{platform}{speed_suffix}.mp4")
        try:
            shutil.copy2(output_path, platform_path)
        except Exception:
            log.warning("Failed to copy to %s", platform_path)

    if on_progress:
        on_progress(1.0, "Complete")

    web_path = f"/static/projects/{script_id}/renders/{output_filename}"

    if title:
        try:
            speed_label = f" ({speed}x)" if speed != 1.0 else ""
            copy_to_downloads(title, output_path, f"{_sanitize_filename(title)} - Short-Form{speed_label}.mp4")
        except Exception:
            log.warning("Failed to copy to downloads", exc_info=True)

    return web_path
