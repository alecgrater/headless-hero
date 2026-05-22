"""FX generator — uses the routed LLM provider to assign visual effects to each scene.

Simplified to zoom punches only — 3-6 per video, asymmetric scale hits on key moments.

Chapter markers are computed deterministically in remotion_render.py — no AI needed.
"""

import json
import logging

from config import parse_json_array_response, strip_markdown_fences
from integrations.llm_client import chat
from models.script import ALLOWED_TRANSITIONS, SceneFX
from prompts import FX_SYSTEM

logger = logging.getLogger(__name__)

_BATCH_SIZE = 12
_BATCH_MAX_TOKENS = 8192


def _normalize_transition_in(value: object, scene_id: str, script_id: str | None = None) -> str:
    if isinstance(value, str) and value in ALLOWED_TRANSITIONS:
        return value

    logger.warning(
        "[%s] FX generator returned invalid transition_in for scene %s: %r; using cut",
        script_id or "no-id",
        scene_id,
        value,
    )
    return "cut"


def _validate_entry(entry: dict, expected_id: str, script_id: str | None) -> dict | None:
    """Validate one batch entry into the standard {id, fx, transition_in} shape.

    Returns None when validation fails so the caller can retry the scene
    individually.
    """
    if not isinstance(entry, dict):
        return None
    fx_data = entry.get("fx", {})
    if not isinstance(fx_data, dict):
        return None
    try:
        SceneFX.model_validate(fx_data)
    except Exception:
        logger.warning("[%s] FX batch entry for scene %s failed SceneFX validation",
                       script_id or "no-id", expected_id, exc_info=True)
        return None
    transition_in = _normalize_transition_in(entry.get("transition_in", "cut"), expected_id, script_id)
    return {
        "id": entry.get("id", expected_id),
        "fx": fx_data,
        "transition_in": transition_in,
    }


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
    fx_list = parse_json_array_response(cleaned, key="scenes")

    if len(fx_list) == 0:
        raise ValueError("Expected non-empty JSON array from FX generator")

    entry = fx_list[0]
    fx_data = entry.get("fx", {})
    transition_in = _normalize_transition_in(entry.get("transition_in", "cut"), scene_id, script_id)

    SceneFX.model_validate(fx_data)

    has_zoom = fx_data.get("zoom_punch") is not None
    has_drift = fx_data.get("drift") is not None
    logger.info("[%s] FX assigned for scene %s: drift=%s zoom_punch=%s transition_in=%s",
                script_id or "no-id", scene_id, has_drift, has_zoom, transition_in)
    return {"id": entry.get("id", scene_data.get("id")), "fx": fx_data, "transition_in": transition_in}


def generate_fx_batch(
    scenes_data: list[dict],
    script_id: str | None = None,
) -> dict[str, dict]:
    """Generate FX for many scenes per LLM call.

    Splits `scenes_data` into chunks of `_BATCH_SIZE` and asks the model to
    return a JSON object `{"scenes": [...]}` with one entry per scene.
    Returns a dict keyed by scene id; entries that fail validation or are
    missing from the response are simply absent — the caller is expected to
    retry those individually via `generate_scene_fx`.
    """
    results: dict[str, dict] = {}
    if not scenes_data:
        return results

    total = len(scenes_data)
    for chunk_start in range(0, total, _BATCH_SIZE):
        chunk = scenes_data[chunk_start:chunk_start + _BATCH_SIZE]
        chunk_ids = [scene.get("id", "?") for scene in chunk]
        logger.info(
            "[%s] FX batch: chunk %d-%d of %d (%d scenes)",
            script_id or "no-id",
            chunk_start + 1,
            chunk_start + len(chunk),
            total,
            len(chunk),
        )

        user_message = json.dumps(chunk, indent=2)

        try:
            response = chat(
                system=FX_SYSTEM.template,
                user_message=user_message,
                max_tokens=_BATCH_MAX_TOKENS,
                script_id=script_id,
                json_mode=True,
                task="fx",
                cache=True,
            )
        except Exception:
            logger.warning(
                "[%s] FX batch call failed for chunk starting at %d (%d scenes); "
                "callers should fall back to per-scene retries",
                script_id or "no-id", chunk_start, len(chunk), exc_info=True,
            )
            continue

        cleaned = strip_markdown_fences(response)
        try:
            entries = parse_json_array_response(cleaned, key="scenes")
        except Exception:
            logger.warning(
                "[%s] FX batch response could not be parsed for chunk starting at %d",
                script_id or "no-id", chunk_start, exc_info=True,
            )
            continue

        # Match returned entries to input scenes by id when possible; fall back
        # to positional alignment when ids are missing/duplicated.
        by_id: dict[str, dict] = {}
        ordered: list[dict] = []
        for entry in entries:
            if isinstance(entry, dict):
                ordered.append(entry)
                eid = entry.get("id")
                if isinstance(eid, str):
                    by_id[eid] = entry

        for pos, expected_id in enumerate(chunk_ids):
            entry = by_id.get(expected_id)
            if entry is None and pos < len(ordered):
                entry = ordered[pos]
            if entry is None:
                continue
            validated = _validate_entry(entry, expected_id, script_id)
            if validated is not None:
                results[expected_id] = validated

    logger.info(
        "[%s] FX batch produced %d/%d valid entries",
        script_id or "no-id", len(results), total,
    )
    return results
