"""Tests for how the thumbnail paths handle the style preset and the Eli portal.

  1. enhance_split_progression  (cinematic-chapters) threads the style preset
     into transform_with_references' image_paths list.
  2. gemini_enhance_thumbnail   (long-form / title-card flow) inserts the Eli
     character portal only when Eli is enabled, and sends no character frame
     when Eli is disabled.

Both call sites live in pipeline.thumbnail.
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
# gemini_enhance_thumbnail gates the Eli portal on eli_enabled
# ---------------------------------------------------------------------------


def test_gemini_enhance_thumbnail_inserts_eli_when_enabled(tmp_path, monkeypatch):
    """When Eli is enabled, the Eli frame is sent and the prompt asks for a portal."""
    import pipeline.thumbnail as thumb_module

    monkeypatch.setattr(thumb_module, "DATA_DIR", tmp_path)

    ref_dir = tmp_path / "character" / "thumbnail_references"
    ref_dir.mkdir(parents=True)
    ref_file = ref_dir / "ref1.png"
    ref_file.write_bytes(b"refpng")
    monkeypatch.setattr(thumb_module, "THUMBNAIL_REFERENCES_DIR", ref_dir)

    # Eli frame on disk + a manifest that points at it.
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    eli_frame = frames_dir / "eli_thumb.png"
    eli_frame.write_bytes(b"elipng")

    class FakeCfg:
        eli_enabled = True
        style_preset_enabled = True

    captured = {}

    def fake_transform(prompt, image_paths, script_id=None):
        captured["prompt"] = prompt
        captured["image_paths"] = list(image_paths)
        out = tmp_path / "enhanced.png"
        out.write_bytes(b"fakepng")
        return str(out)

    with patch("models.project_config.get_project_config", lambda session, script_id: FakeCfg()), \
         patch("pipeline.character_frames.get_manifest", return_value={
             "frames": [{"file_open": "eli_thumb.png"}],
             "thumbnail_frames": [{"file_open": "eli_thumb.png"}],
         }), \
         patch("pipeline.character_frames.FRAMES_DIR", frames_dir), \
         patch("integrations.google_image_client.transform_with_references", fake_transform):
        base = tmp_path / "base.png"
        base.write_bytes(b"basepng")

        thumb_module.gemini_enhance_thumbnail(
            base_image_path=str(base),
            video_title="My Video",
            script_id="proj-1",
        )

    assert captured.get("image_paths") is not None, "transform_with_references was not called"
    assert str(eli_frame) in captured["image_paths"]
    assert "CHARACTER INSERTION" in captured["prompt"]


def test_gemini_enhance_thumbnail_no_portal_when_eli_disabled(tmp_path, monkeypatch):
    """When Eli is disabled, no character frame is sent and no portal is requested."""
    import pipeline.thumbnail as thumb_module

    monkeypatch.setattr(thumb_module, "DATA_DIR", tmp_path)

    ref_dir = tmp_path / "character" / "thumbnail_references"
    ref_dir.mkdir(parents=True)
    ref_file = ref_dir / "ref1.png"
    ref_file.write_bytes(b"refpng")
    monkeypatch.setattr(thumb_module, "THUMBNAIL_REFERENCES_DIR", ref_dir)

    class FakeCfg:
        eli_enabled = False
        style_preset_enabled = True

    captured = {}

    def fake_transform(prompt, image_paths, script_id=None):
        captured["prompt"] = prompt
        captured["image_paths"] = list(image_paths)
        out = tmp_path / "enhanced.png"
        out.write_bytes(b"fakepng")
        return str(out)

    # get_manifest would normally return Eli frames — assert it is never consulted
    # by making it raise if called.
    def explode():
        raise AssertionError("Eli frames must not be loaded when Eli is disabled")

    with patch("models.project_config.get_project_config", lambda session, script_id: FakeCfg()), \
         patch("pipeline.character_frames.get_manifest", side_effect=explode), \
         patch("integrations.google_image_client.transform_with_references", fake_transform):
        base = tmp_path / "base.png"
        base.write_bytes(b"basepng")

        thumb_module.gemini_enhance_thumbnail(
            base_image_path=str(base),
            video_title="My Video",
            script_id="proj-1",
        )

    # Only the base image and the reference thumbnail — no character frame.
    assert captured.get("image_paths") is not None
    assert len(captured["image_paths"]) == 2
    assert str(base) in captured["image_paths"]
    assert str(ref_file) in captured["image_paths"]
    assert "CHARACTER INSERTION" not in captured["prompt"]


# ---------------------------------------------------------------------------
# Cache invalidation: style_preset participates in the cache key
# ---------------------------------------------------------------------------


def test_enhance_split_progression_cache_busted_when_style_preset_changes(tmp_path, monkeypatch):
    """Activating or changing the style preset causes the cached output to be regenerated."""
    import json
    import pipeline.thumbnail as thumb_module

    monkeypatch.setattr(thumb_module, "DATA_DIR", tmp_path)

    call_count = {"n": 0}

    def fake_transform(prompt, image_paths, script_id=None):
        call_count["n"] += 1
        out = tmp_path / "enhanced.png"
        out.write_bytes(b"fakepng")
        return str(out)

    clean = tmp_path / "clean.png"
    clean.write_bytes(b"cleanpng")
    out_path = tmp_path / "split.png"

    style_ref_a = str(tmp_path / "preset_a.png")
    style_ref_b = str(tmp_path / "preset_b.png")
    (tmp_path / "preset_a.png").write_bytes(b"a")
    (tmp_path / "preset_b.png").write_bytes(b"b")

    # First run with preset A — should call transform
    monkeypatch.setattr(thumb_module, "_resolve_thumbnail_style_ref", lambda sid: style_ref_a)
    with patch("integrations.google_image_client.transform_with_references", fake_transform):
        thumb_module.enhance_split_progression(
            clean_image_path=clean, output_path=out_path,
            left_label="3 months in", right_label="10 years in",
            script_id="proj-1", force=False,
        )
    assert call_count["n"] == 1

    # Second run with same preset A — should cache-hit (no transform call)
    with patch("integrations.google_image_client.transform_with_references", fake_transform):
        thumb_module.enhance_split_progression(
            clean_image_path=clean, output_path=out_path,
            left_label="3 months in", right_label="10 years in",
            script_id="proj-1", force=False,
        )
    assert call_count["n"] == 1, "Should have been a cache hit, not a second Gemini call"

    # Third run with preset B — cache key changes, must regenerate
    monkeypatch.setattr(thumb_module, "_resolve_thumbnail_style_ref", lambda sid: style_ref_b)
    with patch("integrations.google_image_client.transform_with_references", fake_transform):
        thumb_module.enhance_split_progression(
            clean_image_path=clean, output_path=out_path,
            left_label="3 months in", right_label="10 years in",
            script_id="proj-1", force=False,
        )
    assert call_count["n"] == 2, "Changing the style preset should have busted the cache"
