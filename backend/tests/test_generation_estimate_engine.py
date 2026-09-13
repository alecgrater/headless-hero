"""Generation ETAs are scoped to the engine that will actually run the work.

A script takes ~2 minutes on Claude and ~95 on a local 27B. Pooled into one
average they produce a number that is wrong for both and converges on neither,
which is how a progress bar comes to sit at 95% for an hour.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from api import app
from database import get_session
from models.generation_duration import GenerationDuration, engine_for_operation


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def client(db_engine):
    def override():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _seed(db_engine, engine: str, seconds: float, count: int = 1) -> None:
    with Session(db_engine) as session:
        for _ in range(count):
            session.add(GenerationDuration(
                operation_type="script_generation_youtube",
                duration_seconds=seconds,
                engine=engine,
            ))
        session.commit()


def _estimate(client) -> dict:
    res = client.get("/api/generation/estimate?operation_type=script_generation_youtube")
    assert res.status_code == 200
    return res.json()


def test_a_local_estimate_ignores_cloud_history(client, db_engine, monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    cloud_engine = engine_for_operation("script_generation_youtube")
    _seed(db_engine, cloud_engine, 120.0, count=5)
    _seed(db_engine, "ollama:local-27b", 5700.0)

    assert _estimate(client)["average_seconds"] == 120.0

    monkeypatch.setattr(
        "api.generation.engine_for_operation", lambda _op: "ollama:local-27b",
    )
    local = _estimate(client)
    assert local["average_seconds"] == 5700.0, "cloud runs must not drag the local estimate down"
    assert local["engine"] == "ollama:local-27b"
    assert local["source"] == "measured"


def test_a_first_local_run_gets_the_published_baseline_not_the_cloud_average(
    client, db_engine, monkeypatch
):
    """The dangerous direction: a 95-minute wait announced as two minutes."""
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    _seed(db_engine, engine_for_operation("script_generation_youtube"), 120.0, count=5)

    monkeypatch.setattr(
        "api.generation.engine_for_operation", lambda _op: "ollama:local-27b",
    )
    estimate = _estimate(client)

    assert estimate["source"] == "baseline"
    assert estimate["sample_count"] == 0
    assert estimate["average_seconds"] > 1800, estimate


def test_an_engine_independent_operation_still_pools_every_sample(client, db_engine):
    """A Remotion render does not care which model wrote the script."""
    with Session(db_engine) as session:
        session.add(GenerationDuration(operation_type="video_render", duration_seconds=100.0))
        session.add(GenerationDuration(operation_type="video_render", duration_seconds=200.0))
        session.commit()

    res = client.get("/api/generation/estimate?operation_type=video_render")
    body = res.json()
    assert body["engine"] == ""
    assert body["sample_count"] == 2
    assert body["average_seconds"] == 150.0


def test_a_recorded_duration_is_stamped_with_the_engine(db_engine, monkeypatch):
    """The ten call sites that record a duration do not pass an engine; the
    insert listener is what keeps them scoped."""
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.delenv("LOCAL_VOICE_MODE", raising=False)
    monkeypatch.setenv("LOCAL_VOICE_MODEL", "kokoro-82m")

    with Session(db_engine) as session:
        row = GenerationDuration(operation_type="single_audio_generation", duration_seconds=3.0)
        session.add(row)
        session.commit()
        session.refresh(row)
        assert row.engine == "local:kokoro-82m"

    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    with Session(db_engine) as session:
        row = GenerationDuration(operation_type="single_audio_generation", duration_seconds=3.0)
        session.add(row)
        session.commit()
        session.refresh(row)
        assert row.engine == "cloud"


def test_an_unknown_operation_is_not_scoped(db_engine):
    with Session(db_engine) as session:
        row = GenerationDuration(operation_type="export_bundle", duration_seconds=1.0)
        session.add(row)
        session.commit()
        session.refresh(row)
        assert row.engine == ""
