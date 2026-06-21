from datetime import datetime, timezone

from PIL import Image


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
        "detected": True,
        "coordinate_space": "normalized_layer_frame",
        "skin_fill": "#F0D2B4",
        "eye_left": {"x": 0.45, "y": 0.4, "width": 0.03, "height": 0.02},
        "eye_right": {"x": 0.55, "y": 0.4, "width": 0.03, "height": 0.02},
        "mouth": {"x": 0.5, "y": 0.52},
        "brow_left": {"x": 0.45, "y": 0.35},
        "brow_right": {"x": 0.55, "y": 0.35},
    }
    monkeypatch.setattr(full_frame_blink, "_blink_overlay_anchor_metadata", lambda *_args, **_kwargs: anchor)

    result = detect_full_frame_blink_anchor(image_path)

    assert result.eligible is True
    assert result.status == "passed"
    assert result.anchor == anchor
    assert result.reason == ""


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
