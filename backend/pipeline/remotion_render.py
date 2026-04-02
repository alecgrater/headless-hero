"""Remotion rendering pipeline — orchestrates Remotion CLI to produce videos.

Replaces FFmpeg-based scene rendering with Remotion React compositions.
Keeps the same interface (render_full_video, render_scene_preview) so the
API layer can swap to this module with minimal changes.
"""

import json
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable

from config import DATA_DIR
from models.script import KenBurnsConfig, Scene, SceneFX, ScriptContent

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str], None] | None

# Path to the remotion project at repo root
REMOTION_DIR = Path(__file__).resolve().parents[2] / "remotion"
REMOTION_ENTRY = REMOTION_DIR / "src" / "index.ts"


BACKEND_STATIC_BASE = "http://localhost:8420/static/projects"


def _to_remotion_path(abs_path: str) -> str:
    """Convert absolute data path to a URL served by the FastAPI backend."""
    projects_dir = str(DATA_DIR / "projects")
    if abs_path.startswith(projects_dir):
        relative = abs_path[len(projects_dir):]
        return f"{BACKEND_STATIC_BASE}{relative}"
    return abs_path


def _sanitize_filename(name: str) -> str:
    """Strip unsafe filesystem characters and truncate to 80 chars."""
    clean = re.sub(r'[<>:"/\\|?*]', "", name).strip()
    return clean[:80] if clean else "Untitled"


def _renders_dir(script_id: str) -> Path:
    d = DATA_DIR / "projects" / script_id / "renders"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _scene_image_path(script_id: str, scene_id: str, image_url: str | None = None) -> str | None:
    """Resolve local filesystem path for a scene image. Returns None if not found."""
    base = DATA_DIR / "projects" / script_id / "images"

    if image_url:
        filename = image_url.rsplit("/", 1)[-1]
        custom = base / filename
        if custom.exists():
            return _to_remotion_path(str(custom))

    plain = base / f"{scene_id}.png"
    if plain.exists():
        return _to_remotion_path(str(plain))
    f0 = base / f"{scene_id}_f0.png"
    if f0.exists():
        return _to_remotion_path(str(f0))
    return None


def _scene_audio_path(script_id: str, scene_id: str) -> str | None:
    """Resolve local filesystem path for a scene audio file. Returns None if not found."""
    path = DATA_DIR / "projects" / script_id / "audio" / f"{scene_id}.mp3"
    return _to_remotion_path(str(path)) if path.exists() else None


def _scene_frame_paths(script_id: str, scene: Scene) -> list[str]:
    """Resolve local filesystem paths for multi-frame scene images."""
    paths = []
    if scene.frame_urls and len(scene.frame_urls) > 1:
        for i in range(len(scene.frame_urls)):
            fp = DATA_DIR / "projects" / script_id / "images" / f"{scene.id}_f{i}.png"
            if fp.exists():
                paths.append(_to_remotion_path(str(fp)))
    return paths


def _video_clip_path(script_id: str, scene: Scene) -> str | None:
    """Resolve local filesystem path for a video clip."""
    if not scene.video_clip_url:
        return None
    # video_clip_url format: /static/projects/{script_id}/...
    filename = scene.video_clip_url.rsplit("/", 1)[-1]
    path = DATA_DIR / "projects" / script_id / "media" / filename
    if path.exists():
        return _to_remotion_path(str(path))
    # Try directly under the images dir as fallback
    path2 = DATA_DIR / "projects" / script_id / "images" / filename
    return _to_remotion_path(str(path2)) if path2.exists() else None


def _title_card_image_path(script_id: str) -> str | None:
    """Resolve path to the title card composite image."""
    notitle = DATA_DIR / "projects" / script_id / "images" / "composite_title_card_notitle.png"
    if notitle.exists():
        return _to_remotion_path(str(notitle))
    withtitle = DATA_DIR / "projects" / script_id / "images" / "composite_title_card.png"
    return _to_remotion_path(str(withtitle)) if withtitle.exists() else None


def _all_scenes(content: ScriptContent) -> list[Scene]:
    """Flatten all scenes from all segments in order."""
    return [sc for seg in content.segments for sc in seg.scenes]


def _scene_to_input_props(scene: Scene, script_id: str) -> dict[str, Any]:
    """Convert a Scene model to the input props expected by Remotion."""
    # Resolve asset paths
    image_path = _scene_image_path(script_id, scene.id, scene.image_url or None)
    audio_path = _scene_audio_path(script_id, scene.id)
    frame_paths = _scene_frame_paths(script_id, scene)
    clip_path = _video_clip_path(script_id, scene)

    # For title cards, use the composite image
    if scene.is_title_card and scene.title_card_zoom_target:
        tc_path = _title_card_image_path(script_id)
        if tc_path:
            image_path = tc_path

    # Use audio duration if available, otherwise estimate
    duration = scene.audio_duration_seconds if scene.audio_duration_seconds > 0 else scene.duration_estimate_seconds

    # Parse FX if stored as dict
    fx = scene.fx

    # Legacy KB config for fallback
    kb = scene.ken_burns or KenBurnsConfig()

    return {
        "id": scene.id,
        "narration": scene.narration,
        "visual_prompt": scene.visual_prompt,
        "text_overlay": scene.text_overlay,
        "duration_seconds": duration,
        "is_title_card": scene.is_title_card,
        "media_type": scene.media_type or "ai_generated",
        "image_path": image_path,
        "image_path_b": None,  # legacy A/B not used in Remotion
        "frame_paths": frame_paths if frame_paths else None,
        "audio_path": audio_path,
        "video_clip_path": clip_path,
        "title_card_zoom_target": scene.title_card_zoom_target,
        "fx": fx,
        "ken_burns_effect": kb.effect,
        "ken_burns_intensity": kb.intensity,
        "scene_transition": scene.scene_transition or "",
    }


def _write_input_props(props: dict[str, Any], output_path: Path) -> Path:
    """Write input props JSON file for Remotion to consume."""
    props_path = output_path.parent / f"{output_path.stem}_props.json"
    props_path.write_text(json.dumps(props, indent=2, default=str))
    return props_path


def _run_remotion(
    composition_id: str,
    props_path: Path,
    output_path: Path,
    width: int = 1920,
    height: int = 1080,
    fps: int = 30,
    log_level: str = "warn",
) -> None:
    """Run Remotion render via npx subprocess."""
    cmd = [
        "npx",
        "remotion",
        "render",
        str(REMOTION_ENTRY),
        composition_id,
        str(output_path),
        f"--props={props_path}",
        f"--width={width}",
        f"--height={height}",
        f"--fps={fps}",
        "--codec=h264",
        f"--log={log_level}",
        "--overwrite",
    ]

    logger.info("Running Remotion: %s", " ".join(cmd))

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=1200,  # 20 min max
        cwd=str(REMOTION_DIR),
        env={**os.environ, "NODE_OPTIONS": "--max-old-space-size=4096"},
    )

    if result.returncode != 0:
        logger.error("Remotion stderr: %s", result.stderr[-1000:])
        raise RuntimeError(
            f"Remotion render failed (exit {result.returncode}): {result.stderr[-500:]}"
        )

    logger.info("Remotion render complete: %s", output_path)


def render_scene_preview(
    scene: Scene,
    script_id: str,
    width: int = 1920,
    height: int = 1080,
    modifier_ids: list[str] | None = None,
    brand: dict | None = None,
) -> str:
    """Render a single scene to MP4 via Remotion and return the web-relative path.

    Runs modifier pre-render hooks before rendering.
    """
    # Run modifier pre-render hooks (e.g. generate title card images)
    if modifier_ids:
        import pipeline.modifiers  # noqa: F401
        from pipeline.modifiers.registry import get_active

        brand_dict = brand or {}
        for mod in get_active(modifier_ids):
            scene = mod.modify_scene_pre_render(scene, script_id, brand_dict)

    renders = _renders_dir(script_id)
    scenes_dir = renders / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    output_path = scenes_dir / f"{scene.id}.mp4"

    scene_props = _scene_to_input_props(scene, script_id)
    props = {
        "scene": scene_props,
        "fps": 30,
        "width": width,
        "height": height,
    }
    props_path = _write_input_props(props, output_path)

    try:
        _run_remotion(
            composition_id="ScenePreview",
            props_path=props_path,
            output_path=output_path,
            width=width,
            height=height,
        )
    finally:
        # Clean up props file
        try:
            props_path.unlink()
        except OSError:
            pass

    return f"/static/projects/{script_id}/renders/scenes/{scene.id}.mp4"


def render_full_video(
    script_id: str,
    content: ScriptContent,
    width: int = 1920,
    height: int = 1080,
    on_progress: ProgressCallback = None,
    title: str = "",
    speed: float = 1.0,
    modifier_ids: list[str] | None = None,
    brand: dict | None = None,
) -> str:
    """Render the full video as a single Remotion composition.

    Returns the web-relative path to the final MP4.
    """
    scenes = _all_scenes(content)
    total = len(scenes)

    # Run modifier pre-render hooks for all scenes
    if modifier_ids:
        import pipeline.modifiers  # noqa: F401
        from pipeline.modifiers.registry import get_active

        brand_dict = brand or {}
        for i, scene in enumerate(scenes):
            if on_progress:
                on_progress(i / (total + 2), f"Preparing scene {i + 1}/{total}")
            for mod in get_active(modifier_ids):
                scenes[i] = mod.modify_scene_pre_render(scene, script_id, brand_dict)

    if on_progress:
        on_progress(0.3, "Building Remotion composition...")

    # Build input props for the full video
    segments_props = []
    for seg in content.segments:
        seg_scenes = []
        for sc in seg.scenes:
            seg_scenes.append(_scene_to_input_props(sc, script_id))
        segments_props.append({
            "name": seg.name,
            "scenes": seg_scenes,
        })

    props = {
        "segments": segments_props,
        "title": title or content.title,
        "fps": 30,
        "width": width,
        "height": height,
    }

    renders = _renders_dir(script_id)
    speed_suffix = f"_{speed}x" if speed != 1.0 else ""
    output_filename = f"full_youtube{speed_suffix}.mp4"
    output_path = renders / output_filename

    props_path = _write_input_props(props, output_path)

    if on_progress:
        on_progress(0.4, "Rendering video with Remotion...")

    try:
        _run_remotion(
            composition_id="FullVideo",
            props_path=props_path,
            output_path=output_path,
            width=width,
            height=height,
            log_level="verbose",
        )
    finally:
        try:
            props_path.unlink()
        except OSError:
            pass

    if on_progress:
        on_progress(1.0, "Complete")

    web_path = f"/static/projects/{script_id}/renders/{output_filename}"

    if title:
        try:
            speed_label = f" ({speed}x)" if speed != 1.0 else ""
            _copy_to_downloads(
                title,
                str(output_path),
                f"{_sanitize_filename(title)} - YouTube{speed_label}.mp4",
            )
        except Exception:
            logger.warning("Failed to copy to downloads", exc_info=True)

    return web_path


def _copy_to_downloads(title: str, src_path: str, dest_name: str) -> str:
    """Copy a rendered file to the downloads directory."""
    base = os.environ.get("DOWNLOADS_DIR", "") or str(Path.home() / "Downloads")
    folder = Path(base) / _sanitize_filename(title)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / dest_name
    shutil.copy2(src_path, dest)
    logger.info("Copied to downloads: %s", dest)
    return str(dest)
