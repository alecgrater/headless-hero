from pipeline.blink_actions import (
    BLINK_ACTIONS,
    blink_action_prompt_guidance,
    has_human_blink_subject,
    normalize_blink_action,
)


def test_normalize_blink_action_accepts_only_allowlist():
    assert normalize_blink_action("blink") == "blink"
    assert normalize_blink_action("Blink") == ""
    assert normalize_blink_action("walking") == ""
    assert normalize_blink_action(None) == ""


def test_blink_actions_are_stable_snake_case_values():
    assert BLINK_ACTIONS == ("blink",)


def test_action_prompt_guidance_states_blink_is_not_selectable():
    guidance = blink_action_prompt_guidance()
    assert "blink is not a selectable visual mode" in guidance
    assert "Always choose another visual_mode" in guidance


def test_has_human_blink_subject_checks_narration_and_prompt():
    assert has_human_blink_subject("He blinks once.", "[CLOSE-UP] Cartoon man at desk")
    assert has_human_blink_subject("The teacher points at the board.", "")
    assert not has_human_blink_subject("The clock ticks.", "[CLOSE-UP] Clock on wall")
    assert not has_human_blink_subject("The cracked wall shifts.", "[CLOSE-UP] Empty wall")


def test_has_human_blink_subject_rejects_pronoun_object_prompt():
    assert not has_human_blink_subject(
        "His bank account blinks red.",
        "[CLOSE-UP] A blank bank account screen on a desk.",
    )


def test_has_human_blink_subject_rejects_clock_hands_object_prompt():
    assert not has_human_blink_subject(
        "The clock hands move.",
        "[CLOSE-UP] Clock hands on a wall.",
    )


def test_has_human_blink_subject_rejects_cave_mouth_object_prompt():
    assert not has_human_blink_subject(
        "The cave mouth opens wider.",
        "[CLOSE-UP] Mouth of a cave.",
    )


def test_has_human_blink_subject_allows_narration_role_without_prompt():
    assert has_human_blink_subject("The teacher points at the board.", "")


def test_has_human_blink_subject_allows_pronoun_with_human_prompt():
    assert has_human_blink_subject("He blinks once.", "[CLOSE-UP] Cartoon man at desk")


def test_has_human_blink_subject_allows_named_eli_prompt():
    assert has_human_blink_subject(
        "He blinks once.",
        "[REACTION] Eli in a casino uniform behind a counter.",
    )


def test_has_human_blink_subject_allows_cashier_prompt():
    assert has_human_blink_subject(
        "She explains the rule.",
        "[REACTION] A cashier behind the counter.",
    )


def test_has_human_blink_subject_allows_bartender_prompt():
    assert has_human_blink_subject(
        "He nods.",
        "[REACTION] A bartender polishing a glass.",
    )
