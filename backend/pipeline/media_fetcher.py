"""Media fetcher pipeline — downloads real gameplay clips and hardware images via yt-dlp."""

import logging
import os
import shutil
import subprocess
import tempfile

from config import DATA_DIR

logger = logging.getLogger(__name__)


def _check_ytdlp() -> None:
    """Verify yt-dlp is installed."""
    if not shutil.which("yt-dlp"):
        raise RuntimeError(
            "yt-dlp is not installed. Install it with: brew install yt-dlp"
        )


def _query_marker_path(base_path: str) -> str:
    """Return the .query marker path for a given media file."""
    return base_path + ".query"


def _is_cached(output_path: str, search_query: str, force: bool) -> bool:
    """Check if the output already exists with a matching search query."""
    if force:
        return False
    if not os.path.exists(output_path):
        return False
    marker = _query_marker_path(output_path)
    if not os.path.exists(marker):
        return False
    with open(marker) as f:
        return f.read().strip() == search_query.strip()


def _write_marker(output_path: str, search_query: str) -> None:
    """Write a .query marker file alongside the output."""
    marker = _query_marker_path(output_path)
    with open(marker, "w") as f:
        f.write(search_query.strip())


def _download_video(search_query: str, output_path: str) -> None:
    """Download a video via yt-dlp search."""
    cmd = [
        "yt-dlp",
        f"ytsearch1:{search_query}",
        "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "--merge-output-format", "mp4",
        "--no-playlist",
        "--no-warnings",
        "-o", output_path,
    ]
    logger.info("yt-dlp download: %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        logger.error("yt-dlp stderr: %s", result.stderr)
        raise RuntimeError(f"yt-dlp failed: {result.stderr[-500:]}")


def search_and_download_clip(
    script_id: str,
    scene_id: str,
    search_query: str,
    trim_duration: float = 10.0,
    force: bool = False,
) -> str:
    """Download a gameplay clip from YouTube and trim it.

    Returns the web-relative path to the clip.
    """
    _check_ytdlp()

    clips_dir = DATA_DIR / "projects" / script_id / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(clips_dir / f"{scene_id}.mp4")

    if _is_cached(output_path, search_query, force):
        logger.info("Clip cache hit: %s", output_path)
        return f"/static/projects/{script_id}/clips/{scene_id}.mp4"

    # Download to temp file
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_path = os.path.join(tmpdir, "raw.mp4")
        _download_video(search_query, raw_path)

        # Trim: skip first 10s (usually intros/logos), take trim_duration seconds
        trim_cmd = [
            "ffmpeg", "-y",
            "-ss", "10",
            "-i", raw_path,
            "-t", str(trim_duration),
            "-c:v", "libx264",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            output_path,
        ]
        logger.info("Trimming clip: %s", " ".join(trim_cmd))
        result = subprocess.run(trim_cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg trim failed: {result.stderr[-500:]}")

    _write_marker(output_path, search_query)
    return f"/static/projects/{script_id}/clips/{scene_id}.mp4"


def search_and_extract_frame(
    script_id: str,
    scene_id: str,
    search_query: str,
    force: bool = False,
) -> str:
    """Download a YouTube video and extract a single frame as a PNG.

    Outputs to the standard images directory so existing render pipeline works unchanged.
    Returns the web-relative path.
    """
    _check_ytdlp()

    images_dir = DATA_DIR / "projects" / script_id / "images"
    images_dir.mkdir(parents=True, exist_ok=True)
    output_path = str(images_dir / f"{scene_id}.png")

    if _is_cached(output_path, search_query, force):
        logger.info("Frame cache hit: %s", output_path)
        return f"/static/projects/{script_id}/images/{scene_id}.png"

    # Download to temp, extract frame at 5s mark
    with tempfile.TemporaryDirectory() as tmpdir:
        raw_path = os.path.join(tmpdir, "raw.mp4")
        _download_video(search_query, raw_path)

        frame_cmd = [
            "ffmpeg", "-y",
            "-ss", "5",
            "-i", raw_path,
            "-frames:v", "1",
            "-q:v", "1",
            output_path,
        ]
        logger.info("Extracting frame: %s", " ".join(frame_cmd))
        result = subprocess.run(frame_cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg frame extract failed: {result.stderr[-500:]}")

    _write_marker(output_path, search_query)
    return f"/static/projects/{script_id}/images/{scene_id}.png"


def fetch_scene_media(
    script_id: str,
    scene_id: str,
    media_type: str,
    search_query: str,
    duration: float = 10.0,
    force: bool = False,
) -> dict:
    """Dispatch to the appropriate fetcher based on media_type.

    Returns dict with video_clip_url or image_url.
    """
    if media_type == "gameplay_clip":
        url = search_and_download_clip(script_id, scene_id, search_query, duration, force)
        return {"scene_id": scene_id, "video_clip_url": url}
    elif media_type == "hardware_image":
        url = search_and_extract_frame(script_id, scene_id, search_query, force)
        return {"scene_id": scene_id, "image_url": url}
    else:
        raise ValueError(f"Unsupported media_type for fetching: {media_type}")


def fetch_batch(
    scenes: list[dict],
    script_id: str,
) -> list[dict]:
    """Fetch media for multiple scenes sequentially.

    Each scene dict should have: scene_id, media_type, search_query, duration (optional).
    Returns list of result dicts with scene_id + url or error.
    """
    results: list[dict] = []
    for scene in scenes:
        try:
            result = fetch_scene_media(
                script_id=script_id,
                scene_id=scene["scene_id"],
                media_type=scene["media_type"],
                search_query=scene["search_query"],
                duration=scene.get("duration", 10.0),
                force=scene.get("force", False),
            )
            results.append(result)
        except Exception as e:
            logger.error("Failed to fetch media for scene %s: %s", scene["scene_id"], e)
            results.append({"scene_id": scene["scene_id"], "error": str(e)})
    return results
