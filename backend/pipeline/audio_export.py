"""Audio export pipeline — FFmpeg audio concatenation + download copy utilities."""

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable

from config import DATA_DIR, sanitize_filename
from models.script import ScriptContent
from pipeline.ffmpeg_builder import build_audio_concat_cmd

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str], None] | None

def _run_ffmpeg(cmd: list[str]) -> None:
    """Run an FFmpeg command, raising on failure."""
    logger.info("Running: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        logger.error("FFmpeg stderr: %s", result.stderr)
        raise RuntimeError(f"FFmpeg failed (exit {result.returncode}): {result.stderr[-500:]}")

def copy_to_downloads(title: str, src_path: str, dest_name: str) -> str:
    """Copy a rendered file to the downloads directory.

    Returns the destination path.
    """
    base = os.environ.get("DOWNLOADS_DIR", "") or str(Path.home() / "Downloads")
    folder = Path(base) / sanitize_filename(title)
    folder.mkdir(parents=True, exist_ok=True)
    dest = folder / dest_name
    shutil.copy2(src_path, dest)
    logger.info("Copied to downloads: %s", dest)
    return str(dest)

def _scene_audio_path(script_id: str, scene_id: str) -> str:
    """Resolve local filesystem path for a scene audio file."""
    return str(DATA_DIR / "projects" / script_id / "audio" / f"{scene_id}.mp3")

def _renders_dir(script_id: str) -> Path:
    d = DATA_DIR / "projects" / script_id / "renders"
    d.mkdir(parents=True, exist_ok=True)
    return d


def export_full_audio(
    script_id: str,
    content: ScriptContent,
    title: str = "",
) -> str:
    """Concatenate all scene audio files into a single MP3.

    Returns the web-relative path to the output.
    """
    scenes = content.all_scenes()
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
            copy_to_downloads(title, output_path, f"{sanitize_filename(title)} - Audio.mp3")
        except Exception:
            logger.warning("Failed to copy audio to downloads", exc_info=True)

    return web_path
