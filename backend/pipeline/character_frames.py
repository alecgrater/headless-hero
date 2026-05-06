"""Character frame library — minimal helpers for reading the frame manifest.

The frame generation pipeline has been removed. This module retains only the
constants and read-only helpers that other modules (thumbnail, image_gen,
title_card_composer, remotion_render) depend on.
"""

import json
import logging
from pathlib import Path

from config import DATA_DIR

logger = logging.getLogger(__name__)

CHARACTER_DIR = DATA_DIR / "character"
FRAMES_DIR = CHARACTER_DIR / "frames"
MANIFEST_PATH = CHARACTER_DIR / "manifest.json"
SELECTED_REFERENCE_PATH = FRAMES_DIR / "selected_reference.png"


def get_manifest() -> dict | None:
    """Read the frame manifest, or None if not generated yet."""
    if not MANIFEST_PATH.exists():
        return None
    return json.loads(MANIFEST_PATH.read_text())


def load_variant_counts() -> dict[str, int]:
    """Read manifest and return a map of {frame_id: variant_count}.

    Checks actual files on disk rather than trusting manifest values.
    Returns empty dict if manifest doesn't exist.
    """
    manifest = get_manifest()
    if not manifest:
        return {}
    counts: dict[str, int] = {}
    for f in manifest.get("frames", []):
        fid = f["id"]
        actual = 1
        for v in range(2, f.get("variant_count", 1) + 1):
            if (FRAMES_DIR / f"{fid}_v{v}_closed.png").exists():
                actual = v
            else:
                break
        counts[fid] = actual
    return counts
