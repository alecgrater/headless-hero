from pipeline.scriptwriter import (
    build_main_character_instructions,
    build_outline_main_character_addendum,
    build_script_outline_instructions,
)


def test_main_character_instructions_present():
    text = build_main_character_instructions()
    # Must instruct Claude to output a main_character block
    assert "main_character" in text
    # Must instruct Claude to set contains_person on relevant scenes
    assert "contains_person" in text
    # Must say Eli is disabled
    assert "Eli" in text


def test_main_character_instructions_short_enough_to_inject():
    text = build_main_character_instructions()
    # Sanity: not absurdly long (keeps prompt token budget reasonable)
    assert len(text) < 3000


def test_outline_addendum_includes_main_character_schema():
    """The outline addendum must reference the main_character schema."""
    text = build_outline_main_character_addendum()
    assert "main_character" in text
    assert "name" in text
    assert "appearance" in text
    assert "vibe" in text


def test_segmented_script_outline_instructions_include_main_character_when_eli_disabled():
    """Outline instructions for eli_disabled mode reference main_character schema."""
    text_disabled = build_script_outline_instructions(eli_enabled=False)
    assert "main_character" in text_disabled

    text_enabled = build_script_outline_instructions(eli_enabled=True)
    assert "main_character" not in text_enabled
