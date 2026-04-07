"""FFmpeg command-line argument builder — audio concat utility."""

import logging
import os
import tempfile

logger = logging.getLogger(__name__)


def build_audio_concat_cmd(
    audio_paths: list[str],
    output_path: str,
) -> tuple[list[str], str]:
    """Build FFmpeg command to concatenate multiple audio files into one MP3.

    Returns (command args, path to temp concat list file).
    """
    fd, list_path = tempfile.mkstemp(suffix=".txt", prefix="ffaudioconcat_")
    with os.fdopen(fd, "w") as f:
        for path in audio_paths:
            f.write(f"file '{path}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", list_path,
        "-c:a", "libmp3lame",
        "-b:a", "192k",
        output_path,
    ]

    return cmd, list_path
