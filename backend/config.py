"""Shared configuration constants and utilities for the backend."""

import os
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


def strip_markdown_fences(text: str) -> str:
    """Strip markdown code fences (```json ... ```) from an LLM response."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()
