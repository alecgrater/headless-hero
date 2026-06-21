from datetime import datetime, timezone

from PIL import Image
from PIL import ImageDraw


def test_deterministic_blink_gate_is_stable_and_roughly_half():
    from pipeline.full_frame_blink import deterministic_blink_enabled

    first = deterministic_blink_enabled("script-1", "scene-1")
    assert deterministic_blink_enabled("script-1", "scene-1") is first

    enabled_count = sum(
        deterministic_blink_enabled("script-1", f"scene-{index}")
        for index in range(100)
    )
    assert 35 <= enabled_count <= 65


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
    draw.ellipse((520, 182, 558, 238), fill=(248, 248, 246, 255), outline=(25, 25, 25, 255), width=4)
    draw.ellipse((476, 194, 486, 206), fill=(20, 20, 20, 255))
    draw.ellipse((526, 206, 536, 218), fill=(20, 20, 20, 255))
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
    assert report.candidates[0].blink_enabled in {True, False}


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
