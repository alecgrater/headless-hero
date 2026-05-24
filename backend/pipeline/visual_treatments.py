"""Static-canvas animation type analysis and assignment helpers.

The persisted scene field is still named ``visual_treatment`` for backward
compatibility with existing script JSON and Remotion props.
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel, Field

from models.script import ScriptContent, Scene, VISUAL_TREATMENTS, VisualLayer, VisualTreatment
from pipeline.render_jobs import UserFacingJobError

logger = logging.getLogger(__name__)

VIDEO_OR_PHOTO_SOURCES = {"ai_video"}
LIST_MARKERS = {
    "first",
    "second",
    "third",
    "fourth",
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
TWO_STATE_MARKERS = {"again"}
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
        "Generate voiceover first so animation types can sync to words. "
        f"{audio_count} scene(s) are missing audio duration and "
        f"{word_count} scene(s) are missing word timing."
    )


def require_visual_treatment_voiceover(content: ScriptContent) -> None:
    missing_audio, missing_words = missing_visual_treatment_voiceover_scene_ids(content)
    if not missing_audio and not missing_words:
        return

    scene_ids = sorted(set(missing_audio) | set(missing_words))
    logger.info(
        "[ANIMATION_TYPE] blocked; missing_audio=%d missing_word_timing=%d scene_ids=%s",
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
        "[ANIMATION_TYPE] analysis requested; script=%s scenes=%d format=%s",
        script_id,
        len(scenes),
        content.format_id,
    )

    assignments: list[VisualTreatmentAssignment] = []
    for scene in scenes:
        assignment = _analyze_scene(scene)
        logger.info(
            "[ANIMATION_TYPE] scene=%s animation_type=%s layers=%d reason=%s",
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

    marker_list_items = _matching_words(scene, LIST_MARKERS)
    if len(marker_list_items) >= 2:
        layer_count = min(len(marker_list_items), 4)
        layers = _popup_layers(scene, marker_list_items[:layer_count])
        return VisualTreatmentAssignment(
            scene_id=scene.id,
            visual_treatment="popup_sequence",
            reasoning=f"Detected {layer_count} list markers in narration.",
            visual_layers=layers,
        )

    contrast_words = _matching_words(scene, CONTRAST_MARKERS)
    two_state_words = _matching_words(scene, TWO_STATE_MARKERS)
    state_b_enter_at = _state_b_enter_at(scene, [*contrast_words, *two_state_words])
    if (
        contrast_words
        or _has_repeated_content_word(scene)
        or two_state_words
        or any(phrase in scene.narration.lower() for phrase in TWO_STATE_PHRASES)
    ):
        return VisualTreatmentAssignment(
            scene_id=scene.id,
            visual_treatment="flipflop",
            reasoning="Detected contrast, repetition, or two-state narration.",
            visual_layers=_flipflop_layers(scene, state_b_enter_at),
        )

    natural_list_items = _natural_list_items(scene)
    if len(natural_list_items) >= 2:
        layer_count = min(len(natural_list_items), 4)
        layers = _popup_layers(scene, natural_list_items[:layer_count])
        return VisualTreatmentAssignment(
            scene_id=scene.id,
            visual_treatment="popup_sequence",
            reasoning=f"Detected {layer_count} list items in narration.",
            visual_layers=layers,
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
    )


def _normalize_treatment(value: str) -> VisualTreatment:
    if value in VISUAL_TREATMENTS:
        return value  # type: ignore[return-value]
    return "full_frame"


def _popup_layers(scene: Scene, list_items: list[tuple[str, float]]) -> list[VisualLayer]:
    placements_by_count = {
        2: ["left", "right"],
        3: ["left", "center", "right"],
        4: ["top-left", "top-right", "bottom-left", "bottom-right"],
    }
    placements = placements_by_count.get(len(list_items), placements_by_count[2])
    fallback_step = max(scene.audio_duration_seconds / max(len(list_items), 1), 0.5)
    layers: list[VisualLayer] = []
    for index, (item, enter_at) in enumerate(list_items):
        fallback_enter_at = round(index * fallback_step, 2)
        layers.append(
            VisualLayer(
                id=f"{scene.id}_popup_{index + 1}",
                prompt=_panel_prompt(scene, item),
                placement=placements[index],
                enter_at_seconds=round(enter_at if enter_at >= 0 else fallback_enter_at, 2),
                animation="pop_in",
            )
        )
    return layers


def _flipflop_layers(scene: Scene, state_b_enter_at: float) -> list[VisualLayer]:
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
            enter_at_seconds=round(state_b_enter_at, 2),
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


def _state_b_enter_at(scene: Scene, cue_words: list[tuple[str, float]]) -> float:
    if cue_words:
        return cue_words[0][1]
    midpoint = scene.audio_duration_seconds / 2 if scene.audio_duration_seconds > 0 else 0.5
    return max(midpoint, 0.5)


def _natural_list_items(scene: Scene) -> list[tuple[str, float]]:
    text = scene.narration.strip()
    if not text:
        return []

    normalized_text = re.sub(r"\s+", " ", text)
    pieces = [
        piece.strip(" .,:;-")
        for piece in re.split(r"\s*;\s*|\s*,\s*|\s+\b(?:and|or)\b\s+", normalized_text, flags=re.IGNORECASE)
    ]
    items = [piece for piece in pieces if _is_list_item_phrase(piece)]
    if not 2 <= len(items) <= 6:
        return []

    return [(item, _phrase_start_seconds(scene, item, index, len(items))) for index, item in enumerate(items[:4])]


def _is_list_item_phrase(value: str) -> bool:
    words = [_normalize_word(word) for word in value.split()]
    content_words = [word for word in words if word and word not in REPETITION_STOPWORDS]
    return bool(content_words)


def _phrase_start_seconds(scene: Scene, phrase: str, index: int, total: int) -> float:
    phrase_words = [_normalize_word(word) for word in phrase.split()]
    first_content_word = next(
        (word for word in phrase_words if word and word not in REPETITION_STOPWORDS),
        phrase_words[0] if phrase_words else "",
    )
    if first_content_word:
        for word in scene.word_timestamps or []:
            if _normalize_word(word.word) == first_content_word:
                return word.start_ms / 1000

    fallback_step = max(scene.audio_duration_seconds / max(total, 1), 0.5)
    return index * fallback_step


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
