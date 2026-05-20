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


import pytest

from pipeline.thumbnail import _pick_level_pair


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
