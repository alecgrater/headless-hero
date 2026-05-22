"""life-as-a format — literary second-person level-by-level walk-through."""

from __future__ import annotations

import logging
import re

from models.script import LevelMeta, Scene, ScriptContent, Segment
from prompts import (
    LIFE_AS_A_IDEATION_SYSTEM,
    LIFE_AS_A_LEVEL_SCENES_INSTRUCTIONS,
    LIFE_AS_A_OUTLINE_INSTRUCTIONS,
    LIFE_AS_A_SCRIPT_SYSTEM,
)

from . import _register
from .base import VideoFormat, VisualBeatRules
from .title_cards.cinematic_chapters import CINEMATIC_CHAPTERS

logger = logging.getLogger(__name__)

_ELI_PREFIX_RE = re.compile(r"^Eli, the recurring character, is the main subject\b", re.IGNORECASE)
_ROLE_PREFIX_RE = re.compile(r"^your life as an?\s+", re.IGNORECASE)
_SHOT_PREFIX_RE = re.compile(r"^(\[[A-Z\-]+\]\s*)(.*)$")

_HUMAN_SUBJECT_TERMS = {
    "person",
    "people",
    "human",
    "figure",
    "character",
    "worker",
    "employee",
    "guard",
    "officer",
    "prisoner",
    "inmate",
    "soldier",
    "teacher",
    "nurse",
    "doctor",
    "driver",
    "cashier",
    "chef",
    "parent",
    "student",
    "artist",
    "player",
    "gambler",
    "manager",
    "detective",
    "pilot",
    "farmer",
    "mechanic",
    "engineer",
}


LIFE_AS_A_BEAT_RULES = VisualBeatRules(
    allowed_beats=frozenset({"static", "continuous", "quick_cuts"}),
    target_distribution={
        "static": (0.45, 0.60),
        "continuous": (0.25, 0.35),
        "quick_cuts": (0.15, 0.25),
    },
    max_consecutive_same_beat=2,
    monotony_threshold=3,
)


def life_as_a_role(content: ScriptContent) -> str:
    role = _ROLE_PREFIX_RE.sub("", content.title.strip()).strip(" .,:;!?")
    return role or "the protagonist"


def _role_terms(role: str) -> set[str]:
    terms = {role.lower()} if role else set()
    words = [word for word in re.split(r"[^a-zA-Z]+", role.lower()) if len(word) > 2]
    if words:
        terms.add(words[-1])
    return terms


def _contains_any_term(text: str, terms: set[str]) -> bool:
    lowered = text.lower()
    return any(re.search(rf"\b{re.escape(term)}\b", lowered) for term in terms if term)


def _scene_text(scene: Scene) -> str:
    pieces = [scene.visual_prompt, scene.narration]
    pieces.extend(frame.prompt for frame in scene.frame_directives or [])
    return "\n".join(piece for piece in pieces if piece)


def is_life_as_a_eli_scene(scene: Scene, role: str = "") -> bool:
    """Return True when a life-as-a scene should depict Eli as the protagonist."""
    if scene.is_title_card:
        return False
    text = _scene_text(scene)
    if _ELI_PREFIX_RE.search(text) or re.search(r"\bEli\b", text):
        return True
    terms = _HUMAN_SUBJECT_TERMS | _role_terms(role)
    return scene.contains_person or _contains_any_term(text, terms)


def _eli_scene_prompt(prompt: str, role: str) -> str:
    stripped = prompt.strip()
    if not stripped or _ELI_PREFIX_RE.match(stripped) or re.search(r"\bEli\b", stripped):
        return prompt
    role_phrase = role if role != "the protagonist" else "the protagonist"
    eli_instruction = (
        "Eli, the recurring character, is the main subject and protagonist in this scene. "
        f"Depict Eli as {role_phrase}; any other people are secondary and visually distinct from Eli."
    )
    shot_match = _SHOT_PREFIX_RE.match(stripped)
    if not shot_match:
        return f"{eli_instruction} {stripped}"
    shot_tag, rest = shot_match.groups()
    return f"{shot_tag}{eli_instruction} {rest}".strip()


def _mark_eli_protagonist_scenes(content: ScriptContent) -> int:
    role = life_as_a_role(content)
    updated = 0
    for scene in content.all_scenes():
        if not is_life_as_a_eli_scene(scene, role):
            continue
        original_prompt = scene.visual_prompt
        scene.visual_prompt = _eli_scene_prompt(scene.visual_prompt, role)
        scene.contains_person = True
        if scene.visual_prompt != original_prompt:
            updated += 1

        for frame in scene.frame_directives or []:
            if frame.source != "ai_generated":
                continue
            frame_prompt = frame.prompt
            new_prompt = _eli_scene_prompt(frame_prompt, role)
            if new_prompt != frame_prompt:
                frame.prompt = new_prompt
                updated += 1
            frame.contains_person = True

    if updated:
        logger.info("life-as-a: marked %d visual prompt(s) as Eli-protagonist scenes", updated)
    return updated


def enforce_life_as_a_constraints(content: ScriptContent) -> ScriptContent:
    """Post-process a life-as-a script.

    - Coerce disallowed visual_beat values ('aha_subtitle', 'montage') back to 'static'.
    - Ensure each segment has a chapter-card scene at index 0 (is_title_card=True).
    - Synthesize content.levels[] from segments if Claude omitted it (defensive).
    - Mark visible protagonist scenes so Eli is the main subject and character reference is used.
    """
    allowed = LIFE_AS_A_BEAT_RULES.allowed_beats
    coerced = 0
    for scene in content.all_scenes():
        if scene.visual_beat not in allowed and not scene.is_title_card:
            scene.visual_beat = "static"
            coerced += 1
    if coerced:
        logger.info("life-as-a: coerced %d disallowed visual_beat values to 'static'", coerced)

    # Ensure chapter-card scene at start of each segment
    for seg_idx, segment in enumerate(content.segments):
        if not segment.scenes or not segment.scenes[0].is_title_card:
            level_num = seg_idx + 1
            level = (
                content.levels[seg_idx]
                if content.levels and seg_idx < len(content.levels)
                else None
            )
            descriptor = level.descriptor if level else segment.name
            # Prefer levels[].image_prompt (populated by segmented assembly) over
            # segment.title_card_image_prompt (which the segmented outline does not set).
            image_prompt = (
                (level.image_prompt if level and level.image_prompt else None)
                or (content.cinematic_thumbnail_prompt if level_num == 1 else None)
                or segment.title_card_image_prompt
                or descriptor
            )
            chapter_scene = Scene(
                id=f"chapter_{level_num:02d}",
                narration=f"Level {level_num}, the {descriptor.lower()}.",
                visual_prompt=f"[ESTABLISHING] {image_prompt}",
                duration_estimate_seconds=4.0,
                is_title_card=True,
                visual_beat="static",
            )
            segment.scenes.insert(0, chapter_scene)
            logger.info("life-as-a: inserted chapter card for level %d", level_num)

    # Synthesize levels[] if missing
    if not content.levels:
        content.levels = [
            LevelMeta(
                number=i + 1,
                descriptor=seg.short_name or seg.name,
                image_prompt=seg.title_card_image_prompt,
            )
            for i, seg in enumerate(content.segments)
        ]
        logger.info("life-as-a: synthesized levels[] from segments")

    _mark_eli_protagonist_scenes(content)

    return content


LIFE_AS_A = _register(VideoFormat(
    id="life-as-a",
    display_name="Your Life As A...",
    short_description='A walk through the stages of being something — literary, 4–7 levels, second-person.',
    level_count=(4, 7),
    level_label="level",
    ideation_prompt=LIFE_AS_A_IDEATION_SYSTEM,
    script_system_prompt=LIFE_AS_A_SCRIPT_SYSTEM,
    outline_prompt=LIFE_AS_A_OUTLINE_INSTRUCTIONS,
    segment_scenes_prompt=LIFE_AS_A_LEVEL_SCENES_INSTRUCTIONS,
    supports_cold_open=False,
    supports_hook_scoring=False,
    supports_segmented_generation=True,
    title_card_strategy=CINEMATIC_CHAPTERS,
    visual_beat_rules=LIFE_AS_A_BEAT_RULES,
    enforce_post_processing=enforce_life_as_a_constraints,
))
