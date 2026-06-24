from datetime import datetime, timezone

from PIL import Image
from PIL import ImageDraw


def _full_anchor(*, left_eye=None, right_eye=None):
    left_eye = left_eye or {"x": 0.45, "y": 0.40, "width": 0.03, "height": 0.02}
    right_eye = right_eye or {"x": 0.55, "y": 0.40, "width": 0.03, "height": 0.02}
    return {
        "detected": True,
        "skin_fill": "#F0D2B4",
        "eye_left": left_eye,
        "eye_right": right_eye,
        "mouth": {"x": 0.5, "y": 0.52},
        "brow_left": {"x": left_eye["x"], "y": 0.35},
        "brow_right": {"x": right_eye["x"], "y": 0.35},
    }


def test_build_full_frame_blink_metadata_enables_every_eligible_scene(monkeypatch, tmp_path):
    from pipeline import full_frame_blink
    from pipeline.full_frame_blink import build_full_frame_blink_metadata

    image_path = tmp_path / "scene.png"
    Image.new("RGBA", (400, 300), (240, 210, 180, 255)).save(image_path)
    anchor = _full_anchor()
    monkeypatch.setattr(full_frame_blink, "image_path_from_static_url", lambda _url: image_path)
    monkeypatch.setattr(
        full_frame_blink,
        "detect_full_frame_blink_anchor",
        lambda _path: full_frame_blink.FullFrameBlinkDetection(
            status="passed", eligible=True, anchor=anchor
        ),
    )

    # No 50% deterministic gate: every eligible scene must enable blink.
    for index in range(8):
        meta = build_full_frame_blink_metadata(
            "script-1", f"scene-{index}", "/static/projects/script-1/images/x.png"
        )
        assert meta == {"enabled": True, "action": "blink", "anchor": anchor}


def test_build_full_frame_blink_metadata_suppresses_ineligible_scene(monkeypatch):
    from pipeline import full_frame_blink
    from pipeline.full_frame_blink import build_full_frame_blink_metadata

    monkeypatch.setattr(full_frame_blink, "image_path_from_static_url", lambda _url: full_frame_blink.Path("x.png"))
    monkeypatch.setattr(
        full_frame_blink,
        "detect_full_frame_blink_anchor",
        lambda _path: full_frame_blink.FullFrameBlinkDetection(
            status="failed", eligible=False, reason="blink_quality_eye_size_out_of_range"
        ),
    )

    assert build_full_frame_blink_metadata("s", "scene", "/static/projects/s/images/x.png") is None


def test_media_backed_blink_modes_only_include_render_supported_modes():
    from pipeline.full_frame_blink import MEDIA_BACKED_BLINK_MODES

    assert MEDIA_BACKED_BLINK_MODES == {"full_frame"}


def test_full_frame_blink_quality_rejects_oversized_eyes():
    from pipeline.full_frame_blink import full_frame_blink_quality_rejection_reason

    anchor = _full_anchor(
        left_eye={"x": 0.42, "y": 0.40, "width": 0.30, "height": 0.25},
        right_eye={"x": 0.58, "y": 0.40, "width": 0.30, "height": 0.25},
    )
    assert full_frame_blink_quality_rejection_reason(anchor) == "blink_quality_eye_size_out_of_range"


def test_full_frame_blink_quality_rejects_eyes_too_far_apart():
    from pipeline.full_frame_blink import full_frame_blink_quality_rejection_reason

    anchor = _full_anchor(
        left_eye={"x": 0.05, "y": 0.40, "width": 0.03, "height": 0.02},
        right_eye={"x": 0.95, "y": 0.40, "width": 0.03, "height": 0.02},
    )
    assert full_frame_blink_quality_rejection_reason(anchor) == "blink_quality_eye_separation_out_of_range"


def test_full_frame_blink_quality_rejects_eyes_too_close():
    from pipeline.full_frame_blink import full_frame_blink_quality_rejection_reason

    anchor = _full_anchor(
        left_eye={"x": 0.495, "y": 0.40, "width": 0.03, "height": 0.02},
        right_eye={"x": 0.505, "y": 0.40, "width": 0.03, "height": 0.02},
    )
    assert full_frame_blink_quality_rejection_reason(anchor) == "blink_quality_eye_separation_out_of_range"


def test_full_frame_blink_quality_rejects_overlay_that_would_span_nose():
    from pipeline.full_frame_blink import full_frame_blink_quality_rejection_reason

    # Eyes nearly as wide as the gap between them: the closed-eye marks would
    # reach across the nose, so the anchor must be suppressed.
    anchor = _full_anchor(
        left_eye={"x": 0.46, "y": 0.40, "width": 0.10, "height": 0.02},
        right_eye={"x": 0.54, "y": 0.40, "width": 0.10, "height": 0.02},
    )
    assert full_frame_blink_quality_rejection_reason(anchor) == "blink_quality_overlay_would_span_nose"


def test_full_frame_blink_quality_accepts_a_safe_anchor():
    from pipeline.full_frame_blink import full_frame_blink_quality_rejection_reason

    assert full_frame_blink_quality_rejection_reason(_full_anchor()) == ""


def test_full_frame_eye_erase_box_stays_well_inside_face_half():
    from pipeline.full_frame_blink import _full_frame_eye_erase_box

    face = {
        "left": 0.3, "right": 0.7, "top": 0.2, "bottom": 0.8,
        "width": 0.4, "height": 0.6, "cx": 0.5, "cy": 0.5, "area": 1.0,
    }
    eye = {
        "left": 0.36, "right": 0.46, "top": 0.30, "bottom": 0.42,
        "cx": 0.41, "cy": 0.36, "width": 0.10, "height": 0.12, "area": 1.0,
    }

    box = _full_frame_eye_erase_box(eye, face)

    assert box["right"] - box["left"] <= face["width"] * 0.22 + 1e-9
    assert box["bottom"] - box["top"] <= face["height"] * 0.18 + 1e-9


def test_detect_full_frame_blink_anchor_rejects_missing_file(tmp_path):
    from pipeline.full_frame_blink import detect_full_frame_blink_anchor

    result = detect_full_frame_blink_anchor(tmp_path / "missing.png")

    assert result.eligible is False
    assert result.status == "failed"
    assert result.reason == "image_missing"


def test_detect_full_frame_blink_anchor_accepts_existing_detector_anchor(monkeypatch, tmp_path):
    from pipeline import full_frame_blink
    from pipeline.full_frame_blink import detect_full_frame_blink_anchor

    image_path = tmp_path / "scene.png"
    Image.new("RGBA", (400, 300), (240, 210, 180, 255)).save(image_path)
    anchor = {
        "version": 1,
        "detected": True,
        "coordinate_space": "normalized_image",
        "skin_fill": "#F0D2B4",
        "eye_left": {"x": 0.45, "y": 0.4, "width": 0.03, "height": 0.02},
        "eye_right": {"x": 0.55, "y": 0.4, "width": 0.03, "height": 0.02},
        "mouth": {"x": 0.5, "y": 0.52},
        "brow_left": {"x": 0.45, "y": 0.35},
        "brow_right": {"x": 0.55, "y": 0.35},
    }
    monkeypatch.setattr(
        full_frame_blink,
        "_detect_full_frame_main_face_anchor_points",
        lambda _image: {
            "eye_left": anchor["eye_left"],
            "eye_right": anchor["eye_right"],
            "mouth": anchor["mouth"],
            "brow_left": anchor["brow_left"],
            "brow_right": anchor["brow_right"],
        },
    )
    monkeypatch.setattr(full_frame_blink, "_sample_blink_face_skin_fill", lambda *_args, **_kwargs: "#F0D2B4")

    result = detect_full_frame_blink_anchor(image_path)

    assert result.eligible is True
    assert result.status == "passed"
    assert result.anchor == anchor
    assert result.reason == ""


def test_detect_full_frame_blink_anchor_keeps_full_image_coordinates(monkeypatch, tmp_path):
    from pipeline import full_frame_blink
    from pipeline.full_frame_blink import detect_full_frame_blink_anchor

    image_path = tmp_path / "wide-scene.png"
    Image.new("RGBA", (1920, 1080), (240, 210, 180, 255)).save(image_path)
    detected = {
        "eye_left": {"x": 0.40, "y": 0.24, "width": 0.02, "height": 0.015},
        "eye_right": {"x": 0.48, "y": 0.24, "width": 0.02, "height": 0.015},
        "mouth": {"x": 0.44, "y": 0.34},
        "brow_left": {"x": 0.40, "y": 0.20},
        "brow_right": {"x": 0.48, "y": 0.20},
    }
    monkeypatch.setattr(full_frame_blink, "_detect_full_frame_main_face_anchor_points", lambda _image: detected)
    monkeypatch.setattr(full_frame_blink, "_sample_blink_face_skin_fill", lambda *_args, **_kwargs: "#F0D2B4")

    result = detect_full_frame_blink_anchor(image_path)

    assert result.eligible is True
    assert result.anchor is not None
    assert result.anchor["coordinate_space"] == "normalized_image"
    assert result.anchor["eye_left"]["y"] == 0.24
    assert result.anchor["eye_right"]["x"] == 0.48


def test_detect_full_frame_blink_anchor_rejects_misaligned_eye_pair(monkeypatch, tmp_path):
    from pipeline import full_frame_blink
    from pipeline.full_frame_blink import detect_full_frame_blink_anchor

    image_path = tmp_path / "misaligned-eyes.png"
    Image.new("RGBA", (1000, 560), (240, 210, 180, 255)).save(image_path)
    detected = {
        "eye_left": {"x": 0.5015, "y": 0.3282, "width": 0.0323, "height": 0.0601},
        "eye_right": {"x": 0.5495, "y": 0.3503, "width": 0.0354, "height": 0.0638},
        "mouth": {"x": 0.5199, "y": 0.4208},
        "brow_left": {"x": 0.5015, "y": 0.2953},
        "brow_right": {"x": 0.5495, "y": 0.2953},
    }
    monkeypatch.setattr(full_frame_blink, "_detect_full_frame_main_face_anchor_points", lambda _image: detected)
    monkeypatch.setattr(full_frame_blink, "_sample_blink_face_skin_fill", lambda *_args, **_kwargs: "#F0D2B4")

    result = detect_full_frame_blink_anchor(image_path)

    assert result.eligible is False
    assert result.reason == "blink_quality_eye_pair_misaligned"


def test_detect_full_frame_blink_anchor_rejects_asymmetric_detected_anchor(monkeypatch, tmp_path):
    from pipeline import full_frame_blink
    from pipeline.full_frame_blink import detect_full_frame_blink_anchor

    image_path = tmp_path / "anchor-asymmetry.png"
    Image.new("RGBA", (1000, 560), (240, 210, 180, 255)).save(image_path)
    detected = {
        "eye_left": {"x": 0.4577, "y": 0.3273, "width": 0.0146, "height": 0.0346},
        "eye_right": {"x": 0.4992, "y": 0.3310, "width": 0.0083, "height": 0.0146},
        "mouth": {"x": 0.4728, "y": 0.3994},
        "brow_left": {"x": 0.4577, "y": 0.2870},
        "brow_right": {"x": 0.4992, "y": 0.2870},
    }
    monkeypatch.setattr(full_frame_blink, "_detect_full_frame_main_face_anchor_points", lambda _image: detected)
    monkeypatch.setattr(full_frame_blink, "_sample_blink_face_skin_fill", lambda *_args, **_kwargs: "#F0D2B4")

    result = detect_full_frame_blink_anchor(image_path)

    assert result.eligible is False
    assert result.reason == "blink_quality_eye_pair_asymmetric"


def test_detect_full_frame_blink_anchor_accepts_symmetric_dot_eye_anchor(monkeypatch, tmp_path):
    from pipeline import full_frame_blink
    from pipeline.full_frame_blink import detect_full_frame_blink_anchor

    image_path = tmp_path / "good-dot-eyes.png"
    Image.new("RGBA", (1000, 560), (240, 210, 180, 255)).save(image_path)
    detected = {
        "eye_left": {"x": 0.4011, "y": 0.2435, "width": 0.0073, "height": 0.0109},
        "eye_right": {"x": 0.4427, "y": 0.2433, "width": 0.0073, "height": 0.0109},
        "mouth": {"x": 0.4202, "y": 0.2872},
        "brow_left": {"x": 0.4011, "y": 0.2124},
        "brow_right": {"x": 0.4427, "y": 0.2124},
    }
    monkeypatch.setattr(full_frame_blink, "_detect_full_frame_main_face_anchor_points", lambda _image: detected)
    monkeypatch.setattr(full_frame_blink, "_sample_blink_face_skin_fill", lambda *_args, **_kwargs: "#F0D2B4")

    result = detect_full_frame_blink_anchor(image_path)

    assert result.eligible is True
    assert result.anchor is not None
    assert result.anchor["eye_left"]["x"] == 0.4011


def test_detect_full_frame_blink_anchor_detects_off_center_cartoon_face(tmp_path):
    from pipeline.full_frame_blink import detect_full_frame_blink_anchor

    image_path = tmp_path / "off-center-face.png"
    image = Image.new("RGBA", (800, 450), (188, 205, 190, 255))
    draw = ImageDraw.Draw(image)
    draw.ellipse((120, 72, 320, 286), fill=(236, 224, 190, 255), outline=(28, 28, 28, 255), width=5)
    draw.ellipse((178, 162, 190, 174), fill=(26, 26, 26, 255))
    draw.ellipse((246, 162, 258, 174), fill=(26, 26, 26, 255))
    draw.line((210, 184, 204, 212), fill=(26, 26, 26, 255), width=4)
    draw.line((198, 238, 242, 238), fill=(26, 26, 26, 255), width=4)
    image.save(image_path)

    result = detect_full_frame_blink_anchor(image_path)

    assert result.eligible is True
    assert result.anchor is not None
    assert result.anchor["coordinate_space"] == "normalized_image"
    assert 0.20 <= result.anchor["eye_left"]["x"] <= 0.25
    assert 0.30 <= result.anchor["eye_right"]["x"] <= 0.35


def test_detect_full_frame_blink_anchor_uses_dominant_face_not_supporting_character(tmp_path):
    from pipeline.full_frame_blink import detect_full_frame_blink_anchor

    image_path = tmp_path / "two-faces.png"
    image = Image.new("RGBA", (1000, 560), (185, 190, 178, 255))
    draw = ImageDraw.Draw(image)
    draw.ellipse((330, 90, 510, 300), fill=(238, 225, 190, 255), outline=(28, 28, 28, 255), width=5)
    draw.ellipse((386, 176, 397, 188), fill=(25, 25, 25, 255))
    draw.ellipse((452, 176, 463, 188), fill=(25, 25, 25, 255))
    draw.line((418, 198, 411, 222), fill=(25, 25, 25, 255), width=4)
    draw.arc((405, 238, 455, 260), 0, 180, fill=(25, 25, 25, 255), width=4)
    draw.ellipse((670, 230, 790, 360), fill=(238, 225, 190, 255), outline=(28, 28, 28, 255), width=4)
    draw.arc((702, 280, 725, 294), 180, 360, fill=(25, 25, 25, 255), width=4)
    draw.arc((740, 280, 763, 294), 180, 360, fill=(25, 25, 25, 255), width=4)
    draw.ellipse((710, 318, 760, 348), fill=(25, 25, 25, 255))
    image.save(image_path)

    result = detect_full_frame_blink_anchor(image_path)

    assert result.eligible is True
    assert result.anchor is not None
    assert result.anchor["eye_left"]["x"] < 0.50
    assert result.anchor["eye_right"]["x"] < 0.50


def test_detect_full_frame_blink_anchor_uses_eye_whites_inside_main_face(tmp_path):
    from pipeline.full_frame_blink import detect_full_frame_blink_anchor

    image_path = tmp_path / "visor-face.png"
    image = Image.new("RGBA", (1000, 560), (185, 194, 194, 255))
    draw = ImageDraw.Draw(image)
    draw.ellipse((440, 120, 625, 325), fill=(242, 205, 164, 255), outline=(25, 25, 25, 255), width=5)
    draw.pieslice((430, 88, 640, 168), 180, 360, fill=(226, 48, 48, 255), outline=(25, 25, 25, 255), width=4)
    draw.ellipse((470, 170, 506, 224), fill=(248, 248, 246, 255), outline=(25, 25, 25, 255), width=4)
    draw.ellipse((520, 170, 558, 224), fill=(248, 248, 246, 255), outline=(25, 25, 25, 255), width=4)
    draw.ellipse((476, 194, 486, 206), fill=(20, 20, 20, 255))
    draw.ellipse((526, 194, 536, 206), fill=(20, 20, 20, 255))
    draw.arc((492, 210, 520, 252), 100, 260, fill=(25, 25, 25, 255), width=4)
    draw.arc((500, 270, 545, 288), 200, 340, fill=(25, 25, 25, 255), width=4)
    image.save(image_path)

    result = detect_full_frame_blink_anchor(image_path)

    assert result.eligible is True
    assert result.anchor is not None
    assert 0.46 <= result.anchor["eye_left"]["x"] <= 0.52
    assert 0.51 <= result.anchor["eye_right"]["x"] <= 0.57
    for key in ("eye_left", "eye_right"):
        erase_box = result.anchor[key]["erase_box"]
        assert erase_box["right"] - erase_box["left"] <= 0.07
        assert erase_box["bottom"] - erase_box["top"] <= 0.11


def test_detect_full_frame_blink_anchor_rejects_asymmetric_eye_pair(tmp_path):
    from pipeline.full_frame_blink import detect_full_frame_blink_anchor

    image_path = tmp_path / "asymmetric-eyes.png"
    image = Image.new("RGBA", (1000, 560), (188, 194, 190, 255))
    draw = ImageDraw.Draw(image)
    draw.ellipse((390, 115, 585, 330), fill=(238, 225, 190, 255), outline=(25, 25, 25, 255), width=5)
    draw.ellipse((438, 205, 449, 220), fill=(24, 24, 24, 255))
    draw.ellipse((500, 196, 548, 226), fill=(24, 24, 24, 255))
    draw.arc((440, 260, 520, 290), 190, 350, fill=(24, 24, 24, 255), width=4)
    image.save(image_path)

    result = detect_full_frame_blink_anchor(image_path)

    assert result.eligible is False
    assert result.reason == "face_landmarks_missing"


def test_detect_full_frame_blink_anchor_rejects_top_cropped_face(tmp_path):
    from pipeline.full_frame_blink import detect_full_frame_blink_anchor

    image_path = tmp_path / "top-cropped-face.png"
    image = Image.new("RGBA", (1000, 560), (56, 62, 64, 255))
    draw = ImageDraw.Draw(image)
    draw.ellipse((560, -70, 870, 210), fill=(238, 225, 190, 255), outline=(25, 25, 25, 255), width=5)
    draw.ellipse((640, 55, 652, 70), fill=(24, 24, 24, 255))
    draw.ellipse((745, 55, 757, 70), fill=(24, 24, 24, 255))
    draw.line((690, 82, 680, 128), fill=(24, 24, 24, 255), width=5)
    draw.arc((655, 150, 760, 180), 190, 350, fill=(24, 24, 24, 255), width=5)
    image.save(image_path)

    result = detect_full_frame_blink_anchor(image_path)

    assert result.eligible is False
    assert result.reason == "face_landmarks_missing"


def test_detect_full_frame_blink_anchor_rejects_busy_upper_face(tmp_path):
    from pipeline.full_frame_blink import detect_full_frame_blink_anchor

    image_path = tmp_path / "busy-upper-face.png"
    image = Image.new("RGBA", (1000, 560), (205, 170, 145, 255))
    draw = ImageDraw.Draw(image)
    draw.ellipse((395, 80, 615, 330), fill=(238, 225, 190, 255), outline=(25, 25, 25, 255), width=5)
    for y, left, right in [(112, 475, 530), (128, 455, 545), (152, 438, 478), (152, 520, 560)]:
        draw.line((left, y, right, y), fill=(24, 24, 24, 255), width=3)
    draw.ellipse((448, 190, 460, 204), fill=(24, 24, 24, 255))
    draw.ellipse((535, 190, 547, 204), fill=(24, 24, 24, 255))
    draw.line((493, 210, 484, 252), fill=(24, 24, 24, 255), width=4)
    draw.arc((462, 268, 545, 298), 190, 350, fill=(24, 24, 24, 255), width=4)
    image.save(image_path)

    result = detect_full_frame_blink_anchor(image_path)

    assert result.eligible is False
    assert result.reason == "face_landmarks_missing"


def test_run_full_frame_blink_audit_discovers_media_backed_scene(monkeypatch, tmp_path):
    from models.script import Scene, Script, ScriptContent, Segment
    from pipeline import full_frame_blink
    from pipeline.full_frame_blink import run_full_frame_blink_audit
    from sqlmodel import Session, SQLModel, create_engine
    from sqlmodel.pool import StaticPool

    import models.brand  # noqa: F401
    import models.script  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    image_dir = tmp_path / "projects" / "burger-script" / "images"
    image_dir.mkdir(parents=True)
    image_path = image_dir / "scene-1.png"
    Image.new("RGBA", (400, 300), (240, 210, 180, 255)).save(image_path)
    content = ScriptContent(
        title="Your Life At Every Level Of Working At Burger King",
        segments=[
            Segment(
                name="Level 1",
                scenes=[
                    Scene(id="title-1", narration="Title.", visual_prompt="", is_title_card=True),
                    Scene(
                        id="scene-1",
                        narration="He waits.",
                        visual_prompt="A worker character.",
                        visual_mode="full_frame",
                        image_url="/static/projects/burger-script/images/scene-1.png",
                    ),
                    Scene(id="scene-2", narration="A stat.", visual_prompt="", visual_mode="stat_card"),
                ],
            )
        ],
    )
    with Session(engine) as session:
        session.add(
            Script(
                id="burger-script",
                brand_id="default",
                format_id="life-as-a",
                topic_title="Your Life At Every Level Of Working At Burger King",
                topic_description="",
                script_json=content.model_dump_json(),
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
        monkeypatch.setattr(full_frame_blink, "DATA_DIR", tmp_path)
        monkeypatch.setattr(
            full_frame_blink,
            "detect_full_frame_blink_anchor",
            lambda _path: full_frame_blink.FullFrameBlinkDetection(
                status="passed",
                eligible=True,
                anchor={"detected": True, "skin_fill": "#F0D2B4"},
            ),
        )

        report = run_full_frame_blink_audit(session=session, script_id="burger-script")

    assert report.script_id == "burger-script"
    assert [candidate.scene_id for candidate in report.candidates] == ["scene-1"]
    assert report.candidates[0].image_url == "/static/projects/burger-script/images/scene-1.png"
    assert report.candidates[0].start_seconds >= 0.0


def test_full_frame_blink_audit_persists_report(monkeypatch, tmp_path):
    from pipeline import full_frame_blink
    from pipeline.full_frame_blink import (
        FullFrameBlinkAuditReport,
        list_blink_audit_reports,
        save_blink_audit_report,
    )

    monkeypatch.setattr(full_frame_blink, "DATA_DIR", tmp_path)
    report = FullFrameBlinkAuditReport(
        id="audit-1",
        script_id="script-1",
        title="Title",
        created_at="2026-06-21T00:00:00+00:00",
        candidates=[],
    )

    save_blink_audit_report(report)

    reports = list_blink_audit_reports()
    assert [item.id for item in reports] == ["audit-1"]
