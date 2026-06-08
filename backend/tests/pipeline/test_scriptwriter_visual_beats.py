"""Tests for scriptwriter visual beat post-processing."""

import sys
from pathlib import Path
import re

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from models.script import Scene, ScriptContent, Segment
from pipeline.formats.base import VisualBeatRules
from pipeline.formats.life_as_a import LIFE_AS_A_BEAT_RULES
from pipeline.scriptwriter import (
    _audit_visual_mode_metadata,
    _ensure_scene_granularity,
    _ensure_visual_beat_directives,
    _fix_visual_monotony,
    _scene_granularity_duration,
    _validate_flipflop_actions,
)
from prompts import script as script_prompt
from prompts.script import SCRIPT_SYSTEM as SCRIPT_SYSTEM_PROMPT


def _static_scene(scene_id: str) -> Scene:
    return Scene(
        id=scene_id,
        narration="You wait through another identical hour.",
        visual_prompt="[ESTABLISHING] A quiet institutional hallway under flat lights.",
        visual_beat="static",
        frame_directives=[
            {
                "prompt": "[ESTABLISHING] A quiet institutional hallway under flat lights.",
                "source": "ai_generated",
                "transition": "cut",
                "reference_previous": False,
                "search_query": "",
                "contains_person": False,
            }
        ],
    )


def test_life_as_a_monotony_fix_creates_multi_frame_directives():
    content = ScriptContent(
        title="Your Life As A Test",
        format_id="life-as-a",
        segments=[
            Segment(
                name="Level 1, the waiting",
                scenes=[_static_scene(f"scene_{i:03d}") for i in range(1, 7)],
            ),
        ],
    )

    fixes = _fix_visual_monotony(content, LIFE_AS_A_BEAT_RULES)

    changed = [scene for scene in content.all_scenes() if scene.visual_beat != "static"]
    assert fixes > 0
    assert changed
    assert all(len(scene.frame_directives) > 1 for scene in changed)


def test_monotony_fix_normalizes_legacy_alternatives_to_multi_frame():
    content = ScriptContent(
        title="Your Life As A Test",
        format_id="youtube-listicle",
        segments=[
            Segment(
                name="Segment 1",
                scenes=[_static_scene(f"scene_{i:03d}") for i in range(1, 5)],
            ),
        ],
    )
    rules = VisualBeatRules(
        allowed_beats=frozenset({"static", "quick_cuts", "montage"}),
        monotony_threshold=3,
    )

    _fix_visual_monotony(content, rules)

    beats = [scene.visual_beat for scene in content.all_scenes()]
    assert "quick_cuts" not in beats
    assert "montage" not in beats
    assert "multi_frame" in beats


def test_visual_monotony_fix_does_not_force_extended_modes_into_short_scenes():
    content = ScriptContent(
        title="Test",
        format_id="youtube-listicle",
        segments=[
            Segment(
                name="Segment",
                scenes=[_static_scene(f"scene_{i:03d}") for i in range(1, 8)],
            )
        ],
    )

    fixes = _fix_visual_monotony(
        content,
        VisualBeatRules(
            allowed_beats=frozenset({"static", "continuous", "multi_frame"}),
            monotony_threshold=3,
        ),
    )

    modes = [scene.visual_mode for scene in content.all_scenes()]
    assert fixes > 0
    assert {"continuous", "multi_frame"} & set(modes)
    assert "captions" not in modes
    assert "comparison_board" not in modes
    assert "popup_sequence" not in modes
    assert "stat_card" not in modes


def test_non_static_beats_without_directives_are_repaired():
    scene = _static_scene("scene_001")
    scene.visual_beat = "continuous"
    scene.frame_directives = []
    scene.duration_estimate_seconds = 10.0
    content = ScriptContent(
        title="Your Life As A Test",
        format_id="life-as-a",
        segments=[Segment(name="Level 1, the waiting", scenes=[scene])],
    )

    _ensure_visual_beat_directives(content)

    assert len(scene.frame_directives) == 3
    assert scene.frame_directives[1].reference_previous is True


def test_script_prompt_no_longer_requests_quick_cuts_or_montage():
    prompt_text = script_prompt.SCRIPT_SYSTEM.template

    assert '"quick_cuts"' not in prompt_text
    assert '"montage"' not in prompt_text
    assert '"multi_frame"' in prompt_text


def test_script_prompt_includes_captions_mode_without_extra_renderer_detail():
    prompt_text = script_prompt.SCRIPT_SYSTEM.template

    assert '"captions"' in prompt_text
    assert '"aha_subtitle" — When' not in prompt_text
    assert "Aim for 5-6 per video" not in prompt_text
    assert "caption_text" in prompt_text
    assert "caption_emphasis" in prompt_text
    assert "renderer handles" in prompt_text
    assert "Do not put readable caption text into visual_prompt" in prompt_text
    assert 'set "visual_prompt" to an empty string' in prompt_text


def test_script_prompt_includes_popup_sequence_mode():
    prompt_text = script_prompt.SCRIPT_SYSTEM.template

    assert '"popup_sequence"' in prompt_text
    assert "concrete items" in prompt_text
    assert "pop around" in prompt_text


def test_script_prompt_defines_flipflop_as_cutout_body_language_not_contrast():
    prompt_text = script_prompt.SCRIPT_SYSTEM.template

    assert '"flipflop"' in prompt_text
    assert "cropped-subject" in prompt_text
    assert "Human/character-only" in prompt_text
    assert "face micro-animation" in prompt_text
    assert "Do not use flipflop for object-only scenes" in prompt_text


def test_script_prompt_requires_flipflop_action_allowlist():
    prompt_text = SCRIPT_SYSTEM_PROMPT.template

    assert "flipflop_action" in prompt_text
    assert "blink, speaking_mouth, eye_glance, eyebrow_raise" in prompt_text
    assert "Do not choose pose-changing or body-action values" in prompt_text
    assert "If no allowed face micro-action naturally fits, choose another visual_mode" in prompt_text


def test_script_prompt_includes_comparison_board_mode():
    prompt_text = script_prompt.SCRIPT_SYSTEM.template

    assert '"comparison_board"' in prompt_text
    assert "side-by-side renderer-controlled comparison" in prompt_text
    assert "Before vs After" in prompt_text


def test_script_prompt_routes_modes_by_best_fit_not_forced_quotas():
    prompt_text = script_prompt.SCRIPT_SYSTEM.template

    assert "BEST-FIT ROUTING RULES" in prompt_text
    assert "single best visual mode" in prompt_text
    assert "full_frame remains the fallback" in prompt_text
    assert "50-65%" not in prompt_text
    assert "full-full-variety" not in prompt_text
    assert "MUST use a different mode" not in prompt_text


def test_script_prompt_treats_captions_as_short_editorial_punches():
    prompt_text = script_prompt.SCRIPT_SYSTEM.template

    assert "captions" in prompt_text
    assert "short editorial punch" in prompt_text
    assert "Captions can use normal short-scene timing" in prompt_text
    assert "captions ~14-18s" not in prompt_text


def test_outline_prompt_caption_opportunities_use_normal_duration_profile():
    for prompt_text in (
        script_prompt.SCRIPT_OUTLINE_INSTRUCTIONS.template,
        script_prompt.LIFE_AS_A_OUTLINE_INSTRUCTIONS.template,
    ):
        assert not re.search(
            r'"mode": "captions"[\s\S]{0,240}"duration_profile": "extended"',
            prompt_text,
        )


def test_outline_prompts_request_visual_opportunities_before_scenes():
    standard_prompt = script_prompt.SCRIPT_OUTLINE_INSTRUCTIONS.template
    assert "across the canonical visual-mode vocabulary" in standard_prompt
    assert "soft candidate discovery expectations" in standard_prompt

    for prompt in (
        standard_prompt,
        script_prompt.LIFE_AS_A_OUTLINE_INSTRUCTIONS.template,
    ):
        assert '"visual_opportunities"' in prompt
        assert '"visual_opportunity_coverage"' in prompt
        assert "before any scenes are written" in prompt
        assert "Do not include any scenes" in prompt or "NO scenes" in prompt
        assert "not final scene JSON" in prompt
        assert "not final visual-mode quotas" in prompt


def test_segment_prompts_consume_visual_opportunities_without_quotas():
    standard_prompt = script_prompt.SCRIPT_SEGMENT_SCENES_INSTRUCTIONS.template
    life_as_a_prompt = script_prompt.LIFE_AS_A_LEVEL_SCENES_INSTRUCTIONS.template

    for prompt in (
        standard_prompt,
        life_as_a_prompt,
    ):
        assert "visual_opportunities" in prompt
        assert "shape scene boundaries" in prompt
        assert "Do not force" in prompt
        assert "format voice" in prompt
        assert "duration" in prompt

    assert "standalone-short clarity" in standard_prompt
    assert "protagonist continuity" in life_as_a_prompt
    assert "emotional arc" in life_as_a_prompt


def test_visual_mode_audit_promotes_caption_candidates_without_rewriting_narration():
    scenes = [
        Scene(id="scene_001", narration="This isn't that version.", visual_prompt="[REACTION] A quiet face under fluorescent lights.", visual_mode="full_frame"),
        Scene(id="scene_002", narration="You clean the same counter again.", visual_prompt="[CLOSE-UP] A hand wiping a counter.", visual_mode="full_frame"),
        Scene(id="scene_003", narration="None of this counts.", visual_prompt="[METAPHOR] A healed burn on a wrist.", visual_mode="full_frame"),
        Scene(id="scene_004", narration="The phrase becomes load-bearing.", visual_prompt="[METAPHOR] A small phrase weighing down a schedule.", visual_mode="full_frame"),
    ]
    original_narration = [scene.narration for scene in scenes]
    content = ScriptContent(title="Test", segments=[Segment(name="Level 1", scenes=scenes)])

    counts = _audit_visual_mode_metadata(content)

    assert counts["captions"] >= 2
    assert [scene.narration for scene in scenes] == original_narration
    caption_scenes = [scene for scene in scenes if scene.visual_mode == "captions"]
    assert caption_scenes
    assert all(scene.caption_text and scene.caption_text in scene.narration for scene in caption_scenes)
    assert all(scene.caption_emphasis and scene.caption_emphasis in scene.caption_text for scene in caption_scenes)


def test_visual_mode_audit_promotes_stat_card_from_life_story_number():
    content = ScriptContent(
        title="Test",
        segments=[
            Segment(
                name="Level 1",
                scenes=[
                    Scene(id="scene_001", narration="The first paycheck is $214.", visual_prompt="[CLOSE-UP] A paper paycheck stub.", visual_mode="full_frame"),
                    Scene(id="scene_002", narration="You keep walking home after close.", visual_prompt="[ESTABLISHING] A sidewalk after close.", visual_mode="full_frame"),
                    Scene(id="scene_003", narration="Marcus retires with seventeen years of service.", visual_prompt="[REACTION] A break room retirement cake.", visual_mode="full_frame"),
                ],
            ),
        ],
    )

    counts = _audit_visual_mode_metadata(content)

    assert counts["stat_card"] >= 1
    stat_scenes = [scene for scene in content.all_scenes() if scene.visual_mode == "stat_card"]
    assert stat_scenes[0].stat_value in {"$214", "seventeen years"}
    assert stat_scenes[0].stat_label


def test_visual_mode_audit_preserves_existing_specialized_modes():
    popup = Scene(
        id="scene_001",
        narration="Keys, slips, and checklists gather around you.",
        visual_prompt="[ESTABLISHING] A manager station with paperwork.",
        visual_mode="popup_sequence",
    )
    content = ScriptContent(
        title="Test",
        segments=[
            Segment(
                name="Level 1",
                scenes=[
                    popup,
                    Scene(id="scene_002", narration="This isn't that version.", visual_prompt="[REACTION] A quiet face under fluorescent lights.", visual_mode="full_frame"),
                ],
            ),
        ],
    )

    _audit_visual_mode_metadata(content)

    assert popup.visual_mode == "popup_sequence"


def test_validate_flipflop_actions_downgrades_missing_action():
    scene = Scene(
        id="s1",
        narration="He blinks once.",
        visual_prompt="[CLOSE-UP] Cartoon man at a desk.",
        visual_mode="flipflop",
    )
    content = ScriptContent(title="Test", segments=[Segment(name="One", scenes=[scene])])

    counts = _validate_flipflop_actions(content, script_id="script-1")

    assert counts["downgraded"] == 1
    assert scene.visual_mode == "full_frame"
    assert scene.flipflop_action == ""


def test_validate_flipflop_actions_preserves_valid_human_action():
    scene = Scene(
        id="s1",
        narration="He blinks once.",
        visual_prompt="[CLOSE-UP] Cartoon man at a desk.",
        visual_mode="flipflop",
        flipflop_action="blink",
    )
    content = ScriptContent(title="Test", segments=[Segment(name="One", scenes=[scene])])

    counts = _validate_flipflop_actions(content, script_id="script-1")

    assert counts["preserved"] == 1
    assert scene.visual_mode == "flipflop"
    assert scene.flipflop_action == "blink"


def test_validate_flipflop_actions_downgrades_pose_changing_action():
    scene = Scene(
        id="s1",
        narration="He nods once.",
        visual_prompt="[CLOSE-UP] Cartoon man at a desk.",
        visual_mode="flipflop",
        flipflop_action="head_nod",
    )
    content = ScriptContent(title="Test", segments=[Segment(name="One", scenes=[scene])])

    counts = _validate_flipflop_actions(content, script_id="script-1")

    assert counts["downgraded"] == 1
    assert scene.visual_mode == "full_frame"
    assert scene.flipflop_action == ""


def test_validate_flipflop_actions_downgrades_pronoun_object_scene(monkeypatch):
    fallback_calls = []

    def fake_record_fallback(**kwargs):
        fallback_calls.append(kwargs)

    monkeypatch.setattr("pipeline.scriptwriter.record_fallback", fake_record_fallback)
    scene = Scene(
        id="s1",
        narration="His bank account blinks red.",
        visual_prompt="[CLOSE-UP] A blank bank account screen on a desk.",
        visual_mode="flipflop",
        flipflop_action="blink",
    )
    content = ScriptContent(title="Test", segments=[Segment(name="One", scenes=[scene])])

    counts = _validate_flipflop_actions(content, script_id="script-1")

    assert counts["downgraded"] == 1
    assert scene.visual_mode == "full_frame"
    assert scene.flipflop_action == ""
    assert fallback_calls == [
        {
            "category": "visual_mode",
            "event": "flipflop_invalid_micro_action_downgraded",
            "reason": "Flipflop scene missing valid human micro-action",
            "severity": "warn",
            "script_id": "script-1",
            "scene_id": "s1",
            "from_value": "flipflop",
            "to_value": "full_frame",
        }
    ]


def test_validate_flipflop_actions_clears_non_flipflop_action():
    scene = Scene(
        id="s1",
        narration="He blinks once.",
        visual_prompt="[CLOSE-UP] Cartoon man at a desk.",
        visual_mode="full_frame",
    )
    object.__setattr__(scene, "flipflop_action", "blink")
    content = ScriptContent(title="Test", segments=[Segment(name="One", scenes=[scene])])

    counts = _validate_flipflop_actions(content, script_id="script-1")

    assert counts["cleared"] == 1
    assert scene.visual_mode == "full_frame"
    assert scene.flipflop_action == ""


def test_visual_mode_audit_rejects_internal_renderer_terms_in_narration():
    content = ScriptContent(
        title="Test",
        segments=[
            Segment(
                name="Level 1",
                scenes=[
                    Scene(
                        id="scene_001",
                        narration="The captions rendering isn't about the phrase itself.",
                        visual_prompt="[METAPHOR] A phrase on a blank canvas.",
                        visual_mode="full_frame",
                    ),
                ],
            ),
        ],
    )

    try:
        _audit_visual_mode_metadata(content)
    except RuntimeError as exc:
        assert "internal visual-mode language" in str(exc)
        assert "scene_001" in str(exc)
    else:
        raise AssertionError("Expected internal visual-mode narration to be rejected")


def test_scene_granularity_preserves_extended_visual_mode_scene():
    content = ScriptContent(
        title="Test",
        intro_hook="",
        outro_cta="",
        segments=[
            Segment(
                name="Segment",
                scenes=[
                    Scene(
                        id="scene_001",
                        narration=(
                            "The old choice looks safe from the outside. "
                            "The new choice costs more up front. "
                            "By the end of the month, the cheap option is the expensive one."
                        ),
                        visual_prompt="Two choices compared side by side.",
                        duration_estimate_seconds=20.0,
                        visual_mode="comparison_board",
                    )
                ],
            )
        ],
    )

    changed = _ensure_scene_granularity(content)

    assert changed == 0
    assert len(content.segments[0].scenes) == 1
    assert content.segments[0].scenes[0].visual_mode == "comparison_board"


def test_scene_granularity_duration_reestimates_low_extended_mode_estimate():
    scene = Scene(
        id="scene_001",
        narration=(
            "The old choice looks safe from the outside. "
            "The new choice costs more up front. "
            "By the end of the month, the cheap option is the expensive one."
        ),
        visual_prompt="Two choices compared side by side.",
        duration_estimate_seconds=10.0,
        visual_mode="comparison_board",
    )

    estimated_duration = _scene_granularity_duration(scene, sentence_count=3)

    assert estimated_duration == 24.0


def test_scene_granularity_duration_applies_extended_floor_for_short_scene():
    scene = Scene(
        id="scene_001",
        narration=(
            "The old choice looks safe from the outside. "
            "The new choice costs more up front."
        ),
        visual_prompt="Two choices compared side by side.",
        duration_estimate_seconds=10.0,
        visual_mode="comparison_board",
    )

    estimated_duration = _scene_granularity_duration(scene, sentence_count=2)

    assert estimated_duration == 20.0


def test_scene_granularity_keeps_low_estimate_extended_visual_mode_scene():
    content = ScriptContent(
        title="Test",
        intro_hook="",
        outro_cta="",
        segments=[
            Segment(
                name="Segment",
                scenes=[
                    Scene(
                        id="scene_001",
                        narration=(
                            "The old choice looks safe from the outside. "
                            "The new choice costs more up front. "
                            "By the end of the month, the cheap option is the expensive one."
                        ),
                        visual_prompt="Two choices compared side by side.",
                        duration_estimate_seconds=10.0,
                        visual_mode="comparison_board",
                    )
                ],
            )
        ],
    )

    changed = _ensure_scene_granularity(content)

    assert changed == 0
    assert len(content.segments[0].scenes) == 1
    scene = content.segments[0].scenes[0]
    assert scene.visual_mode == "comparison_board"
    assert scene.duration_estimate_seconds == 10.0


def test_scene_granularity_keeps_short_low_estimate_extended_visual_mode_scene():
    content = ScriptContent(
        title="Test",
        intro_hook="",
        outro_cta="",
        segments=[
            Segment(
                name="Segment",
                scenes=[
                    Scene(
                        id="scene_001",
                        narration=(
                            "The old choice looks safe from the outside. "
                            "The new choice costs more up front."
                        ),
                        visual_prompt="Two choices compared side by side.",
                        duration_estimate_seconds=10.0,
                        visual_mode="comparison_board",
                    )
                ],
            )
        ],
    )

    changed = _ensure_scene_granularity(content)

    assert changed == 0
    assert len(content.segments[0].scenes) == 1
    scene = content.segments[0].scenes[0]
    assert scene.visual_mode == "comparison_board"
    assert scene.duration_estimate_seconds == 10.0


def test_life_as_a_level_prompt_uses_full_vocabulary_without_quotas():
    prompt_text = script_prompt.LIFE_AS_A_LEVEL_SCENES_INSTRUCTIONS.template

    for mode in (
        "full_frame",
        "continuous",
        "multi_frame",
        "popup_sequence",
        "flipflop",
        "comparison_board",
        "captions",
        "stat_card",
    ):
        assert f"`{mode}`" in prompt_text
    assert "single best visual mode" in prompt_text
    assert "60–75%" not in prompt_text
    assert "NEVER use text-only/editorial caption modes" not in prompt_text


def test_multi_frame_mode_without_directives_is_repaired():
    scene = _static_scene("scene_001")
    scene.visual_mode = "multi_frame"
    scene.visual_beat = "multi_frame"
    scene.frame_directives = []
    content = ScriptContent(
        title="Your Life As A Test",
        format_id="life-as-a",
        segments=[Segment(name="Level 1, the waiting", scenes=[scene])],
    )

    _ensure_visual_beat_directives(content)

    assert scene.visual_mode == "multi_frame"
    assert len(scene.frame_directives) == 4
    assert all(frame.reference_previous is False for frame in scene.frame_directives)
    assert all(frame.transition == "cut" for frame in scene.frame_directives)


def test_continuous_mode_without_directives_is_repaired():
    scene = _static_scene("scene_001")
    scene.visual_mode = "continuous"
    scene.visual_beat = "continuous"
    scene.frame_directives = []
    content = ScriptContent(
        title="Your Life As A Test",
        format_id="life-as-a",
        segments=[Segment(name="Level 1, the waiting", scenes=[scene])],
    )

    _ensure_visual_beat_directives(content)

    assert scene.visual_mode == "continuous"
    assert len(scene.frame_directives) == 3
    assert scene.frame_directives[0].reference_previous is False
    assert all(frame.reference_previous is True for frame in scene.frame_directives[1:])
    assert all(frame.transition == "crossfade" for frame in scene.frame_directives[1:])


def test_captions_mode_without_directives_is_preserved():
    scene = _static_scene("scene_001")
    scene.visual_mode = "captions"
    scene.visual_beat = "captions"
    scene.frame_directives = []
    scene.caption_text = "The quiet cost"
    scene.caption_emphasis = "cost"
    content = ScriptContent(
        title="Your Life As A Test",
        format_id="youtube-listicle",
        segments=[Segment(name="Level 1, the waiting", scenes=[scene])],
    )

    _ensure_visual_beat_directives(content)

    assert scene.visual_mode == "captions"
    assert scene.visual_beat == "captions"
    assert scene.frame_directives == []
    assert scene.caption_text == "The quiet cost"


def test_scene_granularity_splits_overlong_listicle_scene_without_rewriting_narration():
    scene = _static_scene("scene_001")
    scene.narration = (
        "The first warning arrives quietly. "
        "The second one is harder to ignore. "
        "By the third, the whole system is bending around the mistake. "
        "Then the bill arrives."
    )
    scene.duration_estimate_seconds = 32.0
    scene.audio_url = "/static/projects/script/audio/scene_001.mp3"
    scene.audio_duration_seconds = 31.0
    content = ScriptContent(
        title="Test",
        format_id="youtube-listicle",
        segments=[Segment(name="Segment", scenes=[scene])],
    )

    split_count = _ensure_scene_granularity(content)

    scenes = content.segments[0].scenes
    assert split_count == 1
    assert [scene.narration for scene in scenes] == [
        "The first warning arrives quietly.",
        "The second one is harder to ignore.",
        "By the third, the whole system is bending around the mistake.",
        "Then the bill arrives.",
    ]
    assert [scene.id for scene in scenes] == ["scene_001", "scene_002", "scene_003", "scene_004"]
    assert all(scene.visual_mode == "full_frame" for scene in scenes)
    assert all(scene.visual_beat == "static" for scene in scenes)
    assert all(scene.audio_url == "" for scene in scenes)
    assert all(scene.audio_duration_seconds == 0.0 for scene in scenes)


def test_scene_granularity_splits_two_sentence_overlong_listicle_scene():
    scene = _static_scene("scene_001")
    scene.narration = (
        "The first warning stretches into a long explanation that should not stay fused. "
        "The second warning is also long enough that it deserves its own visual beat."
    )
    scene.duration_estimate_seconds = 32.0
    content = ScriptContent(
        title="Test",
        format_id="youtube-listicle",
        segments=[Segment(name="Segment", scenes=[scene])],
    )

    split_count = _ensure_scene_granularity(content)

    scenes = content.segments[0].scenes
    assert split_count == 1
    assert [scene.narration for scene in scenes] == [
        "The first warning stretches into a long explanation that should not stay fused.",
        "The second warning is also long enough that it deserves its own visual beat.",
    ]
    assert [scene.id for scene in scenes] == ["scene_001", "scene_002"]
    assert all(scene.visual_mode == "full_frame" for scene in scenes)
