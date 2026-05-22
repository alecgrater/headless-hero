from pathlib import Path
from unittest.mock import patch

from models.script import MainCharacter
from pipeline.main_character import (
    build_reference_prompt,
    character_reference_path,
    generate_character_reference,
)


def test_build_reference_prompt_uses_all_fields():
    char = MainCharacter(
        name="Sam",
        appearance="tall, red beard, flannel shirt",
        vibe="calm woodworker",
    )
    prompt = build_reference_prompt(char)
    assert "Sam" in prompt
    assert "red beard" in prompt
    assert "calm" in prompt
    # Must enforce neutral framing for a reference image
    assert "neutral" in prompt.lower() or "plain" in prompt.lower()


def test_character_reference_path_is_per_project():
    p = character_reference_path("script-abc")
    assert "script-abc" in str(p)
    assert p.name == "reference.png"


def test_generate_character_reference_writes_file_and_returns_web_path(tmp_path, monkeypatch):
    monkeypatch.setenv("HH_DATA_DIR", str(tmp_path))

    # Re-import so DATA_DIR picks up tmp path.
    import importlib

    import config

    importlib.reload(config)
    import pipeline.main_character as mc

    importlib.reload(mc)

    fake_temp = tmp_path / "fake_gemini_output.png"
    fake_temp.write_bytes(b"\x89PNG fake")

    with patch.object(mc, "_call_image_generator", return_value=str(fake_temp)):
        web_path = mc.generate_character_reference(
            script_id="script-xyz",
            character=MainCharacter(name="x", appearance="y", vibe="z"),
        )

    assert web_path.startswith("/static/projects/script-xyz/character/")
    target = tmp_path / "projects" / "script-xyz" / "character" / "reference.png"
    assert target.exists()
