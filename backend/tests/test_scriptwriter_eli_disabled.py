from pipeline.scriptwriter import build_main_character_instructions


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
