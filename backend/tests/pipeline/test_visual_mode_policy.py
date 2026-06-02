from models.script import VISUAL_MODES
from pipeline.visual_mode_policy import (
    CANONICAL_VISUAL_MODES,
    duration_profile_for_mode,
    duration_target_for_mode,
    prompt_duration_guidance,
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
