"""Scene refinement pipeline — polishes human-edited scenes to match script tone."""

import json
import logging

from config import strip_markdown_fences
from integrations.llm_client import chat
from models.script import Scene, ScriptContent
from pipeline.formats import resolve_format
from prompts import REFINE_SYSTEM

logger = logging.getLogger(__name__)


def _format_refine_addendum(script: ScriptContent) -> str:
    """Return format-specific guardrails for LLM scene refinement."""
    fmt = resolve_format(script.format_id)
    if fmt.id == "life-as-a":
        return (
            "\n\n## Format-Specific Guardrails: Your Life As A\n"
            "- Preserve second-person, present-tense narration.\n"
            "- Preserve the observational, literary register; do not add listicle cadence, punchlines, "
            "rule-of-three escalation, greetings, or YouTube-host language.\n"
            "- Keep chapter-card narration descriptor-only when `is_title_card` is true; do not add "
            "`Level N` because the TTS layer handles that.\n"
            "- Keep one short visual/narrative beat per non-title scene, roughly matching the original length.\n"
            "- Preserve protagonist continuity and life-path immersion in visual prompts.\n"
        )
    return (
        f"\n\n## Format-Specific Guardrails: {fmt.display_name}\n"
        f"- This script uses `{fmt.id}`. Match its surrounding narration and section structure.\n"
        "- Do not introduce recap language, subscribe requests, or whole-video CTAs into scene narration.\n"
    )


def refine_scene(
    script: ScriptContent,
    segment_index: int,
    scene_id: str,
) -> Scene:
    """Refine a human-edited scene to match the surrounding script's tone.

    Args:
        script: The full script content for context.
        segment_index: Index of the segment containing the scene.
        scene_id: ID of the scene to refine.

    Returns:
        A refined Scene object.
    """
    segment = script.segments[segment_index]
    target_scene = next(s for s in segment.scenes if s.id == scene_id)

    logger.info("Refining scene %s in segment %d", scene_id, segment_index)

    # Build context: surrounding scenes for tone reference
    context_scenes: list[dict] = []
    for seg in script.segments:
        for sc in seg.scenes:
            context_scenes.append({
                "id": sc.id,
                "narration": sc.narration,
            })

    user_message = json.dumps({
        "script_title": script.title,
        "intro_hook": script.intro_hook,
        "surrounding_context": context_scenes,
        "segment_name": segment.name,
        "scene_to_refine": target_scene.model_dump(),
    })

    system_prompt = REFINE_SYSTEM.template + _format_refine_addendum(script)
    raw = chat(system_prompt, user_message, max_tokens=2048, json_mode=True, task="script")

    text = strip_markdown_fences(raw)

    data = json.loads(text)
    # Preserve fields that shouldn't change
    data["id"] = target_scene.id
    data["is_title_card"] = target_scene.is_title_card
    data["image_url"] = target_scene.image_url
    data["audio_url"] = target_scene.audio_url
    data["audio_duration_seconds"] = target_scene.audio_duration_seconds

    refined = Scene.model_validate(data)
    logger.info("Scene %s refined successfully", scene_id)
    return refined
