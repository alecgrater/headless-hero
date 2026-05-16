"""Short-form (9:16) render pipeline — renders one or all per-segment shorts via Remotion."""

import json
import logging
import os
import shutil
from pathlib import Path
from typing import Callable

from config import BACKEND_PORT, DATA_DIR, FPS, sanitize_filename
from models.script import ScriptContent, ShortIntro
from pipeline.remotion_render import (
    _reencode_h264,
    _run_remotion,
    _scene_to_input_props,
    _verify_video,
)

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str], None] | None

SHORT_WIDTH = 1080
SHORT_HEIGHT = 1920


def _shorts_dir(script_id: str) -> Path:
    d = DATA_DIR / "projects" / script_id / "renders" / "shorts"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _intro_backdrop_path(script_id: str, segment_idx: int) -> str | None:
    """Web-served path to the per-segment title card image (square)."""
    base = DATA_DIR / "projects" / script_id / "images"
    p = base / f"title_card_{segment_idx}.png"
    if not p.exists():
        return None
    return f"http://localhost:{BACKEND_PORT}/static/projects/{script_id}/images/title_card_{segment_idx}.png"


def _intro_audio_path(script_id: str, segment_idx: int) -> str | None:
    p = DATA_DIR / "projects" / script_id / "audio" / f"short_intro_{segment_idx}.mp3"
    if not p.exists():
        return None
    return f"http://localhost:{BACKEND_PORT}/static/projects/{script_id}/audio/short_intro_{segment_idx}.mp3"


def _build_intro_props(intro: ShortIntro, script_id: str) -> dict:
    backdrop_path = _intro_backdrop_path(script_id, intro.segment_idx)
    audio_path = _intro_audio_path(script_id, intro.segment_idx)
    if not audio_path:
        raise RuntimeError(
            f"Intro audio missing for segment {intro.segment_idx} — generate intros first"
        )
    return {
        "segment_idx": intro.segment_idx,
        "display_text": intro.display_text,
        "audio_path": audio_path,
        "duration_seconds": intro.duration_seconds,
        "word_timestamps": intro.word_timestamps or [],
        "backdrop_image_path": backdrop_path or "",
    }


def _short_filename(project_title: str, n: int, total: int) -> str:
    """Build the destination filename per spec: '[short form N/M] {project name}.mp4'."""
    safe = sanitize_filename(project_title)
    return f"[short form {n}/{total}] {safe}.mp4"


def _copy_to_downloads(project_title: str, src_path: Path, dest_filename: str) -> str:
    """Copy a rendered short into ~/Downloads/{project name}/{dest_filename}.

    Always overwrites the destination.
    """
    base = os.environ.get("DOWNLOADS_DIR", "") or str(Path.home() / "Downloads")
    folder = Path(base) / sanitize_filename(project_title)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / dest_filename
    shutil.copy2(str(src_path), str(dest))
    logger.info("Copied short to downloads: %s", dest)
    return str(dest)


def _find_intro(content: ScriptContent, segment_idx: int) -> ShortIntro:
    if not content.short_intros:
        raise RuntimeError("No short_intros on content — generate intros first")
    for intro in content.short_intros:
        if intro.segment_idx == segment_idx:
            return intro
    raise RuntimeError(f"Short intro for segment {segment_idx} not generated yet")


def render_short_segment(
    script_id: str,
    segment_idx: int,
    content: ScriptContent,
    project_title: str,
    on_progress: ProgressCallback = None,
) -> str:
    """Render a single short for one segment. Returns the web-relative path to the MP4."""
    if segment_idx < 0 or segment_idx >= len(content.segments):
        raise RuntimeError(f"segment_idx {segment_idx} out of range (0..{len(content.segments) - 1})")

    intro = _find_intro(content, segment_idx)
    segment = content.segments[segment_idx]

    # Build scene props (skip the long-form title-card scene if present — shorts use intro instead)
    scene_props = []
    for sc in segment.scenes:
        if sc.is_title_card:
            continue
        scene_props.append(_scene_to_input_props(sc, script_id))

    props = {
        "intro": _build_intro_props(intro, script_id),
        "scenes": scene_props,
        "fps": FPS,
        "width": SHORT_WIDTH,
        "height": SHORT_HEIGHT,
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
        if not _reencode_h264(raw_output, output_path):
            raise RuntimeError(f"H.264 re-encode failed for segment {segment_idx}")

        # Copy to downloads (always overwrites per spec)
        if on_progress:
            on_progress(0.95, "Copying to Downloads...")
        dest_name = _short_filename(project_title, n, total)
        _copy_to_downloads(project_title, output_path, dest_name)
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

    return f"/static/projects/{script_id}/renders/shorts/{output_filename}"


def render_all_shorts(
    script_id: str,
    content: ScriptContent,
    project_title: str,
    on_progress: ProgressCallback = None,
) -> list[str]:
    """Render every segment as a short, sequentially. Returns list of web-relative MP4 paths."""
    total = len(content.segments)
    results: list[str] = []
    for i in range(total):
        n = i + 1

        def seg_progress(p: float, msg: str, _n: int = n) -> None:
            if on_progress:
                # Map per-segment 0..1 into the global range
                global_p = ((_n - 1) + p) / total
                on_progress(global_p, f"Short {_n}/{total}: {msg}")

        url = render_short_segment(
            script_id=script_id,
            segment_idx=i,
            content=content,
            project_title=project_title,
            on_progress=seg_progress,
        )
        results.append(url)

    return results
