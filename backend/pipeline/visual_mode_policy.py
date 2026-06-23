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


@dataclass(frozen=True)
class VisualModeOpportunityPolicy:
    visual_mode: str
    purpose: str
    frequency_guidance: str
    opportunity_cues: tuple[str, ...]
    avoid_when: tuple[str, ...]


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
    "captions": VisualModeDurationTarget(
        visual_mode="captions",
        profile="normal",
        min_seconds=5.0,
        target_seconds=8.0,
        max_seconds=14.0,
        ui_label="Normal target · 5-9s",
        prompt_guidance="Use about 5-9 seconds for a short editorial punch phrase from narration.",
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
PRODUCTION_OPPORTUNITY_MODES: tuple[str, ...] = CANONICAL_VISUAL_MODES

_OPPORTUNITY_POLICIES: dict[str, VisualModeOpportunityPolicy] = {
    "full_frame": VisualModeOpportunityPolicy(
        visual_mode="full_frame",
        purpose="Default full-bleed image for one clear lived moment, object, atmosphere, character beat, or metaphor.",
        frequency_guidance="Dominant fallback; most scenes may remain full_frame when no specialized mode clearly improves the beat.",
        opportunity_cues=("single location or object", "quiet character moment", "atmosphere", "simple metaphor"),
        avoid_when=(
            "multiple distinct examples are needed",
            "same-scene progression is central",
            "renderer-owned text or board structure is the point",
        ),
    ),
    "multi_frame": VisualModeOpportunityPolicy(
        visual_mode="multi_frame",
        purpose="Several independent generated frames inside one narration scene.",
        frequency_guidance="Common variety mode when narration naturally contains multiple examples, routines, or sensory cuts.",
        opportunity_cues=("multiple examples", "repeated routines", "fast context shifts", "several memories"),
        avoid_when=(
            "one coherent progression should stay continuous",
            "one strong image is clearer",
            "cutouts or renderer-owned typography are required",
        ),
    ),
    "continuous": VisualModeOpportunityPolicy(
        visual_mode="continuous",
        purpose="Same-scene progression where one subject, action, or environment changes over time.",
        frequency_guidance="Common variety mode for physical progression, time passage, and transformations.",
        opportunity_cues=(
            "time passes in one place",
            "object changes state",
            "person repeats an action",
            "environment gradually shifts",
        ),
        avoid_when=("frames are unrelated examples", "the scene is only a static realization", "side-by-side comparison is clearer"),
    ),
    "captions": VisualModeOpportunityPolicy(
        visual_mode="captions",
        purpose="Renderer-owned editorial text beat for a realization, reversal, label, or key claim.",
        frequency_guidance="Common expressive rhythm opportunity in long scripts; plan several when exact narration phrases deserve large in-scene text.",
        opportunity_cues=("quotable realization", "short emotional label", "turning-point sentence", "clear reversal", "key claim"),
        avoid_when=("caption text would need paraphrasing", "ordinary subtitles are enough", "the scene is too short for context"),
    ),
    "popup_sequence": VisualModeOpportunityPolicy(
        visual_mode="popup_sequence",
        purpose="Anchor subject with concrete item/tool/document/object cutouts appearing around it.",
        frequency_guidance="Low-count and meaning-driven; actively scan for concrete item clusters before accepting zero.",
        opportunity_cues=("small set of tools", "documents", "possessions", "symptoms", "ingredients", "objects around a person"),
        avoid_when=("items are abstract", "the list is too long", "a multi-frame montage communicates better"),
    ),
    "comparison_board": VisualModeOpportunityPolicy(
        visual_mode="comparison_board",
        purpose="Renderer-owned two- or three-way comparison with cutout subjects and board layout.",
        frequency_guidance="Low-count and meaning-driven; actively scan for true comparisons before accepting zero.",
        opportunity_cues=("before vs after", "then vs now", "choice vs consequence", "two roles", "two outcomes"),
        avoid_when=("only one environment or event matters", "same-subject micro-animation is enough", "process progression is clearer"),
    ),
    "stat_card": VisualModeOpportunityPolicy(
        visual_mode="stat_card",
        purpose="One decisive number rendered as dominant typography.",
        frequency_guidance="Low-count and capped; actively scan for decisive numbers before accepting zero, but use only 1-2 in most videos.",
        opportunity_cues=("money amount", "percentage", "duration", "ranking", "odds", "population count"),
        avoid_when=("multiple numbers compete", "setting or character emotion matters more", "the number is incidental"),
    ),
    "video": VisualModeOpportunityPolicy(
        visual_mode="video",
        purpose="Planned AI-video scene when motion clearly improves the beat before timing validation.",
        frequency_guidance="Timing-sensitive planned mode; do not let it crowd out stronger renderer-owned opportunities.",
        opportunity_cues=("meaningful motion", "gesture", "physical transformation", "environmental movement", "reveal"),
        avoid_when=("static text or board is required", "title card", "captions scene", "motion does not add clarity"),
    ),
}

_missing_opportunity_policies = VISUAL_MODES - set(_OPPORTUNITY_POLICIES)
_unknown_opportunity_policies = set(_OPPORTUNITY_POLICIES) - VISUAL_MODES
if _missing_opportunity_policies or _unknown_opportunity_policies:
    raise RuntimeError(
        "Visual mode opportunity policies must exactly match models.script.VISUAL_MODES: "
        f"missing={sorted(_missing_opportunity_policies)}, unknown={sorted(_unknown_opportunity_policies)}"
    )


def duration_target_for_mode(visual_mode: str | None) -> VisualModeDurationTarget:
    return _TARGETS.get(visual_mode or "", _TARGETS["full_frame"])


def opportunity_policy_for_mode(visual_mode: str | None) -> VisualModeOpportunityPolicy:
    return _OPPORTUNITY_POLICIES.get(visual_mode or "", _OPPORTUNITY_POLICIES["full_frame"])


def duration_profile_for_mode(visual_mode: str | None) -> str:
    return duration_target_for_mode(visual_mode).profile


def max_scene_seconds_for_mode(visual_mode: str | None) -> float:
    return duration_target_for_mode(visual_mode).max_seconds


def target_scene_seconds_for_mode(visual_mode: str | None) -> float:
    return duration_target_for_mode(visual_mode).target_seconds


def prompt_duration_guidance() -> str:
    lines = [
        "Scene duration is driven by visual_mode, not script type, and is planned before voiceover.",
        "Use full_frame, multi_frame, and continuous as normal short scenes around 5-9 seconds.",
        "Use captions as normal short scenes around 5-9 seconds for a short editorial punch phrase.",
        "Use comparison_board around 16-24 seconds so viewers can compare the columns.",
        "Use popup_sequence around 14-20 seconds so item layers can appear clearly.",
        "Use stat_card around 10-14 seconds unless it is a very fast numerical punch.",
        "Plan video scenes before voiceover when motion clearly improves the beat; later validation may downgrade unsafe video choices.",
    ]
    return "\n".join(f"- {line}" for line in lines)


def prompt_visual_opportunity_guidance(projected_scene_count: int | None = None) -> str:
    scene_hint = (
        f"For a projected script of about {projected_scene_count} scenes, "
        if projected_scene_count and projected_scene_count > 0
        else "For the projected script, "
    )
    lines = [
        "Visual opportunity planning is script-type agnostic and happens before final scenes are written.",
        "Scene boundaries, narration length, duration estimates, and mode-specific fields must be shaped together.",
        f"{scene_hint}full_frame remains dominant. Do not force a quota or distort narration for visual variety.",
        (
            "Use soft candidate discovery expectations during outline planning: these are not final scene quotas, "
            "but long scripts should not silently accept zero candidates for renderer-owned modes."
        ),
        (
            "For long scripts, captions: usually find at least 2 exact-phrase editorial candidates; "
            "popup_sequence: usually find at least 2 concrete item/object cluster candidates; "
            "comparison_board: usually find at least 2 true contrast candidates; "
            "stat_card: usually find 1-2 decisive-number candidates."
        ),
        (
            "If the outline falls below those soft expectations, add visual_opportunity_coverage explaining "
            "which modes were genuinely unsupported by the topic instead of omitting them silently."
        ),
        "Treat captions as a common expressive rhythm opportunity in long scripts when the narration supports it.",
        "Keep popup_sequence, comparison_board, and stat_card low-count and meaning-driven, but actively scan for them before accepting zero.",
        "Post-generation checks may validate or downgrade invalid modes, but must not redistribute modes into already-cut short scenes.",
    ]
    for mode in PRODUCTION_OPPORTUNITY_MODES:
        policy = opportunity_policy_for_mode(mode)
        cues = ", ".join(policy.opportunity_cues[:4])
        avoids = ", ".join(policy.avoid_when[:2])
        lines.append(f"{mode}: {policy.frequency_guidance} Cues: {cues}. Avoid when: {avoids}.")
    return "\n".join(f"- {line}" for line in lines)


def prompt_visual_opportunity_schema_guidance() -> str:
    return """\
Add a compact "visual_opportunities" array to every outline segment. Do not include scenes or narration body.
Also add a top-level "visual_opportunity_coverage" object that summarizes candidate discovery across the whole outline; explain any mode that falls below the soft candidate expectation.
Each opportunity object must use this shape:
{
  "mode": "captions|multi_frame|continuous|popup_sequence|comparison_board|stat_card|video|full_frame",
  "beat": "Short natural-language description of the future scene beat.",
  "why": "Why this mode strengthens the beat without hurting script quality.",
  "duration_profile": "normal|medium|extended|planned",
  "priority": "strong|possible"
}
The coverage object should use this shape:
{
  "captions": "Found 2+ candidates, or explain why fewer exact-phrase editorial beats fit.",
  "popup_sequence": "Found 2+ candidates, or explain why fewer concrete item/object clusters fit.",
  "comparison_board": "Found 2+ candidates, or explain why fewer true comparisons fit.",
  "stat_card": "Found 1-2 candidates, or explain why no decisive number fits."
}
Use opportunities as planning notes only. They guide future scene boundaries; they are not final scene JSON.
"""
