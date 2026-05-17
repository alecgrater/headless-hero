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

# Default Claude model for script generation and LLM tasks.
# Anthropic API model ids are used here, not AWS Bedrock ids.
DEFAULT_CLAUDE_MODEL = "claude-opus-4-1-20250805"

# Faster models for structured/classification tasks
BALANCED_CLAUDE_MODEL = "claude-sonnet-4-20250514"
FAST_CLAUDE_MODEL = "claude-3-5-haiku-20241022"

# Default OpenAI models for routed LLM tasks
DEFAULT_OPENAI_MODEL = "gpt-5.5"
BALANCED_OPENAI_MODEL = "gpt-5-mini"
FAST_OPENAI_MODEL = "gpt-5-nano"

# Default Gemini model for image generation
DEFAULT_IMAGE_MODEL = "gemini-2.5-flash-image"

# YouTube thumbnail dimensions
THUMBNAIL_WIDTH = 1280
THUMBNAIL_HEIGHT = 720

# Backend server port
BACKEND_PORT = 8420

# Default directory for final exported project assets.
DEFAULT_EXPORTS_DIR = Path("~/Headless Hero Videos")


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


def parse_json_array_response(text: str, *, key: str | None = None) -> list:
    """Parse a JSON response expected to be an array, tolerating dict-wrapped variants.

    OpenAI's `response_format={"type":"json_object"}` mode forbids top-level arrays,
    so models must wrap them under a key. Pass `key=` to make extraction explicit
    (preferred — matches the wrapper key your prompt asked for). Without `key`,
    falls back to heuristics that handle common shapes like `{"items":[...]}`,
    `{"0":{...},"1":{...}}`, and dict-of-dicts.
    """
    data = parse_json_response(text)
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON array, got {type(data).__name__}")

    # Preferred path: caller specified the wrapper key it asked the model to use.
    if key and isinstance(data.get(key), list):
        return data[key]

    # Common wrapper keys models gravitate to when forced into json_object mode.
    for common in ("items", "results", "data", "list"):
        if isinstance(data.get(common), list):
            return data[common]

    list_values = [v for v in data.values() if isinstance(v, list)]
    if len(list_values) == 1:
        return list_values[0]
    if len(list_values) > 1:
        list_keys = [k for k, v in data.items() if isinstance(v, list)]
        hint = f" (pass key= to disambiguate; expected one of: {list_keys})" if not key else ""
        raise ValueError(
            f"Expected a JSON array, got dict with multiple list values: {list_keys}{hint}"
        )

    if data and all(isinstance(k, str) and k.isdigit() for k in data.keys()):
        return [data[k] for k in sorted(data.keys(), key=int)]

    # Dict-of-dicts shape: {"scene_001": {...}, "scene_002": {...}}.
    if data and all(isinstance(v, dict) for v in data.values()):
        return list(data.values())

    value_types = {k: type(v).__name__ for k, v in list(data.items())[:20]}
    raise ValueError(
        f"Expected a JSON array, got dict with no extractable list "
        f"(keys/types={value_types})"
    )
