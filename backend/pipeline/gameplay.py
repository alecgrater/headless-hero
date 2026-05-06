"""Gameplay clip pipeline — searches Twitch VODs, downloads, validates, stores."""

import logging
import os
import shutil
import tempfile
from pathlib import Path

from config import DATA_DIR
from integrations.twitch_client import lookup_game, search_vods
from integrations.gameplay_downloader import download_vod_segment, detect_facecam

logger = logging.getLogger(__name__)

MAX_FACECAM_RETRIES = 3


def generate_gameplay_clip(
    script_id: str,
    scene_id: str,
    game_name: str,
    duration_seconds: float,
) -> str:
    """Find, download, and validate a gameplay clip for a scene.

    Returns the web-relative URL for the stored clip.
    """
    clips_dir = DATA_DIR / "projects" / script_id / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    dest = clips_dir / f"{scene_id}.mp4"

    if dest.exists():
        logger.info("Gameplay clip already exists: %s", dest)
        return f"/static/projects/{script_id}/clips/{scene_id}.mp4"

    game = lookup_game(game_name)
    if not game:
        raise RuntimeError(f"Game not found on Twitch: {game_name!r}")

    vods = search_vods(game["id"])
    if not vods:
        raise RuntimeError(f"No VODs found for game: {game_name!r}")

    for attempt in range(MAX_FACECAM_RETRIES):
        vod = vods[attempt % len(vods)]
        vod_url = vod["url"]

        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp.close()
        os.unlink(tmp.name)  # yt-dlp needs the path to NOT exist

        try:
            download_vod_segment(vod_url, duration_seconds, tmp.name)

            # yt-dlp may add format suffix — find the actual output file
            output = Path(tmp.name)
            if not output.exists() or output.stat().st_size == 0:
                parent = output.parent
                stem = output.stem
                candidates = [c for c in parent.glob(f"{stem}*") if c.stat().st_size > 0]
                if candidates:
                    output = candidates[0]
                else:
                    raise RuntimeError(f"yt-dlp produced no output for {vod_url}")

            has_facecam = detect_facecam(str(output))
            if not has_facecam:
                shutil.move(str(output), str(dest))
                logger.info("Gameplay clip stored: %s (attempt %d)", dest, attempt + 1)
                return f"/static/projects/{script_id}/clips/{scene_id}.mp4"

            logger.info("Facecam detected in clip from %s, retrying (%d/%d)", vod_url, attempt + 1, MAX_FACECAM_RETRIES)
            output.unlink(missing_ok=True)
        except Exception:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)
            if attempt == MAX_FACECAM_RETRIES - 1:
                raise
            logger.warning("Clip download failed, retrying (%d/%d)", attempt + 1, MAX_FACECAM_RETRIES)

    raise RuntimeError(f"Could not find facecam-free gameplay clip for {game_name!r} after {MAX_FACECAM_RETRIES} attempts")
