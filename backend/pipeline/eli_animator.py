"""Eli pose picker — selects one character pose per scene via Claude."""

import json
import logging

from integrations.claude_client import chat
from config import FAST_CLAUDE_MODEL
from pipeline.character_frames import get_manifest
from prompts import ELI_POSE_PICKER_SYSTEM

logger = logging.getLogger(__name__)

CORNERS = ["TL", "TR", "BL", "BR"]
LEFT_CORNERS = {"TL", "BL"}
RIGHT_CORNERS = {"TR", "BR"}
BOTTOM_CORNERS = {"BL", "BR"}


def _pick_corner(previous_corner: str | None) -> str:
    """Deterministic corner alternation: left↔right, 70% bottom."""
    if not previous_corner:
        return "BR"
    if previous_corner in LEFT_CORNERS:
        return "BR"
    return "BL"


def generate_scene_eli(
    narration: str,
    previous_corner: str | None = None,
) -> dict:
    """Pick one pose for a scene based on narration tone.

    Returns: {"enabled": True, "corner": "BR", "frame_id": "thinking_handonchin"}
    """
    manifest = get_manifest()
    if not manifest or not manifest.get("frames"):
        return {"enabled": True, "corner": _pick_corner(previous_corner), "frame_id": "neutral_standingneutral"}

    frame_ids = [f["id"] for f in manifest["frames"]]

    user_msg = json.dumps({
        "narration": narration,
        "available_poses": frame_ids,
        "previous_corner": previous_corner,
    })

    text = chat(
        system=ELI_POSE_PICKER_SYSTEM.template,
        user_message=user_msg,
        max_tokens=200,
        model=FAST_CLAUDE_MODEL,
        json_mode=True,
    )

    try:
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(text)
    except (json.JSONDecodeError, IndexError, AttributeError) as e:
        logger.warning("Failed to parse Eli pose response: %s — using fallback", e)
        return {"enabled": True, "corner": _pick_corner(previous_corner), "frame_id": "neutral_standingneutral"}

    frame_id = result.get("frame_id", "neutral_standingneutral")
    corner = result.get("corner", _pick_corner(previous_corner))

    if frame_id not in frame_ids:
        frame_id = "neutral_standingneutral" if "neutral_standingneutral" in frame_ids else frame_ids[0]
    if corner not in CORNERS:
        corner = _pick_corner(previous_corner)
    if corner == previous_corner:
        corner = _pick_corner(previous_corner)

    return {"enabled": True, "corner": corner, "frame_id": frame_id}
