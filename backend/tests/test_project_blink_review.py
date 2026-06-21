from datetime import datetime, timezone

from models.script import Scene, Script, ScriptContent, Segment


def content_with_scene(scene: Scene) -> ScriptContent:
    return ScriptContent(title="Blink Review", segments=[Segment(name="Segment", scenes=[scene])])


def _eligible_detection(project_blink_review):
    return project_blink_review.full_frame_blink.FullFrameBlinkDetection(
        status="passed",
        eligible=True,
        anchor={
            "detected": True,
            "skin_fill": "#F0D2B4",
            "eye_left": {"x": 0.4, "y": 0.3, "width": 0.01, "height": 0.01},
            "eye_right": {"x": 0.46, "y": 0.3, "width": 0.01, "height": 0.01},
            "mouth": {"x": 0.43, "y": 0.38, "width": 0.02, "height": 0.01},
            "brow_left": {"x": 0.4, "y": 0.26, "width": 0.02, "height": 0.004},
            "brow_right": {"x": 0.46, "y": 0.26, "width": 0.02, "height": 0.004},
        },
    )


def test_refresh_blink_review_creates_unreviewed_metadata(monkeypatch, tmp_path):
    from pipeline import project_blink_review

    image_path = tmp_path / "projects" / "script-1" / "images" / "scene_001.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"fake")
    scene = Scene(
        id="scene_001",
        narration="A worker waits.",
        visual_prompt="A worker in a kitchen.",
        visual_mode="full_frame",
        image_url="/static/projects/script-1/images/scene_001.png",
    )
    content = content_with_scene(scene)
    monkeypatch.setattr(project_blink_review.full_frame_blink, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        project_blink_review.full_frame_blink,
        "detect_full_frame_blink_anchor",
        lambda _path: _eligible_detection(project_blink_review),
    )

    summary = project_blink_review.refresh_project_blink_review(content, "script-1")

    metadata = content.segments[0].scenes[0].visual_source_metadata["full_frame_blink"]
    assert summary.eligible_count == 1
    assert summary.unreviewed_count == 1
    assert metadata["enabled"] is False
    assert metadata["action"] == "blink"
    assert metadata["review"]["status"] == "unreviewed"
    assert metadata["fingerprint"]


def test_refresh_blink_review_resets_stale_review_when_image_changes(monkeypatch, tmp_path):
    from pipeline import project_blink_review

    image_path = tmp_path / "projects" / "script-1" / "images" / "new.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"fake")
    scene = Scene(
        id="scene_001",
        narration="A worker waits.",
        visual_prompt="A worker in a kitchen.",
        visual_mode="full_frame",
        image_url="/static/projects/script-1/images/new.png",
        visual_source_metadata={
            "full_frame_blink": {
                "enabled": True,
                "action": "blink",
                "fingerprint": "old-fingerprint",
                "anchor": {"detected": True},
                "review": {"status": "enabled", "reviewed_at": "2026-06-21T00:00:00+00:00"},
            }
        },
    )
    content = content_with_scene(scene)
    monkeypatch.setattr(project_blink_review.full_frame_blink, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        project_blink_review.full_frame_blink,
        "detect_full_frame_blink_anchor",
        lambda _path: _eligible_detection(project_blink_review),
    )

    project_blink_review.refresh_project_blink_review(content, "script-1")

    metadata = content.segments[0].scenes[0].visual_source_metadata["full_frame_blink"]
    assert metadata["fingerprint"] != "old-fingerprint"
    assert metadata["enabled"] is False
    assert metadata["review"]["status"] == "unreviewed"
