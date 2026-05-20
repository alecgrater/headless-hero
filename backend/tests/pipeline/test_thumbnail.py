"""Tests for long-form thumbnail helpers."""

from PIL import Image

from pipeline import thumbnail


def test_gemini_thumbnail_prompt_forbids_arrows(tmp_path, monkeypatch):
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
    )

    assert result == str(tmp_path / "enhanced.png")
    assert "DO NOT add any arrow" in captured["prompt"]
