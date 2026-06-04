from models.script import VISUAL_MODES
from pipeline.visual_mode_policy import (
    CANONICAL_VISUAL_MODES,
    duration_profile_for_mode,
    duration_target_for_mode,
    opportunity_policy_for_mode,
    prompt_duration_guidance,
    prompt_visual_opportunity_guidance,
    prompt_visual_opportunity_schema_guidance,
)


def test_duration_policy_covers_all_canonical_visual_modes():
    assert set(CANONICAL_VISUAL_MODES) == VISUAL_MODES

    for mode in CANONICAL_VISUAL_MODES:
        policy = duration_target_for_mode(mode)
        assert policy.visual_mode == mode
        assert policy.profile in {"normal", "medium", "extended", "planned"}
        assert policy.min_seconds > 0
        assert policy.target_seconds >= policy.min_seconds
        assert policy.max_seconds >= policy.target_seconds
        assert policy.ui_label
        assert policy.prompt_guidance


def test_renderer_owned_modes_have_longer_targets_than_full_frame():
    normal = duration_target_for_mode("full_frame")

    assert duration_target_for_mode("captions").target_seconds > normal.target_seconds
    assert duration_target_for_mode("comparison_board").target_seconds > normal.target_seconds
    assert duration_target_for_mode("popup_sequence").target_seconds > normal.target_seconds
    assert duration_target_for_mode("stat_card").target_seconds > normal.target_seconds


def test_unknown_modes_fall_back_to_full_frame_policy():
    assert duration_profile_for_mode("legacy_mode") == "normal"
    assert duration_target_for_mode("legacy_mode") == duration_target_for_mode("full_frame")


def test_prompt_duration_guidance_mentions_extended_and_video_policy():
    text = prompt_duration_guidance()

    assert "captions" in text
    assert "comparison_board" in text
    assert "video" in text
    assert "before voiceover" in text


def test_opportunity_policy_covers_all_canonical_visual_modes():
    for mode in CANONICAL_VISUAL_MODES:
        policy = opportunity_policy_for_mode(mode)
        assert policy.visual_mode == mode
        assert policy.purpose
        assert policy.opportunity_cues
        assert policy.avoid_when
        assert policy.frequency_guidance


def test_visual_opportunity_guidance_is_script_type_agnostic_and_pre_scene():
    text = prompt_visual_opportunity_guidance(projected_scene_count=90)

    assert "script-type agnostic" in text
    assert "before final scenes are written" in text
    assert "Scene boundaries, narration length, duration estimates, and mode-specific fields" in text
    assert "full_frame remains dominant" in text
    assert "flipflop and captions" in text
    assert "common expressive rhythm opportunities" in text
    assert "popup_sequence, comparison_board, and stat_card" in text
    assert "actively scan" in text
    assert "Do not force a quota" in text


def test_flipflop_policy_prefers_character_body_language():
    text = prompt_visual_opportunity_guidance(projected_scene_count=20)
    policy = opportunity_policy_for_mode("flipflop")
    avoid_text = " ".join(policy.avoid_when)

    assert "cropped subject" in text
    assert "body-language" in text
    assert "conceptual" in text
    assert "time periods" in avoid_text
    assert "emotional states" in avoid_text
    assert "locations" in avoid_text
    assert "outcomes" in avoid_text


def test_visual_opportunity_schema_guidance_requests_segment_opportunities():
    text = prompt_visual_opportunity_schema_guidance()

    assert '"visual_opportunities"' in text
    assert '"mode"' in text
    assert '"beat"' in text
    assert '"duration_profile"' in text
    assert '"priority"' in text
    assert "Do not include scenes" in text
