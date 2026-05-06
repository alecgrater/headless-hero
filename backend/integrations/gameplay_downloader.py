"""yt-dlp wrapper for downloading VOD segments + clips + facecam detection via Gemini."""

import logging
import os
import random
import subprocess
import tempfile

logger = logging.getLogger(__name__)


def download_clip(clip_url: str, output_path: str) -> str:
    """Download a Twitch clip using yt-dlp. Returns the output path."""
    cmd = [
        "yt-dlp",
        "-f", "best[height<=1080]",
        "--merge-output-format", "mp4",
        "-o", output_path,
        "--no-playlist",
        clip_url,
    ]
    logger.info("Downloading clip: %s", clip_url)
    subprocess.run(cmd, timeout=120, check=True, capture_output=True, text=True)
    return output_path


def download_vod_segment(
    vod_url: str,
    duration_seconds: float,
    output_path: str,
    start_offset_seconds: float | None = None,
) -> str:
    """Download a segment of a VOD using yt-dlp + ffmpeg.

    If start_offset_seconds is None, picks a random offset from the first 80% of the video.
    Returns the path to the downloaded clip.
    """
    # Probe video duration first
    probe_cmd = [
        "yt-dlp", "--print", "duration", "--no-download", vod_url,
    ]
    try:
        result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
        total_duration = float(result.stdout.strip())
    except (ValueError, subprocess.TimeoutExpired):
        total_duration = 3600.0  # fallback: assume 1 hour

    if start_offset_seconds is None:
        max_start = max(0, total_duration * 0.8 - duration_seconds)
        start_offset_seconds = random.uniform(60.0, max_start) if max_start > 60 else 0.0

    # Build yt-dlp command with time range
    cmd = [
        "yt-dlp",
        "--download-sections", f"*{start_offset_seconds:.0f}-{start_offset_seconds + duration_seconds:.0f}",
        "--force-keyframes-at-cuts",
        "-f", "bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "--merge-output-format", "mp4",
        "-o", output_path,
        "--no-playlist",
        vod_url,
    ]
    logger.info("Downloading VOD segment: %.0fs-%.0fs from %s", start_offset_seconds, start_offset_seconds + duration_seconds, vod_url)
    subprocess.run(cmd, timeout=300, check=True, capture_output=True, text=True)
    return output_path


def detect_facecam(video_path: str, sample_count: int = 3) -> bool:
    """Sample frames from a video clip and use Gemini vision to detect facecam overlays.

    Returns True if a facecam is detected.
    """
    try:
        from integrations.google_client_base import get_google_client
        from google.genai import types
    except ImportError:
        logger.warning("Google GenAI SDK not available for facecam detection")
        return False

    frame_paths = _extract_sample_frames(video_path, sample_count)
    if not frame_paths:
        return False

    client = get_google_client()

    contents: list = [
        "Look at these video frames. Is there a facecam (a streamer's webcam "
        "overlay showing a person's face, usually in a corner)? "
        "Reply with ONLY 'yes' or 'no'."
    ]
    for fp in frame_paths:
        with open(fp, "rb") as f:
            contents.append(types.Part.from_bytes(data=f.read(), mime_type="image/jpeg"))

    resp = client.models.generate_content(
        model="gemini-2.5-flash-preview-05-20",
        contents=contents,
    )
    answer = (resp.text or "").strip().lower()
    has_facecam = answer.startswith("yes")
    logger.info("Facecam detection for %s: %s (%r)", video_path, has_facecam, answer)

    for fp in frame_paths:
        os.unlink(fp)

    return has_facecam


def _extract_sample_frames(video_path: str, count: int) -> list[str]:
    """Extract sample frames from a video using ffmpeg."""
    frames: list[str] = []
    for i in range(count):
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        tmp.close()
        offset = (i + 1) / (count + 1)
        cmd = [
            "ffmpeg", "-y",
            "-ss", f"{offset * 10:.1f}",
            "-i", video_path,
            "-frames:v", "1",
            "-q:v", "2",
            tmp.name,
        ]
        try:
            subprocess.run(cmd, timeout=15, check=True, capture_output=True)
            frames.append(tmp.name)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            os.unlink(tmp.name)
    return frames
