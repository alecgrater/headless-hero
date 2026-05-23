"""Add TTS-only punctuation hints to scene narration so the voiceover sounds
more punchy and intentional.

Bare narration tends to be delivered flat by ElevenLabs. This pass uses a
small Claude call (Haiku) to surgically insert ellipses, em-dashes, and
emphasis punctuation. It does NOT rewrite words — only punctuation changes.
The result is stored on Scene.tts_narration and used in place of narration
when sending text to TTS.
"""

import json
import logging

from config import FAST_CLAUDE_MODEL, strip_markdown_fences
from integrations.llm_client import chat
from models.script import Scene

logger = logging.getLogger(__name__)


SYSTEM = """You are a TTS prosody editor. Take video narration text and add minimal
punctuation that makes a text-to-speech engine deliver lines with more drama
and intent.

Rules:
- DO NOT change wording. Only add or substitute punctuation.
- Use ellipses (...) before reveals or to add a beat of suspense.
- Use em-dashes (—) for asides, sudden topic shifts, or strong pauses.
- Replace flat commas with em-dashes only when the pause should be longer.
- Keep periods. Add commas only where rhythm clearly benefits.
- Surgical changes only — many scenes need zero changes. Do not over-punctuate.
- Output JSON: {"scenes": [{"scene_id": "...", "tts_narration": "..."}]}.
  Include EVERY input scene_id, in the same order, even if unchanged."""


def dramatize_for_tts(scenes: list[Scene], *, script_id: str | None = None) -> dict[str, str]:
    """Return {scene_id: tts_narration} for non-title-card scenes.

    Skips title cards (those get separate framing). Returns an empty dict on
    any failure so callers transparently fall back to raw narration.
    """
    targets = [sc for sc in scenes if not sc.is_title_card and (sc.narration or "").strip()]
    if not targets:
        return {}

    payload = {"scenes": [{"scene_id": sc.id, "narration": sc.narration} for sc in targets]}

    try:
        raw = chat(
            system=SYSTEM,
            user_message=json.dumps(payload, indent=2),
            model=FAST_CLAUDE_MODEL,
            max_tokens=8192,
            json_mode=True,
            task="dramatize",
            script_id=script_id,
        )
    except Exception:
        logger.exception("[%s] Dramatize TTS pass failed; falling back to raw narration", script_id)
        return {}

    try:
        data = json.loads(strip_markdown_fences(raw))
    except (TypeError, ValueError):
        logger.warning("[%s] Dramatize response was not valid JSON; falling back", script_id)
        return {}

    items = data.get("scenes") if isinstance(data, dict) else data
    if not isinstance(items, list):
        logger.warning("[%s] Dramatize response missing 'scenes' array", script_id)
        return {}

    out: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        sid = item.get("scene_id")
        text = item.get("tts_narration") or item.get("narration")
        if isinstance(sid, str) and isinstance(text, str) and text.strip():
            out[sid] = text.strip()

    logger.info(
        "[%s] Dramatize TTS pass: %d/%d scenes returned tts_narration",
        script_id, len(out), len(targets),
    )
    return out
