"""Short-form (9:16) render pipeline — renders one or all per-segment shorts via Remotion."""

import json
import logging
import re
from pathlib import Path
from typing import Callable

from config import BACKEND_PORT, DATA_DIR, FPS
from models.script import Scene, ScriptContent
from pipeline.export_paths import copy_to_project_downloads, shortform_video_filename
from pipeline.remotion_render import (
    _reencode_h264,
    _run_remotion,
    _scene_to_input_props,
    _verify_video,
)
from pipeline.short_form_parts import short_form_part_indicator

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str], None] | None

SHORT_WIDTH = 1080
SHORT_HEIGHT = 1920


def strip_leading_number(title: str) -> str:
    """Strip leading digit(s) followed by whitespace from a title.

    Examples:
        "8 Unsolved Crimes ..." -> "Unsolved Crimes ..."
        "How to Train Your Dragon" -> "How to Train Your Dragon"
        "8Track Memories" -> "8Track Memories"  (no following whitespace)
    """
    return re.sub(r"^\d+\s+", "", title)


def _shorts_dir(script_id: str) -> Path:
    d = DATA_DIR / "projects" / script_id / "renders" / "shorts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _title_card_backdrop_url(script_id: str, segment_idx: int, content: ScriptContent) -> str:
    """Web-served URL for the per-segment square illustration used as title-card backdrop.

    Resolves the filename per the script's title-card strategy:
      - composite-grid: title_card_{idx}.png
      - cinematic-chapters: chapter_{idx + 1}.png

    Returns "" if the file does not exist on disk; the Remotion component falls back
    to a black background in that case.
    """
    from pipeline.formats import resolve_format

    base = DATA_DIR / "projects" / script_id / "images"
    fmt = resolve_format(content.format_id)
    if fmt.title_card_strategy.kind == "cinematic-chapters":
        filename = f"chapter_{segment_idx + 1}.png"
    else:
        filename = f"title_card_{segment_idx}.png"
    p = base / filename
    if not p.exists():
        return ""
    return f"http://localhost:{BACKEND_PORT}/static/projects/{script_id}/images/{filename}"


def _short_filename(segment_name: str, n: int, total: int) -> str:
    """Build the destination filename for a rendered short."""
    return shortform_video_filename(segment_name, n, total)


def _short_metadata_path(script_id: str, segment_idx: int) -> Path:
    return _shorts_dir(script_id) / f"{segment_idx}.json"


def _write_short_render_metadata(script_id: str, segment_idx: int, content: ScriptContent) -> None:
    metadata = {
        "segment_idx": segment_idx,
        "hook_scene_count": content.hook_scene_count or 0,
        "part_indicator": short_form_part_indicator(content, segment_idx),
    }
    _short_metadata_path(script_id, segment_idx).write_text(json.dumps(metadata, indent=2), encoding="utf-8")


def is_short_render_current(script_id: str, segment_idx: int, content: ScriptContent) -> bool:
    """Return whether a cached short render matches content-sensitive render options."""
    expected_part_indicator = short_form_part_indicator(content, segment_idx)
    requires_metadata = bool(expected_part_indicator) or (segment_idx == 0 and bool(content.hook_scene_count))
    if not requires_metadata:
        return True

    metadata_path = _short_metadata_path(script_id, segment_idx)
    if not metadata_path.is_file():
        return False
    try:
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        cached_hook_scene_count = int(metadata.get("hook_scene_count") or 0)
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return False
    if segment_idx == 0 and cached_hook_scene_count != int(content.hook_scene_count or 0):
        return False
    return metadata.get("part_indicator", "") == expected_part_indicator


def _copy_to_downloads(project_title: str, src_path: Path, dest_filename: str) -> str:
    """Copy a rendered short into the standard project Downloads folder."""
    dest = copy_to_project_downloads(project_title, src_path, dest_filename)
    logger.info("Copied short to downloads: %s", dest)
    return dest


def _build_segment_scene_props(
    segment_scenes: list[Scene],
    script_id: str,
    backdrop_url: str,
) -> list[dict]:
    """Convert a segment's scenes to Remotion input props.

    Overrides the title card scene's image_url to the per-segment square illustration
    (shorts use the square, not the long-form composite grid card).
    """
    props: list[dict] = []
    for scene in segment_scenes:
        scene_props = _scene_to_input_props(scene, script_id)
        if scene.is_title_card and backdrop_url:
            scene_props["image_path"] = backdrop_url
        props.append(scene_props)
    return props


def render_short_segment(
    script_id: str,
    segment_idx: int,
    content: ScriptContent,
    project_title: str,
    on_progress: ProgressCallback = None,
) -> tuple[str, str]:
    """Render a single short for one segment.

    Returns a tuple of (web_url, downloads_path):
    - web_url: web-relative path served via static mount (e.g. /static/projects/…)
    - downloads_path: absolute filesystem path in the standard project Downloads folder
    """
    if segment_idx < 0 or segment_idx >= len(content.segments):
        raise RuntimeError(f"segment_idx {segment_idx} out of range (0..{len(content.segments) - 1})")

    segment = content.segments[segment_idx]
    if not segment.scenes:
        raise RuntimeError(f"Segment {segment_idx} has no scenes")
    if not segment.scenes[0].is_title_card:
        raise RuntimeError(
            f"Segment {segment_idx} first scene is not a title card — "
            "run the long-form pipeline first"
        )

    scenes_to_render = list(segment.scenes)

    # For short #1 (segment 0), skip the leading "hook" scenes that tease the whole video.
    # The first scene of segment 0 is still the title card, so skip starts at index 1.
    if segment_idx == 0 and content.hook_scene_count:
        # Preserve title card at index 0, drop the next `hook_scene_count` scenes.
        skip = min(content.hook_scene_count, max(0, len(scenes_to_render) - 2))
        if skip > 0:
            logger.info("[%s] short #1: skipping %d hook scene(s)", script_id, skip)
            scenes_to_render = [scenes_to_render[0]] + scenes_to_render[1 + skip:]

    backdrop_url = _title_card_backdrop_url(script_id, segment_idx, content)
    scene_props = _build_segment_scene_props(scenes_to_render, script_id, backdrop_url)

    props = {
        "scenes": scene_props,
        "stripped_title": strip_leading_number(content.title),
        "segment_name": segment.name,
        "part_indicator": short_form_part_indicator(content, segment_idx),
        "fps": FPS,
        "width": SHORT_WIDTH,
        "height": SHORT_HEIGHT,
        "visual_canvas": content.visual_canvas.model_dump(),
        "subtitle_highlight": (
            {"enabled": True} if content.subtitle_highlight_enabled else None
        ),
    }

    shorts_dir = _shorts_dir(script_id)
    n = segment_idx + 1
    total = len(content.segments)
    output_filename = f"{segment_idx}.mp4"
    output_path = shorts_dir / output_filename
    raw_output = shorts_dir / f"{segment_idx}_raw.mkv"

    props_path = shorts_dir / f"{segment_idx}_props.json"
    props_path.write_text(json.dumps(props, indent=2, default=str))

    logger.info(
        "[%s] Rendering short %d/%d (%s, %d scenes) to %s",
        script_id,
        n,
        total,
        segment.name,
        len(scenes_to_render),
        output_path,
    )

    if on_progress:
        on_progress(0.1, f"Rendering short {n}/{total} with Remotion...")

    try:
        _run_remotion(
            composition_id="ShortFormVideo",
            props_path=props_path,
            output_path=raw_output,
            width=SHORT_WIDTH,
            height=SHORT_HEIGHT,
            log_level="verbose",
        )
        if not _verify_video(raw_output):
            logger.warning("Raw short %d corrupt — retrying", segment_idx)
            _run_remotion(
                composition_id="ShortFormVideo",
                props_path=props_path,
                output_path=raw_output,
                width=SHORT_WIDTH,
                height=SHORT_HEIGHT,
                log_level="verbose",
            )
            if not _verify_video(raw_output):
                raise RuntimeError(f"Remotion produced corrupt short for segment {segment_idx}")

        if on_progress:
            on_progress(0.85, "Re-encoding to H.264...")
        logger.info("[%s] Re-encoding short %d/%d to H.264", script_id, n, total)
        if not _reencode_h264(raw_output, output_path):
            raise RuntimeError(f"H.264 re-encode failed for segment {segment_idx}")

        # Copy to downloads (always overwrites per spec)
        if on_progress:
            on_progress(0.95, "Copying to Downloads...")
        logger.info("[%s] Copying short %d/%d to Downloads", script_id, n, total)
        dest_name = _short_filename(segment.name, n, total)
        downloads_path = _copy_to_downloads(project_title, output_path, dest_name)
        _write_short_render_metadata(script_id, segment_idx, content)
    finally:
        try:
            props_path.unlink()
        except OSError:
            pass
        try:
            raw_output.unlink()
        except OSError:
            pass

    if on_progress:
        on_progress(1.0, f"Short {n}/{total} complete")

    logger.info("[%s] Short %d/%d complete: %s", script_id, n, total, output_path)

    web_url = f"/static/projects/{script_id}/renders/shorts/{output_filename}"
    return web_url, downloads_path


def render_all_shorts(
    script_id: str,
    content: ScriptContent,
    project_title: str,
    on_progress: ProgressCallback = None,
) -> list[tuple[str, str]]:
    """Render every segment as a short, sequentially.

    Returns list of (web_url, downloads_path) tuples, one per segment.
    """
    total = len(content.segments)
    results: list[tuple[str, str]] = []
    for i in range(total):
        n = i + 1

        def seg_progress(p: float, msg: str, _n: int = n) -> None:
            if on_progress:
                # Map per-segment 0..1 into the global range
                global_p = ((_n - 1) + p) / total
                on_progress(global_p, f"Short {_n}/{total}: {msg}")

        web_url, downloads_path = render_short_segment(
            script_id=script_id,
            segment_idx=i,
            content=content,
            project_title=project_title,
            on_progress=seg_progress,
        )
        results.append((web_url, downloads_path))

    return results
