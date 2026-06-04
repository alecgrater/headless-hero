"""Tests for long-form thumbnail helpers."""

import json
import os
import re
from types import SimpleNamespace

from PIL import Image

from pipeline import thumbnail
from pipeline.thumbnail import (
    _EARLY_LIFE_AS_A_THUMBNAIL_LABELS,
    _LATE_LIFE_AS_A_THUMBNAIL_LABELS,
    _pick_level_thumbnail_labels,
    _pick_life_as_a_thumbnail_labels,
    _pick_time_period_thumbnail_labels,
    _read_life_as_a_thumbnail_label_sidecar,
    _write_life_as_a_thumbnail_label_sidecar,
    archive_current_longform_thumbnail,
    list_longform_thumbnails,
    promote_longform_thumbnail,
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
        left, right = _pick_time_period_thumbnail_labels()
        seen_left.add(left)
        seen_right.add(right)
        assert left in _EARLY_LIFE_AS_A_THUMBNAIL_LABELS
        assert right in _LATE_LIFE_AS_A_THUMBNAIL_LABELS
    assert seen_left == set(_EARLY_LIFE_AS_A_THUMBNAIL_LABELS)
    assert seen_right == set(_LATE_LIFE_AS_A_THUMBNAIL_LABELS)


def test_pick_level_thumbnail_labels_respects_range_and_monotonicity():
    label_re = re.compile(r"^LEVEL (\d+)$")
    for n_levels in (2, 3, 4, 6, 10):
        seen_pairs: set[tuple[int, int]] = set()
        for _ in range(200):
            left_label, right_label = _pick_level_thumbnail_labels(n_levels)
            left_n = int(label_re.match(left_label).group(1))
            right_n = int(label_re.match(right_label).group(1))
            assert left_n in (1, 2)
            assert right_n in (n_levels - 1, n_levels)
            assert left_n < right_n
            seen_pairs.add((left_n, right_n))
        expected = {
            (l, r)
            for l in (1, 2)
            for r in (n_levels - 1, n_levels)
            if l < r
        }
        assert seen_pairs == expected


def test_unified_picker_dispatch_default_is_time_periods():
    left, right = _pick_life_as_a_thumbnail_labels()
    assert left in _EARLY_LIFE_AS_A_THUMBNAIL_LABELS
    assert right in _LATE_LIFE_AS_A_THUMBNAIL_LABELS


def test_unified_picker_dispatch_levels():
    left, right = _pick_life_as_a_thumbnail_labels(style="levels", n_levels=5)
    assert left.startswith("LEVEL ")
    assert right.startswith("LEVEL ")


def test_write_and_read_life_as_a_thumbnail_label_sidecar(tmp_path):
    sidecar = tmp_path / "thumb.levels.json"
    _write_life_as_a_thumbnail_label_sidecar(
        sidecar, "time_periods", "3 months in", "8 years in",
    )
    assert _read_life_as_a_thumbnail_label_sidecar(sidecar) == (
        "time_periods",
        "3 months in",
        "8 years in",
    )


def test_write_and_read_life_as_a_thumbnail_label_sidecar_levels(tmp_path):
    sidecar = tmp_path / "thumb.levels.json"
    _write_life_as_a_thumbnail_label_sidecar(
        sidecar, "levels", "LEVEL 1", "LEVEL 4",
    )
    assert _read_life_as_a_thumbnail_label_sidecar(sidecar) == (
        "levels",
        "LEVEL 1",
        "LEVEL 4",
    )


def test_read_life_as_a_thumbnail_label_sidecar_back_compat_no_style(tmp_path):
    """Sidecars written before the style field should be read as time_periods."""
    sidecar = tmp_path / "legacy.json"
    sidecar.write_text(json.dumps({"left_label": "3 months in", "right_label": "8 years in"}))
    assert _read_life_as_a_thumbnail_label_sidecar(sidecar) == (
        "time_periods",
        "3 months in",
        "8 years in",
    )


def test_read_life_as_a_thumbnail_label_sidecar_rejects_mismatched_style(tmp_path):
    sidecar = tmp_path / "bad.json"
    sidecar.write_text(json.dumps({
        "style": "time_periods",
        "left_label": "LEVEL 1",
        "right_label": "LEVEL 4",
    }))
    assert _read_life_as_a_thumbnail_label_sidecar(sidecar) is None


def test_read_life_as_a_thumbnail_label_sidecar_rejects_invalid_level_label(tmp_path):
    sidecar = tmp_path / "bad.json"
    sidecar.write_text(json.dumps({
        "style": "levels",
        "left_label": "level 1",  # lowercase
        "right_label": "LEVEL 4",
    }))
    assert _read_life_as_a_thumbnail_label_sidecar(sidecar) is None


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


def test_promote_longform_thumbnail_swaps_archived_into_active(tmp_path, monkeypatch):
    monkeypatch.setattr(thumbnail, "DATA_DIR", tmp_path)
    script_id = "script-promote"
    first = tmp_path / "first.png"
    second = tmp_path / "second.png"
    third = tmp_path / "third.png"
    Image.new("RGB", (32, 32), (10, 20, 30)).save(first)
    Image.new("RGB", (32, 32), (200, 100, 50)).save(second)
    Image.new("RGB", (32, 32), (50, 150, 200)).save(third)

    # Build up three variants: 0=third, 1=first, 2=second
    write_active_longform_thumbnail(script_id, first)
    replace_active_longform_thumbnail(script_id, second)
    replace_active_longform_thumbnail(script_id, third)

    thumbs_dir = tmp_path / "projects" / script_id / "renders" / "thumbnails"
    first_bytes = (thumbs_dir / "1.png").read_bytes()
    third_bytes = (thumbs_dir / "0.png").read_bytes()

    url = promote_longform_thumbnail(script_id, 1)

    # Promoted variant is now the active 0.png
    assert (thumbs_dir / "0.png").read_bytes() == first_bytes
    # Previous active was archived to the next free slot
    archived_slot = thumbs_dir / "3.png"
    assert archived_slot.is_file()
    assert archived_slot.read_bytes() == third_bytes
    # idx.png slot was consumed
    assert not (thumbs_dir / "1.png").exists()
    # Returned URL points at the active path
    assert "thumbnails/0.png" in url


def test_promote_longform_thumbnail_rejects_idx_zero(tmp_path, monkeypatch):
    monkeypatch.setattr(thumbnail, "DATA_DIR", tmp_path)
    import pytest

    with pytest.raises(ValueError):
        promote_longform_thumbnail("script-x", 0)


def test_promote_longform_thumbnail_missing_variant(tmp_path, monkeypatch):
    monkeypatch.setattr(thumbnail, "DATA_DIR", tmp_path)
    script_id = "script-missing"
    first = tmp_path / "first.png"
    Image.new("RGB", (32, 32), (10, 20, 30)).save(first)
    write_active_longform_thumbnail(script_id, first)

    import pytest

    with pytest.raises(FileNotFoundError):
        promote_longform_thumbnail(script_id, 5)


def test_enhance_split_progression_calls_gemini_with_templated_prompt(tmp_path, monkeypatch):
    clean_path = tmp_path / "clean.png"
    output_path = tmp_path / "final.png"
    Image.new("RGB", (32, 32), (10, 20, 30)).save(clean_path)

    captured: dict[str, object] = {}

    def fake_transform(
        prompt: str,
        image_paths: list[str],
        script_id: str | None = None,
    ) -> str:
        captured["prompt"] = prompt
        captured["image_paths"] = image_paths
        # Simulate Gemini producing a temp output
        result = tmp_path / "gemini_temp.png"
        Image.new("RGB", (32, 32), (200, 100, 50)).save(result)
        return str(result)

    monkeypatch.setattr(
        "integrations.google_image_client.transform_with_references",
        fake_transform,
    )

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
    # The prompt mentions "LEVEL X" only as a casing example, not as a substituted label.
    assert 'lowercase "months in" / "years in"' in captured["prompt"]
    assert "What happened between 3 months in and 8 years in" in captured["prompt"]
    assert "medium-close / waist-up framing" in captured["prompt"]
    assert "45-65% of their panel height" in captured["prompt"]
    assert "visual center of the left panel" in captured["prompt"]
    assert "visual center of the right panel" in captured["prompt"]
    assert "saturated attention-grabbing yellow" in captured["prompt"]
    assert "EXTRA-THICK BLACK OUTLINE" in captured["prompt"]
    assert "strong dark shadow" in captured["prompt"]
    assert "RIGHT PANEL READABILITY" in captured["prompt"]
    assert "never let the right side become near-black" in captured["prompt"]
    assert "roughly 18-24% of the image width" in captured["prompt"]
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

    def fake_transform(
        prompt: str,
        image_paths: list[str],
        script_id: str | None = None,
    ) -> str:
        call_count["n"] += 1
        result = tmp_path / f"gemini_{call_count['n']}.png"
        Image.new("RGB", (32, 32), (call_count["n"] * 10, 0, 0)).save(result)
        return str(result)

    monkeypatch.setattr(
        "integrations.google_image_client.transform_with_references",
        fake_transform,
    )

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


def test_enhance_split_progression_cache_invalidates_on_label_change(tmp_path, monkeypatch):
    clean_path = tmp_path / "clean.png"
    output_path = tmp_path / "final.png"
    Image.new("RGB", (32, 32), (10, 20, 30)).save(clean_path)

    call_count = {"n": 0}

    def fake_transform(
        prompt: str,
        image_paths: list[str],
        script_id: str | None = None,
    ) -> str:
        call_count["n"] += 1
        result = tmp_path / f"gemini_{call_count['n']}.png"
        Image.new("RGB", (32, 32), (call_count["n"] * 10, 0, 0)).save(result)
        return str(result)

    monkeypatch.setattr(
        "integrations.google_image_client.transform_with_references",
        fake_transform,
    )

    thumbnail.enhance_split_progression(
        clean_image_path=clean_path,
        output_path=output_path,
        left_label="3 months in",
        right_label="8 years in",
        script_id="s1",
    )
    thumbnail.enhance_split_progression(
        clean_image_path=clean_path,
        output_path=output_path,
        left_label="4 months in",
        right_label="8 years in",
        script_id="s1",
    )

    assert call_count["n"] == 2


def test_enhance_split_progression_cache_invalidates_on_prompt_change(tmp_path, monkeypatch):
    clean_path = tmp_path / "clean.png"
    output_path = tmp_path / "final.png"
    Image.new("RGB", (32, 32), (10, 20, 30)).save(clean_path)

    call_count = {"n": 0}

    def fake_transform(
        prompt: str,
        image_paths: list[str],
        script_id: str | None = None,
    ) -> str:
        call_count["n"] += 1
        result = tmp_path / f"gemini_{call_count['n']}.png"
        Image.new("RGB", (32, 32), (call_count["n"] * 10, 0, 0)).save(result)
        return str(result)

    monkeypatch.setattr(
        "integrations.google_image_client.transform_with_references",
        fake_transform,
    )
    monkeypatch.setattr(
        "prompts.SPLIT_PROGRESSION_PROMPT",
        SimpleNamespace(template="old prompt {left_label} {right_label}"),
    )
    thumbnail.enhance_split_progression(
        clean_image_path=clean_path,
        output_path=output_path,
        left_label="3 months in",
        right_label="8 years in",
        script_id="s1",
    )

    monkeypatch.setattr(
        "prompts.SPLIT_PROGRESSION_PROMPT",
        SimpleNamespace(template="new prompt {left_label} {right_label}"),
    )
    thumbnail.enhance_split_progression(
        clean_image_path=clean_path,
        output_path=output_path,
        left_label="3 months in",
        right_label="8 years in",
        script_id="s1",
    )

    assert call_count["n"] == 2
