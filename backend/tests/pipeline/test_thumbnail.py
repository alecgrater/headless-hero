"""Tests for long-form thumbnail helpers."""

import json
import os

from PIL import Image

from pipeline import thumbnail
from pipeline.thumbnail import (
    _EARLY_LIFE_AS_A_THUMBNAIL_LABELS,
    _LATE_LIFE_AS_A_THUMBNAIL_LABELS,
    _pick_life_as_a_thumbnail_labels,
    _read_life_as_a_thumbnail_label_sidecar,
    _write_life_as_a_thumbnail_label_sidecar,
    archive_current_longform_thumbnail,
    list_longform_thumbnails,
    replace_active_longform_thumbnail,
    write_active_longform_thumbnail,
)


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


def test_pick_life_as_a_thumbnail_labels_uses_allowed_ranges():
    seen_left: set[str] = set()
    seen_right: set[str] = set()
    for _ in range(200):
        left, right = _pick_life_as_a_thumbnail_labels()
        seen_left.add(left)
        seen_right.add(right)
        assert left in _EARLY_LIFE_AS_A_THUMBNAIL_LABELS
        assert right in _LATE_LIFE_AS_A_THUMBNAIL_LABELS
    assert seen_left == set(_EARLY_LIFE_AS_A_THUMBNAIL_LABELS)
    assert seen_right == set(_LATE_LIFE_AS_A_THUMBNAIL_LABELS)


def test_write_and_read_life_as_a_thumbnail_label_sidecar(tmp_path):
    sidecar = tmp_path / "thumb.levels.json"
    _write_life_as_a_thumbnail_label_sidecar(sidecar, "3 months in", "8 years in")
    assert _read_life_as_a_thumbnail_label_sidecar(sidecar) == (
        "3 months in",
        "8 years in",
    )


def test_read_life_as_a_thumbnail_label_sidecar_missing_returns_none(tmp_path):
    sidecar = tmp_path / "missing.json"
    assert _read_life_as_a_thumbnail_label_sidecar(sidecar) is None


def test_read_life_as_a_thumbnail_label_sidecar_corrupt_returns_none(tmp_path):
    sidecar = tmp_path / "corrupt.json"
    sidecar.write_text("not json {{{")
    assert _read_life_as_a_thumbnail_label_sidecar(sidecar) is None


def test_read_life_as_a_thumbnail_label_sidecar_missing_keys_returns_none(tmp_path):
    sidecar = tmp_path / "partial.json"
    sidecar.write_text(json.dumps({"left_label": "3 months in"}))
    assert _read_life_as_a_thumbnail_label_sidecar(sidecar) is None


def test_read_life_as_a_thumbnail_label_sidecar_rejects_legacy_levels(tmp_path):
    sidecar = tmp_path / "legacy.json"
    sidecar.write_text(json.dumps({"left_level": 1, "right_level": 4}))
    assert _read_life_as_a_thumbnail_label_sidecar(sidecar) is None


def test_longform_thumbnail_archive_preserves_previous_active(tmp_path, monkeypatch):
    monkeypatch.setattr(thumbnail, "DATA_DIR", tmp_path)
    script_id = "script-thumbs"
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    Image.new("RGB", (32, 32), (10, 20, 30)).save(first)
    Image.new("RGB", (32, 32), (200, 100, 50)).save(second)

    write_active_longform_thumbnail(script_id, first)
    archived = archive_current_longform_thumbnail(script_id)
    write_active_longform_thumbnail(script_id, second)

    assert archived is not None
    assert archived.name == "1.png"
    assert archived.read_bytes() == first.read_bytes()

    variants = list_longform_thumbnails(script_id)
    assert [idx for idx, _url in variants] == [0, 1]
    assert "thumbnails/0.png" in variants[0][1]
    assert "thumbnails/1.png" in variants[1][1]


def test_replace_active_longform_thumbnail_archives_under_one_helper(tmp_path, monkeypatch):
    monkeypatch.setattr(thumbnail, "DATA_DIR", tmp_path)
    script_id = "script-replace"
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    third = tmp_path / "third.png"
    Image.new("RGB", (32, 32), (10, 20, 30)).save(first)
    Image.new("RGB", (32, 32), (200, 100, 50)).save(second)
    Image.new("RGB", (32, 32), (50, 150, 200)).save(third)

    write_active_longform_thumbnail(script_id, first)
    replace_active_longform_thumbnail(script_id, second)
    replace_active_longform_thumbnail(script_id, third)

    thumbs_dir = tmp_path / "projects" / script_id / "renders" / "thumbnails"
    assert (thumbs_dir / "0.png").read_bytes() == third.read_bytes()
    assert (thumbs_dir / "1.png").read_bytes() == first.read_bytes()
    assert (thumbs_dir / "2.png").read_bytes() == second.read_bytes()


def test_enhance_split_progression_calls_gemini_with_templated_prompt(tmp_path, monkeypatch):
    clean_path = tmp_path / "clean.png"
    output_path = tmp_path / "final.png"
    Image.new("RGB", (32, 32), (10, 20, 30)).save(clean_path)

    captured: dict[str, object] = {}

    def fake_transform(prompt: str, image_paths: list[str], script_id: str | None = None) -> str:
        captured["prompt"] = prompt
        captured["image_paths"] = image_paths
        # Simulate Gemini producing a temp output
        result = tmp_path / "gemini_temp.png"
        Image.new("RGB", (32, 32), (200, 100, 50)).save(result)
        return str(result)

    monkeypatch.setattr("integrations.google_image_client.transform_with_references", fake_transform)

    result = thumbnail.enhance_split_progression(
        clean_image_path=clean_path,
        output_path=output_path,
        left_label="3 months in",
        right_label="8 years in",
        script_id="script-1",
    )

    assert result == output_path
    assert output_path.exists()
    assert "3 months in" in captured["prompt"]
    assert "8 years in" in captured["prompt"]
    assert "LEVEL " not in captured["prompt"]
    assert "What happened between 3 months in and 8 years in" in captured["prompt"]
    assert captured["image_paths"] == [str(clean_path)]


def test_enhance_split_progression_falls_back_on_gemini_error(tmp_path, monkeypatch):
    clean_path = tmp_path / "clean.png"
    output_path = tmp_path / "final.png"
    Image.new("RGB", (32, 32), (50, 50, 50)).save(clean_path)

    def failing_transform(prompt: str, image_paths: list[str], script_id: str | None = None) -> str:
        raise RuntimeError("Gemini exploded")

    monkeypatch.setattr("integrations.google_image_client.transform_with_references", failing_transform)

    result = thumbnail.enhance_split_progression(
        clean_image_path=clean_path,
        output_path=output_path,
        left_label="4 months in",
        right_label="9 years in",
        script_id="script-1",
    )

    # Fallback: output is a copy of the clean image
    assert result == output_path
    assert output_path.exists()
    assert output_path.read_bytes() == clean_path.read_bytes()


def test_enhance_split_progression_caches_by_mtime(tmp_path, monkeypatch):
    clean_path = tmp_path / "clean.png"
    output_path = tmp_path / "final.png"
    Image.new("RGB", (32, 32), (10, 20, 30)).save(clean_path)

    call_count = {"n": 0}

    def fake_transform(prompt: str, image_paths: list[str], script_id: str | None = None) -> str:
        call_count["n"] += 1
        result = tmp_path / f"gemini_{call_count['n']}.png"
        Image.new("RGB", (32, 32), (call_count["n"] * 10, 0, 0)).save(result)
        return str(result)

    monkeypatch.setattr("integrations.google_image_client.transform_with_references", fake_transform)

    # First call generates
    thumbnail.enhance_split_progression(
        clean_image_path=clean_path,
        output_path=output_path,
        left_label="3 months in",
        right_label="8 years in",
        script_id="s1",
    )
    assert call_count["n"] == 1

    # Second call with unchanged source uses cache
    thumbnail.enhance_split_progression(
        clean_image_path=clean_path,
        output_path=output_path,
        left_label="3 months in",
        right_label="8 years in",
        script_id="s1",
    )
    assert call_count["n"] == 1

    # Bumping source mtime invalidates cache
    new_mtime = output_path.stat().st_mtime + 10
    os.utime(clean_path, (new_mtime, new_mtime))
    thumbnail.enhance_split_progression(
        clean_image_path=clean_path,
        output_path=output_path,
        left_label="3 months in",
        right_label="8 years in",
        script_id="s1",
    )
    assert call_count["n"] == 2

    # force=True also invalidates cache
    thumbnail.enhance_split_progression(
        clean_image_path=clean_path,
        output_path=output_path,
        left_label="3 months in",
        right_label="8 years in",
        script_id="s1",
        force=True,
    )
    assert call_count["n"] == 3
