"""Test the project-mode-aware character reference resolver in image_gen."""

import pytest

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
