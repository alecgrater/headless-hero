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
    detection = _eligible_detection(project_blink_review)
    fingerprint = project_blink_review.blink_metadata_fingerprint(
        "/static/projects/script-1/images/scene_001.png",
        detection.anchor,
    )

    summary = project_blink_review.refresh_project_blink_review(content, "script-1")

    metadata = content.segments[0].scenes[0].visual_source_metadata["full_frame_blink"]
    assert summary.eligible_count == 1
    assert summary.unreviewed_count == 1
    assert metadata["enabled"] is False
    assert metadata["action"] == "blink"
    assert metadata["review"]["status"] == "unreviewed"
    assert metadata["fingerprint"]


def test_refresh_blink_review_ignores_non_full_frame_modes(monkeypatch, tmp_path):
    from pipeline import project_blink_review

    for scene_id in ("scene_multi", "scene_continuous"):
        image_path = tmp_path / "projects" / "script-1" / "images" / f"{scene_id}_f0.png"
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(b"fake")
    content = ScriptContent(
        title="Blink Review",
        segments=[
            Segment(
                name="Segment",
                scenes=[
                    Scene(
                        id="scene_multi",
                        narration="A worker turns toward a locker.",
                        visual_prompt="A worker in a hallway.",
                        visual_mode="multi_frame",
                        image_url="/static/projects/script-1/images/scene_multi_f0.png",
                        frame_urls=[
                            "/static/projects/script-1/images/scene_multi_f0.png",
                            "/static/projects/script-1/images/scene_multi_f1.png",
                        ],
                    ),
                    Scene(
                        id="scene_continuous",
                        narration="A worker waits under the fluorescent light.",
                        visual_prompt="A worker in a kitchen.",
                        visual_mode="continuous",
                        image_url="/static/projects/script-1/images/scene_continuous_f0.png",
                        frame_urls=[
                            "/static/projects/script-1/images/scene_continuous_f0.png",
                            "/static/projects/script-1/images/scene_continuous_f1.png",
                        ],
                    ),
                ],
            )
        ],
    )
    monkeypatch.setattr(project_blink_review.full_frame_blink, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        project_blink_review.full_frame_blink,
        "detect_full_frame_blink_anchor",
        lambda _path: _eligible_detection(project_blink_review),
    )

    summary = project_blink_review.refresh_project_blink_review(content, "script-1")

    assert summary.eligible_count == 0
    assert summary.candidates == []
    assert all(
        not (scene.visual_source_metadata or {}).get("full_frame_blink")
        for scene in content.segments[0].scenes
    )


def test_refresh_blink_review_clears_stale_non_full_frame_metadata():
    from pipeline import project_blink_review

    content = content_with_scene(
        Scene(
            id="scene_multi",
            narration="A worker changes frames.",
            visual_prompt="A worker in a hallway.",
            visual_mode="multi_frame",
            image_url="/static/projects/script-1/images/scene_multi_f0.png",
            visual_source_metadata={
                "full_frame_blink": {
                    "enabled": True,
                    "action": "blink",
                    "fingerprint": "stale",
                    "anchor": {"detected": True},
                    "review": {"status": "enabled"},
                },
            },
        )
    )

    summary = project_blink_review.refresh_project_blink_review(content, "script-1")

    assert summary.candidates == []
    assert content.segments[0].scenes[0].visual_source_metadata is None


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


def test_blink_review_api_returns_project_candidates(monkeypatch):
    from api.blink_review import get_blink_review
    import pipeline.project_blink_review as review
    from sqlmodel import Session, SQLModel, create_engine
    from sqlmodel.pool import StaticPool

    import models.brand  # noqa: F401
    import models.script  # noqa: F401

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    content = content_with_scene(
        Scene(
            id="scene_001",
            narration="A worker waits.",
            visual_prompt="Worker",
            visual_mode="full_frame",
            image_url="/static/projects/script-1/images/scene_001.png",
        )
    )
    monkeypatch.setattr(
        review,
        "refresh_project_blink_review",
        lambda content, script_id: review.BlinkReviewSummary(
            script_id=script_id,
            candidates=[
                review.BlinkReviewCandidate(
                    scene_id="scene_001",
                    scene_label="A worker waits.",
                    image_url="/static/projects/script-1/images/scene_001.png",
                    eligible=True,
                    fingerprint="abc",
                    review_status="unreviewed",
                )
            ],
            eligible_count=1,
            unreviewed_count=1,
            complete=False,
        ),
    )
    with Session(engine) as session:
        session.add(Script(id="script-1", brand_id="brand", script_json=content.model_dump_json(), created_at=datetime.now(timezone.utc)))
        session.commit()
        response = get_blink_review("script-1", session)

    assert response["eligible_count"] == 1
    assert response["complete"] is False


def test_blink_review_api_persists_decision(monkeypatch):
    from api.blink_review import UpdateBlinkReviewDecisionRequest, update_blink_review_decision
    from sqlmodel import Session, SQLModel, create_engine
    from sqlmodel.pool import StaticPool

    import models.brand  # noqa: F401
    import models.script  # noqa: F401

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    content = content_with_scene(
        Scene(
            id="scene_001",
            narration="A worker waits.",
            visual_prompt="Worker",
            visual_mode="full_frame",
            image_url="/static/projects/script-1/images/scene_001.png",
            visual_source_metadata={
                "full_frame_blink": {
                    "enabled": False,
                    "action": "blink",
                    "fingerprint": "abc",
                    "anchor": {"detected": True},
                    "review": {"status": "unreviewed"},
                }
            },
        )
    )
    monkeypatch.setattr(
        "pipeline.project_blink_review.refresh_project_blink_review",
        lambda content, script_id: __import__(
            "pipeline.project_blink_review",
            fromlist=["BlinkReviewSummary"],
        ).BlinkReviewSummary(script_id=script_id, candidates=[], complete=True),
    )
    with Session(engine) as session:
        session.add(Script(id="script-1", brand_id="brand", script_json=content.model_dump_json(), created_at=datetime.now(timezone.utc)))
        session.commit()
        update_blink_review_decision(
            "script-1",
            "scene_001",
            UpdateBlinkReviewDecisionRequest(status="enabled"),
            session,
        )
        stored = session.get(Script, "script-1")
        updated = ScriptContent.model_validate_json(stored.script_json)

    blink = updated.segments[0].scenes[0].visual_source_metadata["full_frame_blink"]
    assert blink["enabled"] is True
    assert blink["review"]["status"] == "enabled"


def test_validate_project_blink_review_blocks_unreviewed_scene(monkeypatch, tmp_path):
    from pipeline.project_blink_review import BlinkReviewRequiredError, validate_project_blink_review_complete

    image_path = tmp_path / "projects" / "script-1" / "images" / "scene_001.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"fake")
    from pipeline import project_blink_review

    monkeypatch.setattr(project_blink_review.full_frame_blink, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        project_blink_review.full_frame_blink,
        "detect_full_frame_blink_anchor",
        lambda _path: _eligible_detection(project_blink_review),
    )
    content = content_with_scene(
        Scene(
            id="scene_001",
            narration="A worker waits.",
            visual_prompt="Worker",
            visual_mode="full_frame",
            image_url="/static/projects/script-1/images/scene_001.png",
            visual_source_metadata={
                "full_frame_blink": {
                    "enabled": False,
                    "action": "blink",
                    "fingerprint": "abc",
                    "anchor": {"detected": True},
                    "review": {"status": "unreviewed"},
                }
            },
        )
    )

    try:
        validate_project_blink_review_complete(content, "script-1")
    except BlinkReviewRequiredError as exc:
        assert exc.summary.unreviewed_count == 1
    else:
        raise AssertionError("Expected BlinkReviewRequiredError")


def test_validate_project_blink_review_allows_reviewed_scene(monkeypatch, tmp_path):
    from pipeline.project_blink_review import validate_project_blink_review_complete

    image_path = tmp_path / "projects" / "script-1" / "images" / "scene_001.png"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"fake")
    from pipeline import project_blink_review

    monkeypatch.setattr(project_blink_review.full_frame_blink, "DATA_DIR", tmp_path)
    monkeypatch.setattr(
        project_blink_review.full_frame_blink,
        "detect_full_frame_blink_anchor",
        lambda _path: _eligible_detection(project_blink_review),
    )
    detection = _eligible_detection(project_blink_review)
    fingerprint = project_blink_review.blink_metadata_fingerprint(
        "/static/projects/script-1/images/scene_001.png",
        detection.anchor,
    )

    content = content_with_scene(
        Scene(
            id="scene_001",
            narration="A worker waits.",
            visual_prompt="Worker",
            visual_mode="full_frame",
            image_url="/static/projects/script-1/images/scene_001.png",
            visual_source_metadata={
                "full_frame_blink": {
                    "enabled": True,
                    "action": "blink",
                    "fingerprint": fingerprint,
                    "anchor": detection.anchor,
                    "review": {"status": "enabled", "reviewed_at": "2026-06-21T00:00:00+00:00"},
                }
            },
        )
    )

    summary = validate_project_blink_review_complete(content, "script-1")

    assert summary.complete is True
