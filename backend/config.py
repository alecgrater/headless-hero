"""Shared configuration constants and utilities for the backend."""

import json
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

# Square image dimension for title card icons and character frames
SQUARE_IMAGE_SIZE = 768

# Frames per second for all video rendering
FPS = 30

# Fixed segment count for video scripts
SEGMENT_COUNT = 8

# Default segment circle colors for title card grids
DEFAULT_SEGMENT_COLORS = [
    "#e91e63", "#2196f3", "#4caf50", "#ff9800",
    "#9c27b0", "#00bcd4", "#ff5722", "#8bc34a",
    "#3f51b5", "#cddc39", "#f44336", "#009688",
]

# Default accent color for title highlights and UI elements
DEFAULT_ACCENT_COLOR = "#e91e63"

# Default Claude model for script generation and LLM tasks
DEFAULT_CLAUDE_MODEL = "anthropic.claude-opus-4-6-v1"

# Faster models for structured/classification tasks
BALANCED_CLAUDE_MODEL = "anthropic.claude-sonnet-4-6-v1"
FAST_CLAUDE_MODEL = "anthropic.claude-haiku-4-5-20251001"

# Default Gemini model for image generation
DEFAULT_IMAGE_MODEL = "gemini-2.5-flash-image"

# YouTube thumbnail dimensions
THUMBNAIL_WIDTH = 1280
THUMBNAIL_HEIGHT = 720

# Backend server port
BACKEND_PORT = 8420

# Default iCloud export directory for finished videos
_DEFAULT_EXPORT_FOLDER = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs" / "headless-hero media" / "Videos"


def get_export_folder() -> Path:
    """Return the configured export folder, falling back to the default iCloud path."""
    custom = os.environ.get("EXPORT_FOLDER", "").strip()
    if custom:
        return Path(custom).expanduser()
    return _DEFAULT_EXPORT_FOLDER


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


def parse_json_response(text: str) -> dict | list:
    """Parse JSON from an LLM response, stripping markdown fences first."""
    cleaned = strip_markdown_fences(text)
    return json.loads(cleaned)
