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


def test_resolve_eli_disabled_no_character_falls_back_to_no_ref(tmp_path, monkeypatch):
    """If eli is disabled but main character not yet generated, fall back to no reference."""
    ig_mod = _reset_data_dir(monkeypatch, tmp_path)

    ref_path, char_text = ig_mod._resolve_character_reference(
        script_id="s",
        contains_person=True,
        eli_enabled=False,
        main_character_reference_url=None,
        main_character=None,
    )
    assert ref_path is None
    assert char_text == ""


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


def test_generate_scene_frames_uses_resolved_reference(tmp_path, monkeypatch):
    """generate_scene_frames must call _resolve_character_reference (not the old path).

    With eli_enabled=False and no main character configured, the first frame should
    receive ref_path=None and the prompt should NOT contain the Eli character prompt.
    """
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

    ig_mod.generate_scene_frames(
        scene_id="scene1",
        frame_prompts=["a person waving"],
        script_id="proj1",
        visual_prompt="a person in a park",
        contains_person=True,
    )

    assert len(captured) == 1
    # Old path would have set ref to the eli reference; new path returns None.
    assert captured[0]["reference_image_path"] is None
    # Old path would have appended the Eli _CHARACTER_PROMPT; new path skips it.
    if ig_mod._CHARACTER_PROMPT:
        assert ig_mod._CHARACTER_PROMPT not in captured[0]["prompt"]


def test_generate_scene_frames_v2_uses_resolved_reference(tmp_path, monkeypatch):
    """generate_scene_frames_v2 must call _resolve_character_reference (not the old path)."""
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

    assert len(captured) == 1
    assert captured[0]["reference_image_path"] is None
    if ig_mod._CHARACTER_PROMPT:
        assert ig_mod._CHARACTER_PROMPT not in captured[0]["prompt"]
