"""Blink on minimal cartoon faces wearing glasses.

The skin/eye-pair detector found 2 faces in 76 images of a stick-figure
protagonist with round glasses; the glasses path finds the lens pair. These
synthetic drawings pin the shape of that case and the false positives it must
reject.
"""

from PIL import Image, ImageDraw

from pipeline import full_frame_blink as fb

WALL = (205, 214, 200)
SKIN = (222, 216, 200)
INK = (25, 25, 25)
EYE = (95, 95, 95)
RIM = (20, 20, 60)  # distinct from INK so tests can tell the glasses rim from hair


def _glasses_face(path, *, eyes=True):
    image = Image.new("RGB", (1344, 768), WALL)
    draw = ImageDraw.Draw(image)
    draw.ellipse((520, 90, 820, 400), fill=SKIN, outline=INK, width=6)  # head
    draw.pieslice((520, 60, 820, 300), 180, 360, fill=INK)  # hair
    for cx in (620, 720):
        draw.ellipse((cx - 38, 210, cx + 38, 286), outline=RIM, width=6)  # lens rim
        if eyes:
            draw.ellipse((cx - 7, 240, cx + 7, 256), fill=EYE)  # grey eye behind glass
        draw.line((cx - 25, 190, cx + 25, 190), fill=INK, width=5)  # brow
    draw.line((658, 248, 682, 248), fill=RIM, width=6)  # bridge
    draw.line((645, 340, 695, 340), fill=INK, width=5)  # mouth
    image.save(path)
    return path


def _shirt_pockets(path):
    image = Image.new("RGB", (1344, 768), WALL)
    draw = ImageDraw.Draw(image)
    draw.rectangle((470, 150, 870, 700), fill=(196, 170, 120), outline=INK, width=6)  # tan shirt
    for cx in (600, 740):
        draw.rectangle((cx - 45, 300, cx + 45, 390), fill=SKIN, outline=INK, width=6)  # pocket
        draw.ellipse((cx - 7, 330, cx + 7, 346), fill=EYE)  # button
    image.save(path)
    return path


def test_glasses_face_is_eligible_with_eyes_on_the_dots(tmp_path):
    detection = fb.detect_full_frame_blink_anchor(_glasses_face(tmp_path / "face.png"))
    assert detection.eligible, detection.reason
    anchor = detection.anchor
    assert anchor["eye_fill_source"] == "lens"
    assert abs(anchor["eye_left"]["x"] - 620 / 1344) < 0.01
    assert abs(anchor["eye_right"]["x"] - 720 / 1344) < 0.01
    assert abs(anchor["eye_left"]["y"] - 248 / 768) < 0.015


def test_closed_eye_is_painted_with_the_lens_color_not_the_eye(tmp_path):
    anchor = fb.detect_full_frame_blink_anchor(_glasses_face(tmp_path / "face.png")).anchor
    fill = fb._hex_rgb(anchor["eye_left"]["fill_top"])
    assert fb._luminance(fill) > fb._luminance(EYE) + 60


def test_empty_glasses_are_not_a_face(tmp_path):
    assert not fb.detect_full_frame_blink_anchor(_glasses_face(tmp_path / "noeyes.png", eyes=False)).eligible


def test_outlined_pockets_with_buttons_are_not_a_face(tmp_path):
    assert not fb.detect_full_frame_blink_anchor(_shirt_pockets(tmp_path / "shirt.png")).eligible


def _skin_anchor(fill):
    eye = {"y": 0.3, "width": 0.02, "height": 0.012, "fill_top": fill}
    return {
        "detected": True,
        "skin_fill": "#ded8c8",
        "eye_left": {**eye, "x": 0.45},
        "eye_right": {**eye, "x": 0.52},
        "mouth": {"x": 0.48, "y": 0.4},
        "brow_left": {"x": 0.45, "y": 0.27},
        "brow_right": {"x": 0.52, "y": 0.27},
    }


def test_patch_that_would_show_as_grey_on_a_pale_face_is_rejected():
    assert fb.full_frame_blink_quality_rejection_reason(_skin_anchor("#959694")) == "blink_quality_fill_mismatch"
    assert fb.full_frame_blink_quality_rejection_reason(_skin_anchor("#d8d2c2")) == ""


def test_tinted_lens_fill_is_allowed_to_differ_from_the_face():
    anchor = {**_skin_anchor("#8a988e"), "eye_fill_source": "lens"}
    assert fb.full_frame_blink_quality_rejection_reason(anchor) == ""
