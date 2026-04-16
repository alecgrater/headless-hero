"""Duration variance — tighten overlong high-energy scenes after voiceover.

After batch voiceover, checks quick_cuts and aha_subtitle scenes against a
duration threshold. If any exceed it, rewrites narration via Claude and
re-voices in a single pass.
"""

import json
import logging

from config import DEFAULT_TTS_MODEL, strip_markdown_fences
from integrations.claude_client import chat
from models.script import Scene, Script, ScriptContent
from pipeline.voiceover import generate_scene_audio

logger = logging.getLogger(__name__)

HIGH_ENERGY_BEATS = {"quick_cuts", "aha_subtitle"}
MAX_DURATION_SECONDS = 10.0


def _flag_overlong_scenes(content: ScriptContent) -> list[Scene]:
    """Return high-energy scenes whose audio exceeds the duration threshold."""
    flagged: list[Scene] = []
    for scene in content.all_scenes():
        if (
            scene.visual_beat in HIGH_ENERGY_BEATS
            and scene.audio_duration_seconds > MAX_DURATION_SECONDS
        ):
            flagged.append(scene)
    return flagged


_TIGHTEN_SYSTEM_PROMPT = (
    "You are a script editor. You will receive high-energy video scenes whose narration is too long.\n"
    "Rewrite each narration to be shorter and punchier while preserving the core fact or message.\n"
    "- quick_cuts scenes: 1 short punchy sentence\n"
    "- aha_subtitle scenes: 1 short sentence with the key stat or fact\n"
    'Return ONLY valid JSON: {"scene_id": "new narration", ...}'
)


def _rewrite_narrations(
    scenes: list[Scene],
    script_id: str | None = None,
) -> dict[str, str]:
    """Call Claude to rewrite overlong narrations. Returns {scene_id: new_narration}.

    Returns empty dict on any failure (best-effort).
    """
    payload = [
        {
            "scene_id": sc.id,
            "visual_beat": sc.visual_beat,
            "narration": sc.narration,
            "current_duration_seconds": sc.audio_duration_seconds,
        }
        for sc in scenes
    ]

    try:
        response = chat(
            system=_TIGHTEN_SYSTEM_PROMPT,
            user_message=json.dumps(payload, indent=2),
            max_tokens=2048,
            script_id=script_id,
        )
        cleaned = strip_markdown_fences(response)
        result = json.loads(cleaned)
        if not isinstance(result, dict):
            logger.warning("Claude returned non-dict for narration rewrite: %s", type(result))
            return {}
        logger.info("Claude rewrote %d narrations", len(result))
        return result
    except Exception:
        logger.exception("Failed to rewrite narrations via Claude")
        return {}
