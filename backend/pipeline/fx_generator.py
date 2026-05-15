"""FX generator — uses the routed LLM provider to assign visual effects to each scene.

Simplified to zoom punches only — 3-6 per video, asymmetric scale hits on key moments.

Chapter markers are computed deterministically in remotion_render.py — no AI needed.
"""

import json
import logging

from config import strip_markdown_fences
from integrations.llm_client import chat
from models.script import SceneFX
from prompts import FX_SYSTEM

logger = logging.getLogger(__name__)


def generate_scene_fx(scene_data: dict, script_id: str | None = None) -> dict:
    """Generate FX for a single scene. Used for per-scene regeneration.

    Takes a scene summary dict (same format as in batch), returns {id, fx}.
    """
    scene_id = scene_data.get("id", "unknown")
    logger.info("[%s] Generating FX for scene %s (beat=%s, duration=%.1fs)",
                script_id or "no-id", scene_id,
                scene_data.get("visual_beat", "unknown"),
                scene_data.get("duration_seconds", 0))

    user_message = json.dumps([scene_data], indent=2)

    response = chat(
        system=FX_SYSTEM.template,
        user_message=user_message,
        max_tokens=2048,
        script_id=script_id,
        json_mode=True,
        task="fx",
    )

    cleaned = strip_markdown_fences(response)
    fx_list = json.loads(cleaned)

    if not isinstance(fx_list, list) or len(fx_list) == 0:
        raise ValueError("Expected non-empty JSON array from Claude FX generator")

    entry = fx_list[0]
    fx_data = entry.get("fx", {})
    transition_in = entry.get("transition_in", "cut")

    SceneFX.model_validate(fx_data)

    has_zoom = fx_data.get("zoom_punch") is not None
    has_drift = fx_data.get("drift") is not None
    logger.info("[%s] FX assigned for scene %s: drift=%s zoom_punch=%s transition_in=%s",
                script_id or "no-id", scene_id, has_drift, has_zoom, transition_in)
    return {"id": entry.get("id", scene_data.get("id")), "fx": fx_data, "transition_in": transition_in}
