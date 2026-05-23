"""Static-canvas visual treatment analysis and assignment helpers."""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel, Field

from models.script import ScriptContent, Scene, VISUAL_TREATMENTS, VisualLayer, VisualTreatment
from pipeline.render_jobs import UserFacingJobError

logger = logging.getLogger(__name__)

VIDEO_OR_PHOTO_SOURCES = {"ai_video", "gameplay_video", "stock_photo", "user_upload"}
LIST_MARKERS = {
    "first",
    "second",
    "third",
    "fourth",
    "one",
    "two",
    "three",
    "four",
    "1",
    "2",
    "3",
    "4",
}
CONTRAST_MARKERS = {
    "but",
    "however",
    "whereas",
    "versus",
    "vs",
    "before",
    "after",
    "then",
    "instead",
    "while",
}
TWO_STATE_PHRASES = (
    "at first",
    "first the",
    "first it",
    "on one side",
    "on the other",
    "two states",
    "switches between",
)
REPETITION_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "but",
    "for",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
}


class VisualTreatmentAssignment(BaseModel):
    scene_id: str
    visual_treatment: str
    reasoning: str = ""
    visual_layers: list[VisualLayer] = Field(default_factory=list)


def missing_visual_treatment_voiceover_scene_ids(content: ScriptContent) -> tuple[list[str], list[str]]:
    """Return non-title scene IDs missing audio duration and word-level timing."""

    missing_audio: list[str] = []
    missing_words: list[str] = []
    for scene in content.all_scenes():
        if scene.is_title_card:
            continue
        if scene.audio_duration_seconds <= 0:
            missing_audio.append(scene.id)
        if not scene.word_timestamps:
            missing_words.append(scene.id)
    return missing_audio, missing_words


def visual_treatment_voiceover_required_message(audio_count: int, word_count: int) -> str:
    return (
        "Generate voiceover first so visual treatments can sync to words. "
        f"{audio_count} scene(s) are missing audio duration and "
        f"{word_count} scene(s) are missing word timing."
    )


def require_visual_treatment_voiceover(content: ScriptContent) -> None:
    missing_audio, missing_words = missing_visual_treatment_voiceover_scene_ids(content)
    if not missing_audio and not missing_words:
        return

    scene_ids = sorted(set(missing_audio) | set(missing_words))
    logger.info(
        "[VISUAL_TREATMENT] blocked; missing_audio=%d missing_word_timing=%d scene_ids=%s",
        len(missing_audio),
        len(missing_words),
        scene_ids,
    )
    raise UserFacingJobError(
        visual_treatment_voiceover_required_message(len(missing_audio), len(missing_words))
    )


def analyze_visual_treatments(
    content: ScriptContent,
    *,
    script_id: str,
) -> list[VisualTreatmentAssignment]:
    require_visual_treatment_voiceover(content)
    scenes = content.all_scenes()
    logger.info(
        "[VISUAL_TREATMENT] analysis requested; script=%s scenes=%d format=%s",
        script_id,
        len(scenes),
        content.format_id,
    )

    assignments: list[VisualTreatmentAssignment] = []
    for scene in scenes:
        assignment = _analyze_scene(scene)
        logger.info(
            "[VISUAL_TREATMENT] scene=%s treatment=%s layers=%d reason=%s",
            scene.id,
            assignment.visual_treatment,
            len(assignment.visual_layers),
            assignment.reasoning,
        )
        assignments.append(assignment)
    return assignments


def apply_visual_treatment_assignments(
    content: ScriptContent,
    assignments: list[VisualTreatmentAssignment],
) -> None:
    scenes_by_id = {scene.id: scene for scene in content.all_scenes()}
    for assignment in assignments:
        scene = scenes_by_id.get(assignment.scene_id)
        if scene is None:
            continue
        treatment = _normalize_treatment(assignment.visual_treatment)
        scene.visual_treatment = treatment
        scene.visual_layers = [] if treatment == "full_frame" else list(assignment.visual_layers)


def _analyze_scene(scene: Scene) -> VisualTreatmentAssignment:
    if scene.is_title_card:
        return _full_frame_assignment(scene.id, "Title-card scenes keep their existing full-frame treatment.")
    if _is_video_or_photo_backed(scene):
        return _full_frame_assignment(scene.id, "Video or photo-backed scenes keep their source media full-frame.")

    list_words = _matching_words(scene, LIST_MARKERS)
    if len(list_words) >= 2:
        layer_count = min(len(list_words), 4)
        layers = _popup_layers(scene, list_words[:layer_count])
        return VisualTreatmentAssignment(
            scene_id=scene.id,
            visual_treatment="popup_sequence",
            reasoning=f"Detected {layer_count} list markers in narration.",
            visual_layers=layers,
        )

    contrast_words = _matching_words(scene, CONTRAST_MARKERS)
    if (
        contrast_words
        or _has_repeated_content_word(scene)
        or any(phrase in scene.narration.lower() for phrase in TWO_STATE_PHRASES)
    ):
        return VisualTreatmentAssignment(
            scene_id=scene.id,
            visual_treatment="flipflop",
            reasoning="Detected contrast, repetition, or two-state narration.",
            visual_layers=_flipflop_layers(scene),
        )

    return _full_frame_assignment(scene.id, "No list or contrast pattern detected.")


def _full_frame_assignment(scene_id: str, reasoning: str) -> VisualTreatmentAssignment:
    return VisualTreatmentAssignment(
        scene_id=scene_id,
        visual_treatment="full_frame",
        reasoning=reasoning,
        visual_layers=[],
    )


def _is_video_or_photo_backed(scene: Scene) -> bool:
    return (
        scene.media_source in VIDEO_OR_PHOTO_SOURCES
        or bool(scene.video_url)
        or bool(scene.upload_url)
    )


def _normalize_treatment(value: str) -> VisualTreatment:
    if value in VISUAL_TREATMENTS:
        return value  # type: ignore[return-value]
    return "full_frame"


def _popup_layers(scene: Scene, matched_words: list[tuple[str, float]]) -> list[VisualLayer]:
    placements_by_count = {
        2: ["left", "right"],
        3: ["left", "center", "right"],
        4: ["top-left", "top-right", "bottom-left", "bottom-right"],
    }
    placements = placements_by_count.get(len(matched_words), placements_by_count[2])
    fallback_step = max(scene.audio_duration_seconds / max(len(matched_words), 1), 0.5)
    layers: list[VisualLayer] = []
    for index, (marker, enter_at) in enumerate(matched_words):
        fallback_enter_at = round(index * fallback_step, 2)
        layers.append(
            VisualLayer(
                id=f"{scene.id}_popup_{index + 1}",
                prompt=_panel_prompt(scene, marker),
                placement=placements[index],
                enter_at_seconds=round(enter_at if enter_at >= 0 else fallback_enter_at, 2),
                animation="pop_in",
            )
        )
    return layers


def _flipflop_layers(scene: Scene) -> list[VisualLayer]:
    return [
        VisualLayer(
            id=f"{scene.id}_state_a",
            prompt=_panel_prompt(scene, "state A"),
            placement="center",
            enter_at_seconds=0.0,
            animation="pop_in",
        ),
        VisualLayer(
            id=f"{scene.id}_state_b",
            prompt=_panel_prompt(scene, "state B"),
            placement="center",
            enter_at_seconds=0.5,
            animation="pop_in",
        ),
    ]


def _panel_prompt(scene: Scene, focus: str) -> str:
    base_prompt = scene.visual_prompt.strip() or scene.narration.strip()
    return (
        f"small framed Headless Hero cartoon panel for {focus}: {base_prompt}. "
        "The panel sits on a flat static color background, not a full video background. "
        "No text in image."
    )


def _matching_words(scene: Scene, markers: set[str]) -> list[tuple[str, float]]:
    matches: list[tuple[str, float]] = []
    for word in scene.word_timestamps or []:
        normalized = _normalize_word(word.word)
        if normalized in markers:
            matches.append((normalized, word.start_ms / 1000))
    return matches


def _has_repeated_content_word(scene: Scene) -> bool:
    seen: set[str] = set()
    for word in scene.word_timestamps or []:
        normalized = _normalize_word(word.word)
        if len(normalized) < 4 or normalized in REPETITION_STOPWORDS:
            continue
        if normalized in seen:
            return True
        seen.add(normalized)
    return False


def _normalize_word(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())
