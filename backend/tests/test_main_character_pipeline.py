from unittest.mock import patch

from PIL import Image, ImageDraw

from models.script import MainCharacter
from pipeline.main_character import (
    build_reference_prompt,
    character_reference_path,
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


def test_build_reference_prompt_enforces_house_cartoon_style():
    char = MainCharacter(
        name="Maya",
        appearance="athletic runner with a high ponytail and teal leggings",
        vibe="upbeat and focused",
    )
    prompt = build_reference_prompt(char).lower()

    assert "universal visual style" in prompt
    assert "flat 2d cartoon" in prompt
    assert "same illustrated world" in prompt
    assert "no text" in prompt
    assert "never use photorealism" in prompt
    assert "cinematic film still aesthetic" not in prompt.replace(
        "never use photorealism, cinematic film still aesthetics", ""
    )


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
    image = Image.new("RGB", (180, 140), (0, 255, 0))
    draw = ImageDraw.Draw(image)
    draw.rectangle((70, 34, 110, 112), fill=(255, 0, 0))
    image.save(fake_temp)

    with patch.object(mc, "_call_image_generator", return_value=str(fake_temp)):
        web_path = mc.generate_character_reference(
            script_id="script-xyz",
            character=MainCharacter(name="x", appearance="y", vibe="z"),
        )

    assert web_path.startswith("/static/projects/script-xyz/character/")
    target = tmp_path / "projects" / "script-xyz" / "character" / "reference.png"
    assert target.exists()
    variant = tmp_path / "projects" / "script-xyz" / "character" / "references" / "1.png"
    variant_cutout = tmp_path / "projects" / "script-xyz" / "character" / "references" / "1.cutout.png"
    active_cutout = tmp_path / "projects" / "script-xyz" / "character" / "cutout.png"
    assert variant.exists()
    assert variant_cutout.exists()
    assert active_cutout.exists()
    variants = mc.list_character_reference_variants("script-xyz")
    assert variants == [
        {
            "idx": 1,
            "image_url": "/static/projects/script-xyz/character/references/1.png",
            "cutout_image_url": "/static/projects/script-xyz/character/references/1.cutout.png",
            "active": True,
        }
    ]
