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
from sqlmodel import Session

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
    "Target: under 8 seconds of speech (roughly 20-25 words).\n"
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


def check_and_tighten(
    script_id: str,
    session: Session,
    voice_id: str,
    model_id: str = DEFAULT_TTS_MODEL,
    voice_settings: dict | None = None,
) -> list[str]:
    """Check high-energy scenes for duration overruns and rewrite if needed.

    Called after batch voiceover. Returns list of scene IDs that were
    rewritten and re-voiced. Best-effort — failures are logged, not raised.
    """
    record = session.get(Script, script_id)
    if not record:
        logger.warning("Script %s not found for duration variance check", script_id)
        return []

    content = ScriptContent.model_validate(json.loads(record.script_json))
    flagged = _flag_overlong_scenes(content)

    if not flagged:
        logger.info("[%s] Duration variance: no high-energy scenes over %.0fs",
                     script_id, MAX_DURATION_SECONDS)
        return []

    logger.info("[%s] Duration variance: %d high-energy scenes over %.0fs — %s",
                 script_id, len(flagged), MAX_DURATION_SECONDS,
                 [f"{s.id} ({s.audio_duration_seconds:.1f}s)" for s in flagged])

    rewrites = _rewrite_narrations(flagged, script_id=script_id)
    if not rewrites:
        logger.info("[%s] Duration variance: no rewrites returned", script_id)
        return []

    # Build scene lookup for updating
    scene_map = {sc.id: sc for seg in content.segments for sc in seg.scenes}

    tightened: list[str] = []
    for scene_id, new_narration in rewrites.items():
        scene = scene_map.get(scene_id)
        if not scene:
            logger.warning("[%s] Rewrite returned unknown scene_id: %s", script_id, scene_id)
            continue

        try:
            audio_url, duration, word_timestamps = generate_scene_audio(
                scene_id=scene_id,
                narration=new_narration,
                voice_id=voice_id,
                script_id=script_id,
                model_id=model_id,
                voice_settings=voice_settings,
            )
            old_duration = scene.audio_duration_seconds
            scene.narration = new_narration
            scene.audio_url = audio_url
            scene.audio_duration_seconds = duration
            if word_timestamps is not None:
                scene.word_timestamps = word_timestamps
            tightened.append(scene_id)
            logger.info("[%s] Tightened scene %s: %.1fs -> %.1fs",
                         script_id, scene_id, old_duration, duration)
        except Exception:
            logger.exception("[%s] Failed to re-voice scene %s, keeping original",
                              script_id, scene_id)

    if tightened:
        record.script_json = content.model_dump_json()
        session.add(record)
        session.commit()
        logger.info("[%s] Duration variance: tightened %d scenes: %s",
                     script_id, len(tightened), tightened)

    return tightened
