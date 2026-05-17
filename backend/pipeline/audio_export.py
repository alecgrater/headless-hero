"""Audio export pipeline — FFmpeg audio concatenation + download copy utilities."""

import logging
import os
import subprocess
from pathlib import Path
from typing import Callable

from config import DATA_DIR
from models.script import ScriptContent
from pipeline.export_paths import copy_to_project_downloads, longform_filename
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
    """Copy a rendered file to the standard project Downloads folder."""
    dest = copy_to_project_downloads(title, src_path, dest_name)
    logger.info("Copied to downloads: %s", dest)
    return dest

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
            copy_to_downloads(title, output_path, longform_filename("Audio", title, ".mp3"))
        except Exception:
            logger.warning("Failed to copy audio to downloads", exc_info=True)

    return web_path
