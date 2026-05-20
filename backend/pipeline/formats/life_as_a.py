"""life-as-a format — literary second-person level-by-level walk-through."""

from __future__ import annotations

import logging

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


LIFE_AS_A_BEAT_RULES = VisualBeatRules(
    allowed_beats=frozenset({"static", "continuous", "quick_cuts"}),
    target_distribution={
        "static": (0.80, 0.90),
        "continuous": (0.10, 0.15),
        "quick_cuts": (0.0, 0.05),
    },
    max_consecutive_same_beat=12,    # static is dominant — long runs are intended
    monotony_threshold=99,           # effectively disable run-breaking
)


def enforce_life_as_a_constraints(content: ScriptContent) -> ScriptContent:
    """Post-process a life-as-a script.

    - Coerce disallowed visual_beat values ('aha_subtitle', 'montage') back to 'static'.
    - Ensure each segment has a chapter-card scene at index 0 (is_title_card=True).
    - Synthesize content.levels[] from segments if Claude omitted it (defensive).
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
