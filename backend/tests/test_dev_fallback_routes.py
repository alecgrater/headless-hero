import json
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from dev.log_handler import DevLog
from pipeline.fallback_observability import FALLBACK_PREFIX


def test_fallback_stats_endpoint_aggregates_logs(monkeypatch, tmp_path):
    import database
    from api import app
    from dev import routes as dev_routes

    engine = create_engine(f"sqlite:///{tmp_path / 'fallbacks.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(dev_routes, "engine", engine)

    now = datetime.now(timezone.utc)
    payload = {
        "category": "visual_mode",
        "event": "ai_video_downgraded",
        "reason": "Adjacent AI-video scene",
        "severity": "warn",
        "script_id": "script-1",
        "scene_id": "scene-2",
    }
    old_payload = {
        "category": "thumbnail",
        "event": "thumbnail_enhancement_fallback",
        "reason": "Old event outside window",
        "severity": "warn",
    }

    with Session(engine) as session:
        session.add(
            DevLog(
                timestamp=now,
                level="WARNING",
                logger_name="pipeline.media_analyzer",
                message=FALLBACK_PREFIX + json.dumps(payload),
            )
        )
        session.add(
            DevLog(
                timestamp=now,
                level="WARNING",
                logger_name="pipeline.media_analyzer",
                message=FALLBACK_PREFIX + "not-json",
            )
        )
        session.add(
            DevLog(
                timestamp=now - timedelta(hours=30),
                level="WARNING",
                logger_name="pipeline.thumbnail",
                message=FALLBACK_PREFIX + json.dumps(old_payload),
            )
        )
        session.commit()

    response = TestClient(app).get("/dev/api/fallbacks/stats?hours=24")

    assert response.status_code == 200
    data = response.json()
    assert data["window_hours"] == 24
    assert data["total"] == 1
    assert data["malformed_count"] == 1
    assert data["by_category"] == [{"category": "visual_mode", "count": 1}]
    assert data["by_event"] == [
        {
            "category": "visual_mode",
            "event": "ai_video_downgraded",
            "count": 1,
            "severity": "warn",
        }
    ]
    assert data["recent"][0]["script_id"] == "script-1"
    assert data["recent"][0]["scene_id"] == "scene-2"
    assert data["recent"][0]["logger_name"] == "pipeline.media_analyzer"


def test_fallback_stats_endpoint_filters_by_category(monkeypatch, tmp_path):
    import database
    from api import app
    from dev import routes as dev_routes

    engine = create_engine(f"sqlite:///{tmp_path / 'fallbacks.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(dev_routes, "engine", engine)

    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        for category in ["visual_mode", "thumbnail"]:
            session.add(
                DevLog(
                    timestamp=now,
                    level="WARNING",
                    logger_name=f"pipeline.{category}",
                    message=FALLBACK_PREFIX
                    + json.dumps(
                        {
                            "category": category,
                            "event": f"{category}_fallback",
                            "reason": "test",
                            "severity": "warn",
                        }
                    ),
                )
            )
        session.commit()

    response = TestClient(app).get("/dev/api/fallbacks/stats?hours=24&category=thumbnail")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["by_category"] == [{"category": "thumbnail", "count": 1}]


def test_fallback_stats_endpoint_aggregates_ratio_events_beyond_recent_limit(monkeypatch, tmp_path):
    import database
    from api import app
    from dev import routes as dev_routes

    engine = create_engine(f"sqlite:///{tmp_path / 'fallbacks.db'}")
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(dev_routes, "engine", engine)
    monkeypatch.setitem(
        dev_routes.FALLBACK_OUTCOME_SPECS,
        ("visual_mode", "layered_assignment_downgraded"),
        {
            "success_event": "layered_assignment_succeeded",
            "success_logger": "pipeline.visual_treatments",
            "success_message_contains": ["[ANIMATION_TYPE]", "animation_type=popup_sequence"],
        },
    )

    now = datetime.now(timezone.utc)
    fallback_payload = {
        "category": "visual_mode",
        "event": "layered_assignment_downgraded",
        "reason": "missing action",
        "severity": "warn",
    }

    with Session(engine) as session:
        for index in range(1001):
            session.add(
                DevLog(
                    timestamp=now - timedelta(seconds=index),
                    level="WARNING",
                    logger_name="pipeline.fallback_observability",
                    message=FALLBACK_PREFIX + json.dumps(fallback_payload),
                )
            )
        session.add(
            DevLog(
                timestamp=now,
                level="INFO",
                logger_name="pipeline.visual_treatments",
                message="[ANIMATION_TYPE] scene=s1 animation_type=popup_sequence layers=3 reason=Explicit layered mode.",
            )
        )
        session.commit()

    response = TestClient(app).get("/dev/api/fallbacks/stats?hours=24&limit=5")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1001
    assert len(data["recent"]) == 5
    assert data["by_event"][0]["fallback_count"] == 1001
    assert data["by_event"][0]["success_count"] == 1
    assert data["by_event"][0]["attempt_count"] == 1002
