"""Gameplay clip pipeline — searches Twitch clips/VODs, downloads, validates, stores."""

import logging
import os
import shutil
import tempfile
from pathlib import Path

from config import DATA_DIR
from integrations.twitch_client import lookup_game, search_clips, search_vods
from integrations.gameplay_downloader import download_clip, download_vod_segment, detect_facecam

logger = logging.getLogger(__name__)

MAX_FACECAM_RETRIES = 3


def _find_yt_dlp_output(tmp_name: str) -> Path | None:
    """Find the actual file yt-dlp produced (may add format suffixes)."""
    output = Path(tmp_name)
    if output.exists() and output.stat().st_size > 0:
        return output
    parent = output.parent
    stem = output.stem
    candidates = [c for c in parent.glob(f"{stem}*") if c.stat().st_size > 0]
    return candidates[0] if candidates else None


def generate_gameplay_clip(
    script_id: str,
    scene_id: str,
    game_name: str,
    duration_seconds: float,
) -> str:
    """Find, download, and validate a gameplay clip for a scene.

    Prefers Twitch clips (short, guaranteed to be from the correct game).
    Falls back to VOD segments if no clips are available.
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

    # --- Try clips first (guaranteed correct game) ---
    clips = search_clips(game["id"])
    if clips:
        for attempt, clip in enumerate(clips[:MAX_FACECAM_RETRIES]):
            clip_url = clip["url"]
            tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
            tmp.close()
            os.unlink(tmp.name)

            try:
                download_clip(clip_url, tmp.name)
                output = _find_yt_dlp_output(tmp.name)
                if not output:
                    logger.warning("Clip download produced no output: %s", clip_url)
                    continue

                has_facecam = detect_facecam(str(output))
                if not has_facecam:
                    shutil.move(str(output), str(dest))
                    logger.info("Gameplay clip (from Twitch clip) stored: %s (attempt %d)", dest, attempt + 1)
                    return f"/static/projects/{script_id}/clips/{scene_id}.mp4"

                logger.info("Facecam detected in clip %s, trying next (%d/%d)", clip_url, attempt + 1, MAX_FACECAM_RETRIES)
                output.unlink(missing_ok=True)
            except Exception:
                logger.warning("Clip download failed for %s, trying next", clip_url, exc_info=True)
                for p in Path(tempfile.gettempdir()).glob(Path(tmp.name).stem + "*"):
                    p.unlink(missing_ok=True)

    # --- Fall back to VOD segments ---
    logger.info("No suitable clips found for %s, falling back to VODs", game_name)
    vods = search_vods(game["id"])
    if not vods:
        raise RuntimeError(f"No clips or VODs found for game: {game_name!r}")

    for attempt in range(MAX_FACECAM_RETRIES):
        vod = vods[attempt % len(vods)]
        vod_url = vod["url"]

        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp.close()
        os.unlink(tmp.name)

        try:
            download_vod_segment(vod_url, duration_seconds, tmp.name)
            output = _find_yt_dlp_output(tmp.name)
            if not output:
                raise RuntimeError(f"yt-dlp produced no output for {vod_url}")

            has_facecam = detect_facecam(str(output))
            if not has_facecam:
                shutil.move(str(output), str(dest))
                logger.info("Gameplay clip (from VOD) stored: %s (attempt %d)", dest, attempt + 1)
                return f"/static/projects/{script_id}/clips/{scene_id}.mp4"

            logger.info("Facecam detected in VOD clip from %s, retrying (%d/%d)", vod_url, attempt + 1, MAX_FACECAM_RETRIES)
            output.unlink(missing_ok=True)
        except Exception:
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)
            if attempt == MAX_FACECAM_RETRIES - 1:
                raise
            logger.warning("VOD clip download failed, retrying (%d/%d)", attempt + 1, MAX_FACECAM_RETRIES)

    raise RuntimeError(f"Could not find facecam-free gameplay clip for {game_name!r} after all attempts")
