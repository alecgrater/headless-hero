from models.script import MainCharacter, ScriptContent


def test_main_character_has_required_fields():
    char = MainCharacter(
        name="Maya",
        appearance="dark hair, leather jacket, late 30s, weathered face",
        vibe="grizzled detective with dry humor",
    )
    assert char.name == "Maya"


def test_script_content_main_character_optional():
    content = ScriptContent(title="t", segments=[])
    assert content.main_character is None


def test_script_content_main_character_serializes():
    char = MainCharacter(name="A", appearance="b", vibe="c")
    content = ScriptContent(title="t", segments=[], main_character=char)
    dumped = content.model_dump()
    assert dumped["main_character"]["name"] == "A"
