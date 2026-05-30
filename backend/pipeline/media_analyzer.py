"""Post-script visual-mode analyzer — uses the routed LLM provider to assign AI video scenes."""

import json
import logging
import re

from config import parse_json_array_response, strip_markdown_fences
from integrations.llm_client import chat
from models.script import Scene, ScriptContent
from prompts import MEDIA_ANALYZER_SYSTEM

logger = logging.getLogger(__name__)


AI_VIDEO_MOTION_TERMS = {
    "walk",
    "walking",
    "slide",
    "sliding",
    "move",
    "moving",
    "turn",
    "turning",
    "shift",
    "shifting",
    "drive",
    "driving",
    "passes",
    "passing",
    "open",
    "opening",
    "close",
    "closing",
    "gesture",
    "reveal",
    "drift",
    "fills",
    "emptying",
    "cycle",
    "change",
    "changing",
    "transition",
}

AI_VIDEO_STATIC_OBJECT_TERMS = {
    "checklist",
    "clipboard",
    "paperwork",
    "calendar",
    "paper",
    "document",
    "plate",
    "television",
}

AI_VIDEO_MAX_ROUTED_DURATION_SECONDS = 6.5


class MediaAssignment:
    __slots__ = ("scene_id", "game_name", "search_query", "reasoning", "visual_mode", "_legacy_media_source")

    def __init__(
        self,
        scene_id: str,
        game_name: str | None = None,
        search_query: str | None = None,
        reasoning: str = "",
        visual_mode: str = "full_frame",
        media_source: str = "",
    ) -> None:
        if game_name in {"ai", "ai_video", "gameplay_video", "stock_photo", "user_upload", "real_photo"}:
            media_source = str(game_name)
            game_name = search_query
            search_query = reasoning
            reasoning = "" if visual_mode == "full_frame" else visual_mode
            visual_mode = "video" if media_source == "ai_video" else "full_frame"
        self.scene_id = scene_id
        self.game_name = game_name
        self.search_query = search_query
        self.reasoning = reasoning
        self._legacy_media_source = media_source
        self.visual_mode = _canonical_visual_mode(visual_mode, media_source)

    @property
    def media_source(self) -> str:
        if self._legacy_media_source in {"gameplay_video", "stock_photo", "user_upload", "real_photo"}:
            return self._legacy_media_source
        return "ai_video" if self.visual_mode == "video" else "ai"


def _canonical_visual_mode(value: str, legacy_media_source: str = "") -> str:
    if legacy_media_source == "ai_video":
        return "video"
    if value in {"quick_cuts", "montage", "multi_frame"}:
        return "multi_frame"
    if value == "continuous":
        return "continuous"
    if value in {"video", "full_frame", "popup_sequence", "flipflop", "comparison_board", "captions", "stat_card", "dossier"}:
        return value
    return "full_frame"


def _valid_existing_script_mode(scene: Scene) -> str:
    """Return a script-chosen mode worth preserving during AI-video analysis."""
    mode = _canonical_visual_mode(scene.visual_mode)
    if scene.is_title_card or mode in {"full_frame", "video"}:
        return ""
    if mode == "captions" and not scene.caption_text.strip():
        return ""
    if mode == "stat_card" and not scene.stat_value.strip():
        return ""
    return mode


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


def _shot_type(scene: Scene) -> str:
    match = re.match(r"\[([^\]]+)\]", scene.visual_prompt.strip())
    return match.group(1).strip().upper() if match else ""


def _has_ai_image_frame(scene: Scene) -> bool:
    if not scene.frame_directives:
        return True
    return any(frame.source == "ai_generated" for frame in scene.frame_directives)


def _known_audio_duration_seconds(scene: Scene) -> float | None:
    return scene.audio_duration_seconds if scene.audio_duration_seconds > 0 else None


def is_ai_video_eligible(
    scene: Scene,
    _current_source: str = "ai",
    *,
    require_eli_scene: bool = False,
    life_as_a_role: str = "",
    enforce_duration_cap: bool = True,
    max_duration_seconds: float = AI_VIDEO_MAX_ROUTED_DURATION_SECONDS,
) -> bool:
    if scene.is_title_card:
        return False
    if scene.visual_mode == "captions" or scene.visual_beat == "aha_subtitle":
        return False
    if scene.visual_mode == "stat_card":
        return False
    known_audio_duration = _known_audio_duration_seconds(scene)
    if (
        enforce_duration_cap
        and known_audio_duration is not None
        and known_audio_duration > max_duration_seconds
    ):
        return False
    if not scene.visual_prompt.strip():
        return False
    if _shot_type(scene) == "DIAGRAM":
        return False
    if require_eli_scene:
        from pipeline.formats.life_as_a import is_life_as_a_eli_scene, is_life_as_a_solo_ai_video_scene

        if not is_life_as_a_eli_scene(scene, life_as_a_role):
            return False
        if not is_life_as_a_solo_ai_video_scene(scene, life_as_a_role):
            return False
    return _has_ai_image_frame(scene)


_is_ai_video_eligible = is_ai_video_eligible


def _ai_video_candidate_score(scene: Scene) -> int:
    text = f"{scene.visual_prompt} {scene.narration}".lower()
    score = 0

    if scene.visual_beat == "continuous":
        score += 50
    elif scene.visual_beat == "static":
        score += 18
    elif scene.visual_beat in {"quick_cuts", "multi_frame"}:
        score += 8

    shot = _shot_type(scene)
    if shot == "REACTION":
        score += 28
    elif shot == "ESTABLISHING":
        score += 20
    elif shot == "METAPHOR":
        score += 16
    elif shot == "CLOSE-UP":
        score += 10

    if scene.contains_person or "guard" in text or "figure" in text or "officer" in text:
        score += 10

    motion_hits = sum(1 for term in AI_VIDEO_MOTION_TERMS if term in text)
    score += min(motion_hits, 6) * 8

    static_hits = sum(1 for term in AI_VIDEO_STATIC_OBJECT_TERMS if term in text)
    score -= min(static_hits, 3) * 5

    if len(scene.narration) > 180:
        score += 5

    return score


def _scene_order(script_content: ScriptContent) -> list[str]:
    return [scene.id for scene in script_content.all_scenes()]


def _has_adjacent_ai_video(
    scene_id: str,
    assignments_by_scene: dict[str, MediaAssignment],
    ordered_scene_ids: list[str],
) -> bool:
    try:
        scene_index = ordered_scene_ids.index(scene_id)
    except ValueError:
        return False

    adjacent_scene_ids = []
    if scene_index > 0:
        adjacent_scene_ids.append(ordered_scene_ids[scene_index - 1])
    if scene_index < len(ordered_scene_ids) - 1:
        adjacent_scene_ids.append(ordered_scene_ids[scene_index + 1])

    return any(
        assignments_by_scene.get(adjacent_scene_id, MediaAssignment(adjacent_scene_id, None, None, "")).visual_mode
        == "video"
        for adjacent_scene_id in adjacent_scene_ids
    )


def _remove_adjacent_ai_video_assignments(
    script_content: ScriptContent,
    assignments_by_scene: dict[str, MediaAssignment],
    scenes_by_id: dict[str, Scene],
    scene_segment_indexes: dict[str, int],
    segment_ai_video_counts: dict[int, int],
) -> int:
    """Downgrade the weaker scene in each adjacent AI-video pair."""
    ordered_scene_ids = _scene_order(script_content)
    for left_id, right_id in zip(ordered_scene_ids, ordered_scene_ids[1:]):
        left = assignments_by_scene.get(left_id)
        right = assignments_by_scene.get(right_id)
        if not left or not right:
            continue
        if left.visual_mode != "video" or right.visual_mode != "video":
            continue

        left_scene = scenes_by_id.get(left_id)
        right_scene = scenes_by_id.get(right_id)
        if not left_scene or not right_scene:
            downgrade_id = right_id
        elif _ai_video_candidate_score(left_scene) >= _ai_video_candidate_score(right_scene):
            downgrade_id = right_id
        else:
            downgrade_id = left_id

        existing = assignments_by_scene[downgrade_id]
        existing_script_mode = _valid_existing_script_mode(scenes_by_id[downgrade_id]) if downgrade_id in scenes_by_id else ""
        assignments_by_scene[downgrade_id] = MediaAssignment(
            scene_id=downgrade_id,
            game_name=None,
            search_query=None,
            reasoning=(
                existing.reasoning
                or "Downgraded to AI art so AI-video scenes are not back to back."
            ),
            visual_mode=existing_script_mode or "full_frame",
        )
        segment_index = scene_segment_indexes.get(downgrade_id)
        if segment_index is not None:
            segment_ai_video_counts[segment_index] = max(0, segment_ai_video_counts.get(segment_index, 0) - 1)

    return sum(1 for assignment in assignments_by_scene.values() if assignment.visual_mode == "video")


def analyze_media_sources(
    script_content: ScriptContent,
    gameplay_enabled: bool = True,
    stock_photo_enabled: bool = True,
    ai_video_enabled: bool = False,
    animated_scene_count: int = 0,
    ai_video_scenes_per_segment: int = 2,
    script_id: str | None = None,
) -> list[MediaAssignment]:
    """Analyze a completed script and assign visual modes per scene.

    Sends the full script to the routed LLM provider, which returns per-scene
    assignments based on the narrative content.
    """
    ai_video_scenes_per_segment = max(0, ai_video_scenes_per_segment)
    ai_video_available = ai_video_enabled and animated_scene_count > 0 and ai_video_scenes_per_segment > 0

    gameplay_enabled = False
    stock_photo_enabled = False

    modes = ['"full_frame"']
    if ai_video_available:
        modes.append('"video"')
    available_sources = ", ".join(modes)

    segment_count = len(script_content.segments)
    ai_video_limit = max(
        0,
        max(animated_scene_count, segment_count * ai_video_scenes_per_segment) if ai_video_available else 0,
    )
    require_eli_scene_for_ai_video = script_content.format_id == "life-as-a"
    life_as_a_role = ""
    if require_eli_scene_for_ai_video:
        from pipeline.formats.life_as_a import life_as_a_chunking_settings, life_as_a_role as resolve_life_as_a_role

        life_as_a_role = resolve_life_as_a_role(script_content)
        ai_video_max_duration = float(life_as_a_chunking_settings()["single_visual_max"])
    else:
        ai_video_max_duration = AI_VIDEO_MAX_ROUTED_DURATION_SECONDS
    system_prompt = (
        MEDIA_ANALYZER_SYSTEM.template
        .replace("{available_sources}", available_sources)
        .replace("{ai_video_limit}", str(ai_video_limit))
        .replace("{ai_video_scenes_per_segment}", str(ai_video_scenes_per_segment))
    )

    scenes_summary = []
    scene_segment_indexes: dict[str, int] = {}
    scenes_by_id: dict[str, Scene] = {}
    valid_scene_ids: set[str] = set()
    for seg_index, seg in enumerate(script_content.segments):
        for scene in seg.scenes:
            valid_scene_ids.add(scene.id)
            scene_segment_indexes[scene.id] = seg_index
            scenes_by_id[scene.id] = scene
            scenes_summary.append({
                "scene_id": scene.id,
                "segment": seg.name,
                "narration": scene.narration,
                "visual_prompt": scene.visual_prompt,
                "is_title_card": scene.is_title_card,
            })

    user_message = json.dumps(scenes_summary, indent=2)

    logger.info("[%s] Analyzing visual modes for %d scenes (ai_video=%s)",
                script_id or "no-id", len(scenes_summary), ai_video_available)

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

    assignments_by_scene: dict[str, MediaAssignment] = {}
    ai_video_assigned = 0
    segment_ai_video_counts: dict[int, int] = {}
    ordered_scene_ids = _scene_order(script_content)
    for entry in raw_assignments:
        mode = _canonical_visual_mode(
            str(entry.get("visual_mode") or entry.get("media_source") or entry.get("visual_beat") or "full_frame"),
            str(entry.get("media_source") or ""),
        )
        scene_id = _resolve_scene_id(str(entry.get("scene_id", "")), valid_scene_ids)
        if not scene_id:
            logger.warning("Skipping media assignment for unknown scene id: %r", entry.get("scene_id"))
            continue
        if scene_id in assignments_by_scene:
            logger.warning("Skipping duplicate media assignment for scene id: %s", scene_id)
            continue
        segment_index = scene_segment_indexes.get(scene_id, -1)
        scene = scenes_by_id[scene_id]
        existing_script_mode = _valid_existing_script_mode(scene)
        if not ai_video_available and mode == "video":
            mode = existing_script_mode or "full_frame"
        if mode == "video":
            if (
                ai_video_assigned >= ai_video_limit
                or segment_ai_video_counts.get(segment_index, 0) >= ai_video_scenes_per_segment
                or _has_adjacent_ai_video(scene_id, assignments_by_scene, ordered_scene_ids)
                or not _is_ai_video_eligible(
                    scene,
                    require_eli_scene=require_eli_scene_for_ai_video,
                    life_as_a_role=life_as_a_role,
                    max_duration_seconds=ai_video_max_duration,
                )
            ):
                mode = existing_script_mode or "full_frame"
            else:
                ai_video_assigned += 1
                segment_ai_video_counts[segment_index] = segment_ai_video_counts.get(segment_index, 0) + 1
        elif mode == "full_frame" and existing_script_mode:
            mode = existing_script_mode
        assignments_by_scene[scene_id] = MediaAssignment(
            scene_id=scene_id,
            game_name=entry.get("game_name"),
            search_query=entry.get("search_query"),
            reasoning=entry.get("reasoning", ""),
            visual_mode=mode,
        )

    for scene in script_content.all_scenes():
        if scene.id not in assignments_by_scene:
            assignments_by_scene[scene.id] = MediaAssignment(
                scene_id=scene.id,
                game_name=None,
                search_query=None,
                reasoning="Defaulted to AI art because the media analyzer omitted this scene.",
                visual_mode=_canonical_visual_mode(scene.visual_mode),
            )

    ai_video_assigned = _remove_adjacent_ai_video_assignments(
        script_content,
        assignments_by_scene,
        scenes_by_id,
        scene_segment_indexes,
        segment_ai_video_counts,
    )

    assignments = [
        assignments_by_scene[scene.id]
        for scene in script_content.all_scenes()
    ]
    for assignment in assignments:
        if assignment.visual_mode == "video":
            scene = scenes_by_id.get(assignment.scene_id)
            duration = scene.audio_duration_seconds if scene else 0.0
            logger.info(
                "[AI_VIDEO] selected scene %s; duration=%.1fs cap=%.1fs",
                assignment.scene_id,
                duration,
                ai_video_max_duration,
            )

    logger.info("[%s] Visual mode analysis complete: %d full_frame, %d video",
                script_id or "no-id",
                sum(1 for a in assignments if a.visual_mode != "video"),
                sum(1 for a in assignments if a.visual_mode == "video"))

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

            mode = _canonical_visual_mode(assignment.visual_mode)
            scene.set_visual_mode(mode)
            if mode not in {"popup_sequence", "flipflop", "comparison_board", "stat_card", "dossier"}:
                scene.visual_layers = []

            scene.original_visual_prompt = ""

            if mode == "video" and script_content.format_id == "life-as-a":
                from pipeline.formats.life_as_a import enforce_life_as_a_ai_video_solo_subject

                enforce_life_as_a_ai_video_solo_subject(scene)
