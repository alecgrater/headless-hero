"""Tests for long-form thumbnail helpers."""

import json
import os

import pytest
from PIL import Image

from pipeline import thumbnail
from pipeline.thumbnail import _pick_level_pair, _read_level_pair_sidecar, _write_level_pair_sidecar


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


def test_pick_level_pair_two_levels_is_deterministic():
    # N == 2 → only valid pair is (1, 2)
    assert _pick_level_pair(2) == (1, 2)


def test_pick_level_pair_three_levels_yields_valid_pair():
    # N == 3 → valid pairs: (1,2), (1,3), (2,3) — all have left < right and both in [1, 3]
    for _ in range(50):
        left, right = _pick_level_pair(3)
        assert 1 <= left < right <= 3
        assert (left, right) in {(1, 2), (1, 3), (2, 3)}


def test_pick_level_pair_four_levels_uses_endpoints():
    # N == 4 → left ∈ {1, 2}, right ∈ {3, 4}, left < right
    seen: set[tuple[int, int]] = set()
    for _ in range(200):
        pair = _pick_level_pair(4)
        seen.add(pair)
        left, right = pair
        assert left in {1, 2}
        assert right in {3, 4}
        assert left < right
    # Over 200 trials all 4 combinations should appear
    assert seen == {(1, 3), (1, 4), (2, 3), (2, 4)}


def test_pick_level_pair_seven_levels_uses_endpoints():
    # N == 7 → left ∈ {1, 2}, right ∈ {6, 7}, left < right
    for _ in range(50):
        left, right = _pick_level_pair(7)
        assert left in {1, 2}
        assert right in {6, 7}
        assert left < right


def test_pick_level_pair_one_level_raises():
    # N < 2 → cannot form a pair
    with pytest.raises(ValueError):
        _pick_level_pair(1)


def test_pick_level_pair_zero_raises():
    with pytest.raises(ValueError):
        _pick_level_pair(0)


def test_write_and_read_level_pair_sidecar(tmp_path):
    sidecar = tmp_path / "thumb.levels.json"
    _write_level_pair_sidecar(sidecar, 1, 4)
    assert _read_level_pair_sidecar(sidecar) == (1, 4)


def test_read_level_pair_sidecar_missing_returns_none(tmp_path):
    sidecar = tmp_path / "missing.json"
    assert _read_level_pair_sidecar(sidecar) is None


def test_read_level_pair_sidecar_corrupt_returns_none(tmp_path):
    sidecar = tmp_path / "corrupt.json"
    sidecar.write_text("not json {{{")
    assert _read_level_pair_sidecar(sidecar) is None


def test_read_level_pair_sidecar_missing_keys_returns_none(tmp_path):
    sidecar = tmp_path / "partial.json"
    sidecar.write_text(json.dumps({"left_level": 1}))
    assert _read_level_pair_sidecar(sidecar) is None


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
        left_level=1,
        right_level=4,
        script_id="script-1",
    )

    assert result == output_path
    assert output_path.exists()
    assert "LEVEL 1" in captured["prompt"]
    assert "LEVEL 4" in captured["prompt"]
    assert "What happened between Level 1 and Level 4" in captured["prompt"]
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
        left_level=1,
        right_level=4,
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
    thumbnail.enhance_split_progression(clean_image_path=clean_path, output_path=output_path, left_level=1, right_level=3, script_id="s1")
    assert call_count["n"] == 1

    # Second call with unchanged source uses cache
    thumbnail.enhance_split_progression(clean_image_path=clean_path, output_path=output_path, left_level=1, right_level=3, script_id="s1")
    assert call_count["n"] == 1

    # Bumping source mtime invalidates cache
    new_mtime = output_path.stat().st_mtime + 10
    os.utime(clean_path, (new_mtime, new_mtime))
    thumbnail.enhance_split_progression(clean_image_path=clean_path, output_path=output_path, left_level=1, right_level=3, script_id="s1")
    assert call_count["n"] == 2

    # force=True also invalidates cache
    thumbnail.enhance_split_progression(clean_image_path=clean_path, output_path=output_path, left_level=1, right_level=3, script_id="s1", force=True)
    assert call_count["n"] == 3
