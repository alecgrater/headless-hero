"""The closed-eye preview matches the renderer, and the vision check gates blink."""

from types import SimpleNamespace

import pytest
from PIL import Image

from pipeline import full_frame_blink as fb

# A real lens anchor from a Nano Banana 2 Lite image of the protagonist.
ANCHOR = {
    "version": 1, "detected": True, "coordinate_space": "normalized_image", "skin_fill": "#e4ddca",
    "eye_left": {"x": 0.4993, "y": 0.22, "width": 0.0063, "height": 0.0131,
                 "fill_top": "#b9c7ba", "fill_bottom": "#b9c7ba", "fill_left": "#b9c7ba", "fill_right": "#b9c7ba"},
    "eye_right": {"x": 0.5475, "y": 0.2182, "width": 0.0063, "height": 0.0131,
                  "fill_top": "#b9c8b8", "fill_bottom": "#b9c8b8", "fill_left": "#b9c8b8", "fill_right": "#b9c8b8"},
    "mouth": {"x": 0.522, "y": 0.2792}, "brow_left": {"x": 0.4993, "y": 0.1826},
    "brow_right": {"x": 0.5475, "y": 0.1826}, "eye_fill_source": "lens",
}


def test_preview_geometry_matches_the_renderer():
    """Expected values come from remotion blinkBlinkEyeOverlayGeometry for ANCHOR."""
    shapes = fb.blink_closed_eye_geometry(ANCHOR)
    expected = [
        {"x": 49.552, "y": 20.887, "w": 0.756, "h": 2.227, "sw": 0.4, "lid_x0": 49.615},
        {"x": 54.372, "y": 20.707, "w": 0.756, "h": 2.227, "sw": 0.4, "lid_x0": 54.435},
    ]
    for shape, want in zip(shapes, expected, strict=True):
        mask, lid = shape["mask"], shape["lid"]
        assert round(mask["x"], 3) == want["x"]
        assert round(mask["y"], 3) == want["y"]
        assert round(mask["width"], 3) == want["w"]
        assert round(mask["height"], 3) == want["h"]
        assert round(lid["stroke_width"], 3) == want["sw"]
        assert round(lid["start"][0], 3) == want["lid_x0"]


def test_preview_draws_over_the_eyes_only():
    base = Image.new("RGBA", (1344, 768), (228, 221, 202, 255))
    closed = fb.render_closed_eye_frame(base, ANCHOR)
    assert closed.size == base.size
    eye = (round(0.4993 * 1344), round(0.22 * 768))
    assert closed.getpixel(eye) != base.getpixel(eye)  # lid or patch drawn on the eye
    assert closed.getpixel((50, 50)) == base.getpixel((50, 50))  # nothing elsewhere


def test_no_detected_eye_size_draws_nothing():
    anchor = {**ANCHOR, "eye_left": {**ANCHOR["eye_left"], "width": 0}}
    assert fb.blink_closed_eye_geometry(anchor) == []


@pytest.fixture
def image_file(tmp_path):
    path = tmp_path / "scene.png"
    Image.new("RGB", (1344, 768), (228, 221, 202)).save(path)
    return path


def _with_judge(monkeypatch, *, available=True, answer=None, error=None):
    from integrations import vision_client

    monkeypatch.setattr(vision_client, "vision_check_available", lambda: available)

    def judge(question, images, **_kw):
        assert [label for label, _ in images] == ["Image A:", "Image B:"]
        if error:
            raise error
        return answer

    monkeypatch.setattr(vision_client, "judge_images", judge)


GOOD = {"on_the_eyes": True, "eyes_hidden": True, "looks_natural": True, "visible_patch": False, "note": "clean"}


def test_a_clean_blink_passes(monkeypatch, image_file):
    _with_judge(monkeypatch, answer=GOOD)
    assert fb.blink_vision_check(image_file, ANCHOR).passed is True


@pytest.mark.parametrize("flaw", [{"visible_patch": True}, {"on_the_eyes": False}, {"eyes_hidden": False},
                                  {"looks_natural": False}])
def test_any_flaw_fails(monkeypatch, image_file, flaw):
    _with_judge(monkeypatch, answer={**GOOD, **flaw})
    assert fb.blink_vision_check(image_file, ANCHOR).passed is False


def test_no_key_or_an_error_skips_the_check(monkeypatch, image_file):
    _with_judge(monkeypatch, available=False)
    assert fb.blink_vision_check(image_file, ANCHOR).passed is None
    _with_judge(monkeypatch, error=RuntimeError("down"))
    assert fb.blink_vision_check(image_file, ANCHOR).passed is None


def _metadata(monkeypatch, image_file, verdict):
    monkeypatch.setattr(fb, "image_path_from_static_url", lambda _url: image_file)
    monkeypatch.setattr(fb, "detect_full_frame_blink_anchor",
                        lambda _p: SimpleNamespace(eligible=True, anchor=ANCHOR))
    monkeypatch.setattr(fb, "blink_vision_check", lambda *_a, **_k: verdict)
    return fb.build_full_frame_blink_metadata("script", "scene_1", "/static/projects/x.png")


def test_a_failed_vision_check_turns_blink_off(monkeypatch, image_file):
    assert _metadata(monkeypatch, image_file, fb.BlinkVisionVerdict(passed=False, note="patch")) is None


def test_a_passed_or_skipped_check_keeps_blink_and_says_which(monkeypatch, image_file):
    assert _metadata(monkeypatch, image_file, fb.BlinkVisionVerdict(passed=True))["vision_check"] == "passed"
    assert _metadata(monkeypatch, image_file, fb.BlinkVisionVerdict(passed=None))["vision_check"] == "skipped"
