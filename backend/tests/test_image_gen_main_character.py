"""Test the project-mode-aware character reference resolver in image_gen."""

from models.script import MainCharacter


def _reset_data_dir(monkeypatch, tmp_path):
    """Re-import config + image_gen with HH_DATA_DIR pointing at tmp_path."""
    monkeypatch.setenv("HH_DATA_DIR", str(tmp_path))
    import importlib

    import config

    importlib.reload(config)
    import pipeline.image_gen as ig_mod

    importlib.reload(ig_mod)
    return ig_mod


def test_resolve_eli_enabled_returns_eli_reference(tmp_path, monkeypatch):
    ig_mod = _reset_data_dir(monkeypatch, tmp_path)

    eli_ref = tmp_path / "character" / "frames" / "selected_reference.png"
    eli_ref.parent.mkdir(parents=True, exist_ok=True)
    eli_ref.write_bytes(b"x")

    ref_path, char_text = ig_mod._resolve_character_reference(
        script_id="s",
        contains_person=True,
        eli_enabled=True,
        main_character_reference_url=None,
        main_character=None,
    )
    assert ref_path == str(eli_ref)
    # Eli's text description should be present (or empty string if not configured)
    assert isinstance(char_text, str)


def test_resolve_eli_disabled_uses_project_character(tmp_path, monkeypatch):
    ig_mod = _reset_data_dir(monkeypatch, tmp_path)

    project_ref = tmp_path / "projects" / "abc" / "character" / "reference.png"
    project_ref.parent.mkdir(parents=True, exist_ok=True)
    project_ref.write_bytes(b"x")

    char = MainCharacter(name="Maya", appearance="red coat", vibe="brisk")
    ref_path, char_text = ig_mod._resolve_character_reference(
        script_id="abc",
        contains_person=True,
        eli_enabled=False,
        main_character_reference_url="/static/projects/abc/character/reference.png",
        main_character=char,
    )
    assert ref_path == str(project_ref)
    assert "Maya" in char_text
    assert "red coat" in char_text


def test_resolve_no_person_returns_none(tmp_path, monkeypatch):
    ig_mod = _reset_data_dir(monkeypatch, tmp_path)

    ref_path, char_text = ig_mod._resolve_character_reference(
        script_id="s",
        contains_person=False,
        eli_enabled=False,
        main_character_reference_url="/static/projects/s/character/reference.png",
        main_character=MainCharacter(name="x", appearance="y", vibe="z"),
    )
    assert ref_path is None
    assert char_text == ""


def test_resolve_eli_disabled_no_character_blocks_generation(tmp_path, monkeypatch):
    """If Eli is disabled, character scenes must not generate without a reference."""
    ig_mod = _reset_data_dir(monkeypatch, tmp_path)

    try:
        ig_mod._resolve_character_reference(
            script_id="s",
            contains_person=True,
            eli_enabled=False,
            main_character_reference_url=None,
            main_character=None,
        )
    except RuntimeError as exc:
        assert "Main character" in str(exc)
    else:
        raise AssertionError("Expected missing main character to block image generation")


def _stub_generate_image(monkeypatch, ig_mod, captured: list[dict]):
    """Replace generate_image with a stub that records args + writes a fake PNG."""
    import os
    import tempfile

    from PIL import Image as _Img

    def fake_generate_image(prompt, *, width, height, reference_image_path=None,
                            original_prompt=None, script_id=None, **kwargs):
        # Write minimal PNG bytes so _move_generated_image succeeds.
        fd, tmp = tempfile.mkstemp(suffix=".png")
        os.close(fd)
        _Img.new("RGB", (8, 8), color=(0, 0, 0)).save(tmp)
        captured.append({
            "prompt": prompt,
            "reference_image_path": reference_image_path,
            "original_prompt": original_prompt,
        })
        return tmp

    monkeypatch.setattr(ig_mod, "generate_image", fake_generate_image)


def test_generate_scene_frames_blocks_when_project_character_missing(tmp_path, monkeypatch):
    """generate_scene_frames must not fall back to Eli or anonymous generation."""
    ig_mod = _reset_data_dir(monkeypatch, tmp_path)

    # Eli reference file exists on disk — old path would have picked it up.
    eli_ref = tmp_path / "character" / "frames" / "selected_reference.png"
    eli_ref.parent.mkdir(parents=True, exist_ok=True)
    eli_ref.write_bytes(b"x")

    # Force resolver to return (None, "") by stubbing _load_project_character_context
    # to indicate eli is disabled and no main character is set.
    monkeypatch.setattr(
        ig_mod,
        "_load_project_character_context",
        lambda script_id: (False, None, None),
    )

    captured: list[dict] = []
    _stub_generate_image(monkeypatch, ig_mod, captured)

    try:
        ig_mod.generate_scene_frames(
            scene_id="scene1",
            frame_prompts=["a person waving"],
            script_id="proj1",
            visual_prompt="a person in a park",
            contains_person=True,
        )
    except RuntimeError as exc:
        assert "Main character" in str(exc)
    else:
        raise AssertionError("Expected missing main character reference to block frame generation")

    assert captured == []


def test_generate_scene_frames_v2_blocks_when_project_character_missing(tmp_path, monkeypatch):
    """generate_scene_frames_v2 must not fall back to Eli or anonymous generation."""
    ig_mod = _reset_data_dir(monkeypatch, tmp_path)

    eli_ref = tmp_path / "character" / "frames" / "selected_reference.png"
    eli_ref.parent.mkdir(parents=True, exist_ok=True)
    eli_ref.write_bytes(b"x")

    monkeypatch.setattr(
        ig_mod,
        "_load_project_character_context",
        lambda script_id: (False, None, None),
    )

    captured: list[dict] = []
    _stub_generate_image(monkeypatch, ig_mod, captured)

    try:
        ig_mod.generate_scene_frames_v2(
            scene_id="scene1",
            frame_directives=[
                {
                    "source": "ai_generated",
                    "prompt": "a person waving",
                    "reference_previous": False,
                    "contains_person": True,
                },
            ],
            script_id="proj1",
            visual_prompt="a person in a park",
            contains_person=True,
        )
    except RuntimeError as exc:
        assert "Main character" in str(exc)
    else:
        raise AssertionError("Expected missing main character reference to block frame generation")

    assert captured == []


def test_generate_scene_frames_v2_independent_frames_share_style_and_forbid_borders(tmp_path, monkeypatch):
    ig_mod = _reset_data_dir(monkeypatch, tmp_path)
    monkeypatch.setattr(ig_mod, "_VISUAL_STYLE", "HOUSE STYLE")
    monkeypatch.setattr(ig_mod, "_STYLE_GUIDE", "COMPOSITION GUIDE")
    monkeypatch.setattr(ig_mod, "_load_project_character_context", lambda script_id: (True, None, None))
    monkeypatch.setattr(ig_mod, "_ensure_project_character_reference_ready", lambda **_kwargs: None)
    monkeypatch.setattr(ig_mod, "_load_project_style_enabled", lambda script_id: False)
    monkeypatch.setattr(ig_mod, "_resolve_style_preset", lambda **_kwargs: None)

    captured: list[dict] = []
    _stub_generate_image(monkeypatch, ig_mod, captured)

    ig_mod.generate_scene_frames_v2(
        scene_id="scene1",
        frame_directives=[
            {
                "source": "ai_generated",
                "prompt": "Opening shot of a flat cartoon city street.",
                "reference_previous": False,
            },
            {
                "source": "ai_generated",
                "prompt": "Escalated shot of the same street cracking apart.",
                "reference_previous": False,
            },
        ],
        script_id="proj1",
        visual_prompt="Flat 2D cartoon city street cracking apart, anxious crowd, clean educational composition.",
    )

    assert len(captured) == 2
    for call in captured:
        prompt = call["prompt"]
        assert "Multi-image sequence consistency" in prompt
        assert "Flat 2D cartoon city street cracking apart" in prompt
        assert "full-bleed 16:9 illustration" in prompt
        assert "No decorative border" in prompt
        assert "This specific frame" not in prompt


def test_generate_scene_image_blocks_all_images_until_project_character_ready(tmp_path, monkeypatch):
    """Eli-disabled projects should not generate even object-only images before the character reference exists."""
    ig_mod = _reset_data_dir(monkeypatch, tmp_path)

    monkeypatch.setattr(
        ig_mod,
        "_load_project_character_context",
        lambda script_id: (False, None, MainCharacter(name="Maya", appearance="red coat", vibe="brisk")),
    )

    captured: list[dict] = []
    _stub_generate_image(monkeypatch, ig_mod, captured)

    try:
        ig_mod.generate_scene_image(
            scene_id="scene1",
            visual_prompt="a close-up of keys on a belt",
            script_id="proj1",
            contains_person=False,
        )
    except RuntimeError as exc:
        assert "reference" in str(exc)
    else:
        raise AssertionError("Expected missing main character reference to block all image generation")

    assert captured == []
