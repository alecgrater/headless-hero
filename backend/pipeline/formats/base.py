"""Base types for the format registry."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from models.script import Scene, ScriptContent
from prompts import PromptDef


FULL_VISUAL_MODE_VOCABULARY: tuple[str, ...] = (
    "full_frame",
    "continuous",
    "multi_frame",
    "video",
    "popup_sequence",
    "blink",
    "comparison_board",
    "captions",
    "stat_card",
)


@dataclass(frozen=True)
class FormatNote:
    """One curated reference gotcha for a format, grouped by category.

    category: "Openings" | "Narration" | "Visuals" | "Title cards"
              | "Scene length" | "Short-form" | "AI video"
    """

    category: str
    text: str


@dataclass(frozen=True)
class VisualBeatRules:
    """Per-format distribution rules for visual_beat reassignment."""

    allowed_beats: frozenset[str]
    target_distribution: dict[str, tuple[float, float]] = field(default_factory=dict)
    max_consecutive_same_beat: int = 3
    monotony_threshold: int = 3  # min run length before _fix_visual_monotony intervenes


class TitleCardStrategy(Protocol):
    """Pluggable title-card / thumbnail behavior per format."""

    kind: str  # "composite-grid" | "cinematic-chapters"

    def prepare_thumbnail(
        self,
        script_id: str,
        content: ScriptContent,
        accent_color: str,
        force: bool = False,
        job_id: str | None = None,
    ) -> None:
        """Generate the YouTube thumbnail and any chapter-card images. Idempotent.

        ``job_id`` is forwarded to underlying pipelines that support cancellation
        / progress tracking (currently only the composite-grid strategy uses it).
        """

    def prepare_title_card_scene(
        self,
        scene: Scene,
        script_id: str,
        content: ScriptContent,
        brand: dict,
    ) -> Scene:
        """Resolve image_url / overlay metadata for a title-card scene at render time."""


@dataclass(frozen=True)
class VideoFormat:
    """Declarative format definition. All orchestration reads from this."""

    id: str
    display_name: str
    short_description: str

    # Structural
    level_count: int | tuple[int, int]   # 8 (fixed) | (4, 7) (range)
    level_label: str                     # "segment" | "level"

    # Prompts
    ideation_prompt: PromptDef
    script_system_prompt: PromptDef
    outline_prompt: PromptDef | None         # required if supports_segmented_generation
    segment_scenes_prompt: PromptDef | None  # required if supports_segmented_generation

    # Generation flags
    supports_cold_open: bool
    supports_hook_scoring: bool
    supports_segmented_generation: bool

    # Strategies
    title_card_strategy: TitleCardStrategy
    visual_beat_rules: VisualBeatRules

    # Post-processing — applied after Claude generation, before _fix_visual_monotony
    enforce_post_processing: Callable[..., ScriptContent]

    # Reference-only metadata (drives the Script Types settings page; not enforced)
    supported_visual_modes: tuple[str, ...] = ()
    reference_notes: tuple[FormatNote, ...] = ()
