"""Post-script media analyzer — uses Claude to assign optimal media sources per scene."""

import json
import logging
from dataclasses import dataclass

from config import strip_markdown_fences
from integrations.claude_client import chat
from models.script import ScriptContent
from prompts import MEDIA_ANALYZER_SYSTEM

logger = logging.getLogger(__name__)


@dataclass
class MediaAssignment:
    scene_id: str
    media_source: str
    game_name: str | None
    search_query: str | None
    reasoning: str


def analyze_media_sources(
    script_content: ScriptContent,
    gameplay_enabled: bool = True,
    stock_photo_enabled: bool = True,
    script_id: str | None = None,
) -> list[MediaAssignment]:
    """Analyze a completed script and assign media sources per scene.

    Sends the full script to Claude, which returns per-scene assignments
    based on the narrative content.
    """
    sources = ['"ai"']
    if gameplay_enabled:
        sources.append('"gameplay_video"')
    if stock_photo_enabled:
        sources.append('"stock_photo"')
    available_sources = ", ".join(sources)

    system_prompt = MEDIA_ANALYZER_SYSTEM.template.replace("{available_sources}", available_sources)

    scenes_summary = []
    for seg in script_content.segments:
        for scene in seg.scenes:
            scenes_summary.append({
                "scene_id": scene.id,
                "segment": seg.name,
                "narration": scene.narration,
                "visual_prompt": scene.visual_prompt,
                "is_title_card": scene.is_title_card,
            })

    user_message = json.dumps(scenes_summary, indent=2)

    logger.info("[%s] Analyzing media sources for %d scenes (gameplay=%s, stock=%s)",
                script_id or "no-id", len(scenes_summary), gameplay_enabled, stock_photo_enabled)

    response = chat(
        system=system_prompt,
        user_message=user_message,
        max_tokens=4096,
        script_id=script_id,
    )

    cleaned = strip_markdown_fences(response)
    raw_assignments = json.loads(cleaned)

    if not isinstance(raw_assignments, list):
        raise ValueError("Expected JSON array from media analyzer")

    valid_sources = {"ai", "gameplay_video", "stock_photo"}
    assignments = []
    for entry in raw_assignments:
        source = entry.get("media_source", "ai")
        if source not in valid_sources:
            source = "ai"
        if not gameplay_enabled and source == "gameplay_video":
            source = "ai"
        if not stock_photo_enabled and source == "stock_photo":
            source = "ai"

        assignments.append(MediaAssignment(
            scene_id=entry["scene_id"],
            media_source=source,
            game_name=entry.get("game_name"),
            search_query=entry.get("search_query"),
            reasoning=entry.get("reasoning", ""),
        ))

    logger.info("[%s] Media analysis complete: %d ai, %d gameplay, %d stock",
                script_id or "no-id",
                sum(1 for a in assignments if a.media_source == "ai"),
                sum(1 for a in assignments if a.media_source == "gameplay_video"),
                sum(1 for a in assignments if a.media_source == "stock_photo"))

    return assignments


def apply_assignments(
    script_content: ScriptContent,
    assignments: list[MediaAssignment],
) -> None:
    """Patch scene fields in-place based on media assignments."""
    assignment_map = {a.scene_id: a for a in assignments}

    for seg in script_content.segments:
        for scene in seg.scenes:
            assignment = assignment_map.get(scene.id)
            if not assignment:
                continue

            scene.media_source = assignment.media_source

            if assignment.media_source == "gameplay_video" and assignment.game_name:
                scene.gameplay_game_override = assignment.game_name

            if assignment.media_source == "stock_photo" and assignment.search_query:
                scene.original_visual_prompt = scene.visual_prompt
                scene.visual_prompt = assignment.search_query
