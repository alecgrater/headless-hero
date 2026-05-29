"""Duration variance diagnostics for voiceover timing.

This module intentionally does not rewrite saved scene narration. Normal scene
narration is the source of truth and should be sent to TTS as-written, aside
from deterministic hidden TTS tags added by ``prepare_tts_text``.
"""

import json
import logging

from models.script import Scene, Script, ScriptContent
from sqlmodel import Session

logger = logging.getLogger(__name__)

HIGH_ENERGY_BEATS = {"multi_frame", "captions"}
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


def check_and_tighten(
    script_id: str,
    session: Session,
    *_: object,
    **__: object,
) -> list[str]:
    """Log overlong high-energy scenes without changing narration or audio.

    The function name is retained for old imports/tests, but the behavior is now
    diagnostic only. Script pacing fixes should happen during script generation
    or through explicit editor action, not an automatic post-voiceover rewrite.
    """
    record = session.get(Script, script_id)
    if not record:
        logger.warning("Script %s not found for duration variance check", script_id)
        return []

    content = ScriptContent.model_validate(json.loads(record.script_json))
    flagged = _flag_overlong_scenes(content)

    if not flagged:
        logger.info(
            "[%s] Duration variance: no high-energy scenes over %.0fs",
            script_id,
            MAX_DURATION_SECONDS,
        )
        return []

    logger.warning(
        "[%s] Duration variance: %d high-energy scenes over %.0fs; leaving narration unchanged: %s",
        script_id,
        len(flagged),
        MAX_DURATION_SECONDS,
        [f"{s.id} ({s.audio_duration_seconds:.1f}s)" for s in flagged],
    )
    return []
