"""Shared configuration constants and utilities for the backend."""

import os
import re
from pathlib import Path

# Root data directory — resolved from env vars with fallback to `<repo>/data`
DATA_DIR = Path(
    os.environ.get(
        "HH_DATA_DIR",
        Path(__file__).resolve().parents[1] / "data",
    )
)

# Default ElevenLabs TTS model
DEFAULT_TTS_MODEL = "eleven_multilingual_v2"

# Video output dimensions (YouTube 16:9)
VIDEO_WIDTH = 1920
VIDEO_HEIGHT = 1080

# Default image generation dimensions (landscape, optimized for AI models)
IMAGE_WIDTH = 1344
IMAGE_HEIGHT = 768

# Frames per second for all video rendering
FPS = 30

# Allowed segment counts for video scripts (8 or 10 only)
ALLOWED_SEGMENT_COUNTS = (8, 10)


def snap_segment_count(n: int) -> int:
    """Snap an arbitrary segment count to the nearest allowed value (8 or 10).

    Ties (e.g. 9) round up to the higher count.
    """
    return min(ALLOWED_SEGMENT_COUNTS, key=lambda x: (abs(x - n), -x))


def strip_markdown_fences(text: str) -> str:
    """Strip markdown code fences (```json ... ```) from an LLM response."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def sanitize_filename(name: str) -> str:
    """Strip unsafe filesystem characters and truncate to 80 chars."""
    clean = re.sub(r'[<>:"/\\|?*]', "", name).strip()
    return clean[:80] if clean else "Untitled"
