"""Tests for style_presets.generate_preset orchestration."""

from unittest.mock import patch

import pytest


def test_generate_preset_writes_image_and_db_row(tmp_path, monkeypatch):
    from pipeline import style_presets
    from sqlmodel import SQLModel, create_engine

    monkeypatch.setattr(style_presets, "DATA_DIR", tmp_path)
    test_engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(test_engine)
    monkeypatch.setattr(style_presets, "engine", test_engine)

    fake_tmp = tmp_path / "gemini_tmp.png"
    fake_tmp.write_bytes(b"fakepng")

    with patch.object(
        style_presets, "generate_image", return_value=str(fake_tmp)
    ):
        preset_id = style_presets.generate_preset(
            prompt="a 16:9 reference sheet of cartoon people and objects",
            name="Saturday Cartoon",
        )

    # The preset image should be moved into data/style/presets/<id>.png
    assert (tmp_path / "style" / "presets" / f"{preset_id}.png").exists()

    # And a DB row should be readable
    from sqlmodel import Session
    from models.style_preset import StylePreset

    with Session(test_engine) as session:
        row = session.get(StylePreset, preset_id)
        assert row is not None
        assert row.name == "Saturday Cartoon"
        assert row.prompt == "a 16:9 reference sheet of cartoon people and objects"


def test_generate_preset_propagates_gemini_failure(tmp_path, monkeypatch):
    from pipeline import style_presets

    monkeypatch.setattr(style_presets, "DATA_DIR", tmp_path)

    with patch.object(
        style_presets, "generate_image", side_effect=RuntimeError("Gemini blocked")
    ):
        with pytest.raises(RuntimeError, match="Gemini blocked"):
            style_presets.generate_preset(prompt="x", name="y")
