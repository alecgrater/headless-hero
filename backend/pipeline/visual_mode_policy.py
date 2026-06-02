"""Shared duration and planning policy for scene visual modes."""

from __future__ import annotations

from dataclasses import dataclass

from models.script import VISUAL_MODES


@dataclass(frozen=True)
class VisualModeDurationTarget:
    visual_mode: str
    profile: str
    min_seconds: float
    target_seconds: float
    max_seconds: float
    ui_label: str
    prompt_guidance: str


_TARGETS: dict[str, VisualModeDurationTarget] = {
    "full_frame": VisualModeDurationTarget(
        visual_mode="full_frame",
        profile="normal",
        min_seconds=5.0,
        target_seconds=8.0,
        max_seconds=14.0,
        ui_label="Normal target · 5-9s",
        prompt_guidance="Use about 5-9 seconds of narration for one clear visual beat.",
    ),
    "continuous": VisualModeDurationTarget(
        visual_mode="continuous",
        profile="normal",
        min_seconds=5.0,
        target_seconds=8.0,
        max_seconds=14.0,
        ui_label="Normal target · 5-9s",
        prompt_guidance="Use about 5-9 seconds while one coherent progression unfolds.",
    ),
    "multi_frame": VisualModeDurationTarget(
        visual_mode="multi_frame",
        profile="normal",
        min_seconds=5.0,
        target_seconds=8.0,
        max_seconds=14.0,
        ui_label="Normal target · 5-9s",
        prompt_guidance="Use about 5-9 seconds unless several concrete examples require a little more room.",
    ),
    "flipflop": VisualModeDurationTarget(
        visual_mode="flipflop",
        profile="normal",
        min_seconds=5.0,
        target_seconds=8.0,
        max_seconds=14.0,
        ui_label="Normal target · 5-9s",
        prompt_guidance="Use about 5-9 seconds for simple same-subject A/B motion.",
    ),
    "captions": VisualModeDurationTarget(
        visual_mode="captions",
        profile="extended",
        min_seconds=12.0,
        target_seconds=16.0,
        max_seconds=20.0,
        ui_label="Extended target · 14-18s",
        prompt_guidance="Use about 14-18 seconds so the editorial text lands with enough narration context.",
    ),
    "comparison_board": VisualModeDurationTarget(
        visual_mode="comparison_board",
        profile="extended",
        min_seconds=14.0,
        target_seconds=20.0,
        max_seconds=26.0,
        ui_label="Extended target · 16-24s",
        prompt_guidance="Use about 16-24 seconds so viewers can compare two or three columns clearly.",
    ),
    "popup_sequence": VisualModeDurationTarget(
        visual_mode="popup_sequence",
        profile="extended",
        min_seconds=12.0,
        target_seconds=17.0,
        max_seconds=22.0,
        ui_label="Extended target · 14-20s",
        prompt_guidance="Use about 14-20 seconds so each popup item has time to appear and register.",
    ),
    "stat_card": VisualModeDurationTarget(
        visual_mode="stat_card",
        profile="medium",
        min_seconds=8.0,
        target_seconds=12.0,
        max_seconds=16.0,
        ui_label="Medium target · 10-14s",
        prompt_guidance="Use about 10-14 seconds unless the statistic is only a quick punch.",
    ),
    "video": VisualModeDurationTarget(
        visual_mode="video",
        profile="planned",
        min_seconds=5.0,
        target_seconds=8.0,
        max_seconds=14.0,
        ui_label="Planned video · validated after voiceover",
        prompt_guidance=(
            "Plan video before voiceover only when motion clearly improves the scene; "
            "validation may downgrade unsafe choices after timing exists."
        ),
    ),
}

_missing_targets = VISUAL_MODES - set(_TARGETS)
_unknown_targets = set(_TARGETS) - VISUAL_MODES
if _missing_targets or _unknown_targets:
    raise RuntimeError(
        "Visual mode duration targets must exactly match models.script.VISUAL_MODES: "
        f"missing={sorted(_missing_targets)}, unknown={sorted(_unknown_targets)}"
    )

CANONICAL_VISUAL_MODES: tuple[str, ...] = tuple(mode for mode in _TARGETS if mode in VISUAL_MODES)


def duration_target_for_mode(visual_mode: str | None) -> VisualModeDurationTarget:
    return _TARGETS.get(visual_mode or "", _TARGETS["full_frame"])


def duration_profile_for_mode(visual_mode: str | None) -> str:
    return duration_target_for_mode(visual_mode).profile


def max_scene_seconds_for_mode(visual_mode: str | None) -> float:
    return duration_target_for_mode(visual_mode).max_seconds


def target_scene_seconds_for_mode(visual_mode: str | None) -> float:
    return duration_target_for_mode(visual_mode).target_seconds


def prompt_duration_guidance() -> str:
    lines = [
        "Scene duration is driven by visual_mode, not script type, and is planned before voiceover.",
        "Use full_frame, multi_frame, continuous, and flipflop as normal short scenes around 5-9 seconds.",
        "Use captions around 14-18 seconds so the editorial text has context.",
        "Use comparison_board around 16-24 seconds so viewers can compare the columns.",
        "Use popup_sequence around 14-20 seconds so item layers can appear clearly.",
        "Use stat_card around 10-14 seconds unless it is a very fast numerical punch.",
        "Plan video scenes before voiceover when motion clearly improves the beat; later validation may downgrade unsafe video choices.",
    ]
    return "\n".join(f"- {line}" for line in lines)
