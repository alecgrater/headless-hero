"""Tests confirming thumbnail paths thread the style preset into
transform_with_references' image_paths list.

Both call sites live in pipeline.thumbnail:
  1. enhance_split_progression  (used by cinematic-chapters strategy)
  2. gemini_enhance_thumbnail   (used by long-form / title-card thumbnail flow)
"""

from unittest.mock import patch


# ---------------------------------------------------------------------------
# _resolve_thumbnail_style_ref
# ---------------------------------------------------------------------------


def test_resolver_returns_path_when_eli_off_and_style_on(tmp_path, monkeypatch):
    """The thumbnail resolver delegates to image_gen._resolve_style_preset
    using the project's eli_enabled and style_preset_enabled flags."""
    import pipeline.thumbnail as thumb_module

    class FakeCfg:
        eli_enabled = False
        style_preset_enabled = True

    def fake_get_cfg(session, script_id):
        return FakeCfg()

    with patch("models.project_config.get_project_config", fake_get_cfg):
        expected = str(tmp_path / "preset.png")
        with patch("pipeline.image_gen._resolve_style_preset", return_value=expected) as mock_resolve:
            result = thumb_module._resolve_thumbnail_style_ref(script_id="proj-1")

    assert result == expected
    mock_resolve.assert_called_once_with(eli_enabled=False, project_style_enabled=True)


def test_resolver_returns_none_when_eli_on(tmp_path, monkeypatch):
    import pipeline.thumbnail as thumb_module

    class FakeCfg:
        eli_enabled = True
        style_preset_enabled = True

    def fake_get_cfg(session, script_id):
        return FakeCfg()

    with patch("models.project_config.get_project_config", fake_get_cfg):
        with patch("pipeline.image_gen._resolve_style_preset", return_value=None) as mock_resolve:
            result = thumb_module._resolve_thumbnail_style_ref(script_id="proj-1")

    assert result is None
    mock_resolve.assert_called_once_with(eli_enabled=True, project_style_enabled=True)


# ---------------------------------------------------------------------------
# enhance_split_progression appends style ref
# ---------------------------------------------------------------------------


def test_enhance_split_progression_appends_style_ref(tmp_path, monkeypatch):
    """When a style preset is active, enhance_split_progression includes it in image_paths."""
    import pipeline.thumbnail as thumb_module

    monkeypatch.setattr(thumb_module, "DATA_DIR", tmp_path)

    captured = {}

    def fake_transform(prompt, image_paths, script_id=None):
        captured["image_paths"] = list(image_paths)
        out = tmp_path / "enhanced.png"
        out.write_bytes(b"fakepng")
        return str(out)

    style_ref = tmp_path / "preset.png"
    style_ref.write_bytes(b"fakepng")

    monkeypatch.setattr(thumb_module, "_resolve_thumbnail_style_ref", lambda script_id: str(style_ref))

    # Patch the lazy import inside enhance_split_progression
    with patch("integrations.google_image_client.transform_with_references", fake_transform):
        clean = tmp_path / "clean.png"
        clean.write_bytes(b"fakepng")
        out_path = tmp_path / "split.png"

        thumb_module.enhance_split_progression(
            clean_image_path=clean,
            output_path=out_path,
            left_label="3 months in",
            right_label="10 years in",
            script_id="proj-1",
            force=True,
        )

    assert captured.get("image_paths") is not None, "transform_with_references was not called"
    assert str(style_ref) in captured["image_paths"]


def test_enhance_split_progression_no_style_ref_unchanged(tmp_path, monkeypatch):
    """When no style preset is active, enhance_split_progression sends only the clean image."""
    import pipeline.thumbnail as thumb_module

    monkeypatch.setattr(thumb_module, "DATA_DIR", tmp_path)

    captured = {}

    def fake_transform(prompt, image_paths, script_id=None):
        captured["image_paths"] = list(image_paths)
        out = tmp_path / "enhanced.png"
        out.write_bytes(b"fakepng")
        return str(out)

    monkeypatch.setattr(thumb_module, "_resolve_thumbnail_style_ref", lambda script_id: None)

    with patch("integrations.google_image_client.transform_with_references", fake_transform):
        clean = tmp_path / "clean.png"
        clean.write_bytes(b"fakepng")
        out_path = tmp_path / "split.png"

        thumb_module.enhance_split_progression(
            clean_image_path=clean,
            output_path=out_path,
            left_label="3 months in",
            right_label="10 years in",
            script_id="proj-1",
            force=True,
        )

    assert captured.get("image_paths") == [str(clean)]


# ---------------------------------------------------------------------------
# gemini_enhance_thumbnail appends style ref
# ---------------------------------------------------------------------------


def test_gemini_enhance_thumbnail_appends_style_ref(tmp_path, monkeypatch):
    """When a style preset is active, gemini_enhance_thumbnail appends it to image_paths."""
    import pipeline.thumbnail as thumb_module

    monkeypatch.setattr(thumb_module, "DATA_DIR", tmp_path)

    # Create a thumbnail references directory with one ref so the function doesn't short-circuit
    ref_dir = tmp_path / "character" / "thumbnail_references"
    ref_dir.mkdir(parents=True)
    ref_file = ref_dir / "ref1.png"
    ref_file.write_bytes(b"refpng")

    monkeypatch.setattr(thumb_module, "THUMBNAIL_REFERENCES_DIR", ref_dir)

    style_ref = tmp_path / "preset.png"
    style_ref.write_bytes(b"stylepng")

    monkeypatch.setattr(thumb_module, "_resolve_thumbnail_style_ref", lambda script_id: str(style_ref))

    captured = {}

    def fake_transform(prompt, image_paths, script_id=None):
        captured["image_paths"] = list(image_paths)
        out = tmp_path / "enhanced.png"
        out.write_bytes(b"fakepng")
        return str(out)

    # Stub character frame manifest so no eli frame is added (keeps test focused)
    with patch("pipeline.character_frames.get_manifest", return_value=None), \
         patch("integrations.google_image_client.transform_with_references", fake_transform):
        base = tmp_path / "base.png"
        base.write_bytes(b"basepng")

        thumb_module.gemini_enhance_thumbnail(
            base_image_path=str(base),
            video_title="My Video",
            script_id="proj-1",
        )

    assert captured.get("image_paths") is not None, "transform_with_references was not called"
    assert str(style_ref) in captured["image_paths"]


def test_gemini_enhance_thumbnail_no_style_ref_unchanged(tmp_path, monkeypatch):
    """When no style preset is active, gemini_enhance_thumbnail does not add extra image_paths."""
    import pipeline.thumbnail as thumb_module

    monkeypatch.setattr(thumb_module, "DATA_DIR", tmp_path)

    ref_dir = tmp_path / "character" / "thumbnail_references"
    ref_dir.mkdir(parents=True)
    ref_file = ref_dir / "ref1.png"
    ref_file.write_bytes(b"refpng")

    monkeypatch.setattr(thumb_module, "THUMBNAIL_REFERENCES_DIR", ref_dir)

    monkeypatch.setattr(thumb_module, "_resolve_thumbnail_style_ref", lambda script_id: None)

    captured = {}

    def fake_transform(prompt, image_paths, script_id=None):
        captured["image_paths"] = list(image_paths)
        out = tmp_path / "enhanced.png"
        out.write_bytes(b"fakepng")
        return str(out)

    with patch("pipeline.character_frames.get_manifest", return_value=None), \
         patch("integrations.google_image_client.transform_with_references", fake_transform):
        base = tmp_path / "base.png"
        base.write_bytes(b"basepng")

        thumb_module.gemini_enhance_thumbnail(
            base_image_path=str(base),
            video_title="My Video",
            script_id="proj-1",
        )

    # Should be [base, ref] — no style ref appended
    assert captured.get("image_paths") is not None
    assert len(captured["image_paths"]) == 2
    assert str(base) in captured["image_paths"]
    assert str(ref_file) in captured["image_paths"]
