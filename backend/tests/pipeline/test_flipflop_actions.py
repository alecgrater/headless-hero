import pytest

from pipeline.flipflop_actions import (
    FLIPFLOP_ACTIONS,
    build_flipflop_state_prompt,
    flipflop_action_prompt_guidance,
    has_human_flipflop_subject,
    normalize_flipflop_action,
)


def test_normalize_flipflop_action_accepts_only_allowlist():
    assert normalize_flipflop_action("blink") == "blink"
    assert normalize_flipflop_action("Blink") == ""
    assert normalize_flipflop_action("walking") == ""
    assert normalize_flipflop_action(None) == ""


def test_flipflop_actions_are_stable_snake_case_values():
    assert FLIPFLOP_ACTIONS == (
        "blink",
        "speaking_mouth",
        "eye_glance",
        "eyebrow_raise",
        "head_nod",
        "explaining_hand_raise",
        "thinking_pose",
        "pointing_gesture",
        "counting_fingers",
        "small_shrug",
    )


def test_action_prompt_guidance_contains_reliability_tiers():
    guidance = flipflop_action_prompt_guidance()
    assert "Most reliable: blink, speaking_mouth, eye_glance, eyebrow_raise" in guidance
    assert "Reliable when supported: head_nod, explaining_hand_raise, thinking_pose" in guidance
    assert "Use only with clear prompt support: pointing_gesture, counting_fingers, small_shrug" in guidance


def test_build_flipflop_state_prompt_uses_action_specific_state_text():
    state_a = build_flipflop_state_prompt(
        visual_prompt="[REACTION] Cartoon teacher explaining at a podium.",
        narration="He calmly explains the rule.",
        action="speaking_mouth",
        state="a",
    )
    state_b = build_flipflop_state_prompt(
        visual_prompt="[REACTION] Cartoon teacher explaining at a podium.",
        narration="He calmly explains the rule.",
        action="speaking_mouth",
        state="b",
    )

    assert "mouth closed or lightly resting" in state_a
    assert "mouth slightly open as if speaking one syllable" in state_b
    assert "The ONLY allowed change between State A and State B is the named micro-action." in state_b
    assert "Lock identity across both states" in state_b
    assert "Render ONE isolated human or character cutout only." in state_b
    assert "ignore and do NOT render any setting, room, counter" in state_b
    assert "Character description:" in state_b


def test_build_flipflop_state_prompt_locks_unaffected_features():
    state_b = build_flipflop_state_prompt(
        visual_prompt="Young employee in a red polo behind a counter with a register.",
        narration="You start your shift.",
        action="eyebrow_raise",
        state="b",
    )

    assert "do not change the mouth shape unless the action is speaking_mouth" in state_b
    assert "do not change the eyes unless the action is blink or eye_glance" in state_b
    assert "do not change the eyebrows unless" in state_b
    assert "do not change hands or arms unless the action requires it" in state_b


def test_build_flipflop_state_prompt_rejects_invalid_state():
    with pytest.raises(ValueError, match="flipflop state must be 'a' or 'b'"):
        build_flipflop_state_prompt(
            visual_prompt="[REACTION] Cartoon teacher explaining at a podium.",
            narration="He calmly explains the rule.",
            action="speaking_mouth",
            state="state_a",  # type: ignore[arg-type]
        )


def test_has_human_flipflop_subject_checks_narration_and_prompt():
    assert has_human_flipflop_subject("He blinks once.", "[CLOSE-UP] Cartoon man at desk")
    assert has_human_flipflop_subject("The teacher points at the board.", "")
    assert not has_human_flipflop_subject("The clock ticks.", "[CLOSE-UP] Clock on wall")
    assert not has_human_flipflop_subject("The cracked wall shifts.", "[CLOSE-UP] Empty wall")


def test_has_human_flipflop_subject_rejects_pronoun_object_prompt():
    assert not has_human_flipflop_subject(
        "His bank account blinks red.",
        "[CLOSE-UP] A blank bank account screen on a desk.",
    )


def test_has_human_flipflop_subject_rejects_clock_hands_object_prompt():
    assert not has_human_flipflop_subject(
        "The clock hands move.",
        "[CLOSE-UP] Clock hands on a wall.",
    )


def test_has_human_flipflop_subject_rejects_cave_mouth_object_prompt():
    assert not has_human_flipflop_subject(
        "The cave mouth opens wider.",
        "[CLOSE-UP] Mouth of a cave.",
    )


def test_has_human_flipflop_subject_allows_narration_role_without_prompt():
    assert has_human_flipflop_subject("The teacher points at the board.", "")


def test_has_human_flipflop_subject_allows_pronoun_with_human_prompt():
    assert has_human_flipflop_subject("He blinks once.", "[CLOSE-UP] Cartoon man at desk")


def test_has_human_flipflop_subject_allows_named_eli_prompt():
    assert has_human_flipflop_subject(
        "He blinks once.",
        "[REACTION] Eli in a casino uniform behind a counter.",
    )


def test_has_human_flipflop_subject_allows_cashier_prompt():
    assert has_human_flipflop_subject(
        "She explains the rule.",
        "[REACTION] A cashier behind the counter.",
    )


def test_has_human_flipflop_subject_allows_bartender_prompt():
    assert has_human_flipflop_subject(
        "He nods.",
        "[REACTION] A bartender polishing a glass.",
    )
