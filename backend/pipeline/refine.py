"""Scene refinement pipeline — polishes human-edited scenes to match script tone."""

import json
import logging

from config import strip_markdown_fences
from integrations.llm_client import chat
from models.script import Scene, ScriptContent
from prompts import REFINE_SYSTEM

logger = logging.getLogger(__name__)


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

    raw = chat(REFINE_SYSTEM.template, user_message, max_tokens=2048, json_mode=True, task="script")

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
