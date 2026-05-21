"""Post-script media analyzer — uses the routed LLM provider to assign optimal media sources per scene."""

import json
import logging
import re
from dataclasses import dataclass

from config import parse_json_array_response, strip_markdown_fences
from integrations.llm_client import chat
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


def _resolve_scene_id(raw_scene_id: str, valid_scene_ids: set[str]) -> str | None:
    """Resolve minor LLM scene-id formatting drift like scene_3 -> scene_003."""
    if raw_scene_id in valid_scene_ids:
        return raw_scene_id
    match = re.fullmatch(r"scene_(\d+)", raw_scene_id)
    if not match:
        return None
    number = int(match.group(1))
    for width in (3, 2, 1):
        candidate = f"scene_{number:0{width}d}"
        if candidate in valid_scene_ids:
            return candidate
    return None


def analyze_media_sources(
    script_content: ScriptContent,
    gameplay_enabled: bool = True,
    stock_photo_enabled: bool = True,
    ai_video_enabled: bool = False,
    animated_scene_count: int = 0,
    script_id: str | None = None,
) -> list[MediaAssignment]:
    """Analyze a completed script and assign media sources per scene.

    Sends the full script to the routed LLM provider, which returns per-scene
    assignments based on the narrative content.
    """
    sources = ['"ai"']
    if ai_video_enabled and animated_scene_count > 0:
        sources.append('"ai_video"')
    if gameplay_enabled:
        sources.append('"gameplay_video"')
    if stock_photo_enabled:
        sources.append('"stock_photo"')
    available_sources = ", ".join(sources)

    ai_video_limit = max(0, animated_scene_count if ai_video_enabled else 0)
    system_prompt = (
        MEDIA_ANALYZER_SYSTEM.template
        .replace("{available_sources}", available_sources)
        .replace("{ai_video_limit}", str(ai_video_limit))
    )

    scenes_summary = []
    scene_segments: dict[str, str] = {}
    valid_scene_ids: set[str] = set()
    for seg in script_content.segments:
        for scene in seg.scenes:
            valid_scene_ids.add(scene.id)
            scene_segments[scene.id] = seg.name
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
        max_tokens=16384,
        script_id=script_id,
        json_mode=True,
        task="media",
    )

    cleaned = strip_markdown_fences(response)
    raw_assignments = parse_json_array_response(cleaned, key="assignments")

    valid_sources = {"ai", "ai_video", "gameplay_video", "stock_photo"}
    assignments = []
    ai_video_assigned = 0
    segment_ai_video_counts: dict[str, int] = {}
    for entry in raw_assignments:
        source = entry.get("media_source", "ai")
        if source not in valid_sources:
            source = "ai"
        scene_id = _resolve_scene_id(str(entry.get("scene_id", "")), valid_scene_ids)
        if not scene_id:
            logger.warning("Skipping media assignment for unknown scene id: %r", entry.get("scene_id"))
            continue
        segment_name = scene_segments.get(scene_id, "")
        if not ai_video_enabled and source == "ai_video":
            source = "ai"
        if source == "ai_video":
            if ai_video_assigned >= ai_video_limit or segment_ai_video_counts.get(segment_name, 0) >= 1:
                source = "ai"
            else:
                ai_video_assigned += 1
                segment_ai_video_counts[segment_name] = segment_ai_video_counts.get(segment_name, 0) + 1
        if not gameplay_enabled and source == "gameplay_video":
            source = "ai"
        if not stock_photo_enabled and source == "stock_photo":
            source = "ai"

        assignments.append(MediaAssignment(
            scene_id=scene_id,
            media_source=source,
            game_name=entry.get("game_name"),
            search_query=entry.get("search_query"),
            reasoning=entry.get("reasoning", ""),
        ))

    logger.info("[%s] Media analysis complete: %d ai, %d ai_video, %d gameplay, %d stock",
                script_id or "no-id",
                sum(1 for a in assignments if a.media_source == "ai"),
                sum(1 for a in assignments if a.media_source == "ai_video"),
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

            previous_source = scene.media_source
            scene.media_source = assignment.media_source

            if assignment.media_source == "gameplay_video":
                scene.gameplay_game_override = assignment.game_name or ""
            else:
                scene.gameplay_game_override = ""

            if assignment.media_source == "stock_photo":
                if previous_source != "stock_photo" and not scene.original_visual_prompt:
                    scene.original_visual_prompt = scene.visual_prompt
                if assignment.search_query is not None:
                    scene.visual_prompt = assignment.search_query
            elif previous_source == "stock_photo" and scene.original_visual_prompt:
                scene.visual_prompt = scene.original_visual_prompt
                scene.original_visual_prompt = ""
