"""Tests for the style-preset resolution helpers."""

from unittest.mock import patch


def test_resolve_returns_none_when_eli_enabled(tmp_path):
    from pipeline.image_gen import _resolve_style_preset

    # Even if a preset would normally be active, Eli takes precedence
    with patch("pipeline.image_gen._active_style_preset_path", return_value=str(tmp_path / "x.png")):
        assert _resolve_style_preset(eli_enabled=True, project_style_enabled=True) is None


def test_resolve_returns_none_when_project_disabled(tmp_path):
    from pipeline.image_gen import _resolve_style_preset

    with patch("pipeline.image_gen._active_style_preset_path", return_value=str(tmp_path / "x.png")):
        assert _resolve_style_preset(eli_enabled=False, project_style_enabled=False) is None


def test_resolve_returns_none_when_no_active_preset():
    from pipeline.image_gen import _resolve_style_preset

    with patch("pipeline.image_gen._active_style_preset_path", return_value=None):
        assert _resolve_style_preset(eli_enabled=False, project_style_enabled=True) is None


def test_resolve_returns_path_when_eligible(tmp_path):
    from pipeline.image_gen import _resolve_style_preset

    expected = str(tmp_path / "preset.png")
    with patch("pipeline.image_gen._active_style_preset_path", return_value=expected):
        assert _resolve_style_preset(eli_enabled=False, project_style_enabled=True) == expected


def test_active_path_returns_none_when_setting_empty():
    from pipeline.image_gen import _active_style_preset_path

    with patch("pipeline.image_gen._read_app_setting", return_value=""):
        assert _active_style_preset_path() is None


def test_active_path_returns_none_when_file_missing(tmp_path):
    from pipeline.image_gen import _active_style_preset_path

    with patch("pipeline.image_gen._read_app_setting", return_value="abc-123"), \
         patch("pipeline.image_gen.DATA_DIR", tmp_path):
        # File does not exist
        assert _active_style_preset_path() is None


def test_active_path_returns_path_when_file_exists(tmp_path):
    from pipeline.image_gen import _active_style_preset_path

    presets_dir = tmp_path / "style" / "presets"
    presets_dir.mkdir(parents=True)
    (presets_dir / "abc-123.png").write_bytes(b"fakepng")

    with patch("pipeline.image_gen._read_app_setting", return_value="abc-123"), \
         patch("pipeline.image_gen.DATA_DIR", tmp_path):
        result = _active_style_preset_path()
        assert result is not None
        assert result.endswith("abc-123.png")
