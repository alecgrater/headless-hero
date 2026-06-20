import pytest

from pipeline.blink_actions import (
    BLINK_ACTIONS,
    PRODUCTION_BLINK_ACTIONS,
    build_blink_state_prompt,
    blink_action_prompt_guidance,
    has_human_blink_subject,
    normalize_blink_action,
    normalize_production_blink_action,
)


def test_normalize_blink_action_accepts_only_allowlist():
    assert normalize_blink_action("blink") == "blink"
    assert normalize_blink_action("Blink") == ""
    assert normalize_blink_action("walking") == ""
    assert normalize_blink_action(None) == ""


def test_blink_actions_are_stable_snake_case_values():
    assert BLINK_ACTIONS == ("blink",)


def test_production_blink_actions_are_face_only():
    assert PRODUCTION_BLINK_ACTIONS == ()
    assert normalize_production_blink_action("blink") == ""
    assert normalize_production_blink_action("talking") == ""
    assert normalize_production_blink_action("walking") == ""


def test_action_prompt_guidance_contains_reliability_tiers():
    guidance = blink_action_prompt_guidance()
    assert "Production blink_action values: none" in guidance
    assert "Always choose another visual_mode" in guidance
    assert "`blink`" in guidance
    assert "`talking`" not in guidance


def test_build_blink_state_prompt_uses_blink_state_text():
    state_a = build_blink_state_prompt(
        visual_prompt="[REACTION] Cartoon teacher explaining at a podium.",
        narration="He calmly explains the rule.",
        action="blink",
        state="a",
    )
    state_b = build_blink_state_prompt(
        visual_prompt="[REACTION] Cartoon teacher explaining at a podium.",
        narration="He calmly explains the rule.",
        action="blink",
        state="b",
    )

    assert "eyes open, neutral natural face" in state_a
    assert "eyes closed in a quick blink" in state_b
    assert "The ONLY allowed change between State A and State B is the named micro-action." in state_b
    assert "Lock identity across both states" in state_b
    assert "Render ONE isolated human or character cutout only." in state_b
    assert "ignore and do NOT render any setting, room, counter" in state_b
    assert "Character description:" in state_b


def test_build_blink_state_prompt_locks_unaffected_features():
    state_b = build_blink_state_prompt(
        visual_prompt="Young employee in a red polo behind a counter with a register.",
        narration="You start your shift.",
        action="blink",
        state="b",
    )

    assert "do not change the mouth shape" in state_b
    assert "do not change the eyebrows" in state_b
    assert "do not change hands or arms" in state_b
    assert "Only the eyelids may change for the blink" in state_b
    assert "Copy State A exactly" in state_b
    assert "hat, hair, ears, neck, collar, torso, shoulders, and arm edges must remain identical" in state_b
    assert "only redraw the small internal facial mark required by the action" in state_b


def test_build_blink_state_prompt_locks_registration_and_zoom():
    state_b = build_blink_state_prompt(
        visual_prompt="Young employee in a red polo, chest-up portrait.",
        narration="You start your shift.",
        action="blink",
        state="b",
    )

    assert "same pixel footprint" in state_b
    assert "Do not zoom" in state_b
    assert "Do not move the character" in state_b


def test_build_blink_state_prompt_rejects_invalid_state():
    with pytest.raises(ValueError, match="blink state must be 'a' or 'b'"):
        build_blink_state_prompt(
            visual_prompt="[REACTION] Cartoon teacher explaining at a podium.",
            narration="He calmly explains the rule.",
            action="blink",
            state="state_a",  # type: ignore[arg-type]
        )


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
