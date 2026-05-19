"""Tests for long-form thumbnail helpers."""

from pathlib import Path

from PIL import Image

from api.settings import ALLOWED_KEYS, _DEFAULTS, _PLAINTEXT_KEYS
from pipeline import thumbnail


def test_longform_thumbnail_arrow_setting_is_exposed():
    key = "LONGFORM_THUMBNAIL_ARROW_ENABLED"

    assert key in ALLOWED_KEYS
    assert key in _PLAINTEXT_KEYS
    assert _DEFAULTS[key] == "true"


def test_gemini_thumbnail_prompt_can_disable_arrow(tmp_path, monkeypatch):
    base_path = tmp_path / "base.png"
    ref_dir = tmp_path / "refs"
    ref_dir.mkdir()
    Image.new("RGB", (32, 32), (20, 40, 80)).save(base_path)
    Image.new("RGB", (32, 32), (80, 40, 20)).save(ref_dir / "ref.png")

    captured: dict[str, str] = {}

    def fake_transform_with_references(prompt: str, image_paths: list[str], script_id: str | None = None) -> str:
        captured["prompt"] = prompt
        assert image_paths[0] == str(base_path)
        return str(tmp_path / "enhanced.png")

    monkeypatch.setattr(thumbnail, "THUMBNAIL_REFERENCES_DIR", ref_dir)
    monkeypatch.setattr("integrations.google_image_client.transform_with_references", fake_transform_with_references)

    result = thumbnail.gemini_enhance_thumbnail(
        base_image_path=str(base_path),
        video_title="Test Video",
        script_id="script-1",
        include_arrow=False,
    )

    assert result == str(tmp_path / "enhanced.png")
    assert "DO NOT add any arrow" in captured["prompt"]
