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
from models.generation_duration import (
    ENGINE_INDEPENDENT_OPERATIONS,
    OPERATION_ENGINE_SCOPE,
    GenerationDuration,
    engine_for_operation,
)


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


def test_every_recorded_operation_is_classified():
    """A new operation must not inherit "pooled across every engine" by omission.

    Scans the real recording sites rather than a hand-kept list, so adding a
    `GenerationDuration(operation_type="…")` anywhere forces a decision about
    whether its duration depends on a model engine.
    """
    import re
    from pathlib import Path

    backend = Path(__file__).resolve().parent.parent
    recorded: set[str] = set()
    for directory in ("api", "pipeline"):
        for path in (backend / directory).rglob("*.py"):
            recorded.update(
                re.findall(r'operation_type="([a-z0-9_]+)"', path.read_text(encoding="utf-8"))
            )

    # The browser records its own durations through POST /record-duration, so a
    # backend-only scan would pass while the timeline's two longest waits
    # (batch images, batch audio) pooled cloud and local timings together.
    frontend = backend.parent / "frontend" / "src"
    for path in list(frontend.rglob("*.ts")) + list(frontend.rglob("*.tsx")):
        if path.name.endswith((".test.ts", ".test.tsx")):
            continue
        text = path.read_text(encoding="utf-8")
        recorded.update(re.findall(r'recordDuration\(\s*"([a-z0-9_]+)"', text))
        recorded.update(re.findall(r'fetchGenerationEstimate\(\s*"([a-z0-9_]+)"', text))
        # useOperationProgress passes its operationType through to
        # recordDuration as a *variable*, so eleven of the thirteen frontend
        # types are invisible without matching the hook's own call site.
        recorded.update(re.findall(r'useOperationProgress\(\s*"([a-z0-9_]+)"', text))

    assert recorded, "found no recording sites — did the scan break?"
    classified = set(OPERATION_ENGINE_SCOPE) | set(ENGINE_INDEPENDENT_OPERATIONS)
    assert recorded <= classified, (
        "unclassified operation types: "
        f"{sorted(recorded - classified)} — add them to OPERATION_ENGINE_SCOPE "
        "or ENGINE_INDEPENDENT_OPERATIONS in models/generation_duration.py"
    )


def test_text_operations_are_scoped_to_their_own_llm_task(monkeypatch):
    """Stamping every text timing with the `script` engine would discard SEO
    history whenever SCRIPT_MODEL changed, and pool it when SEO_MODEL did."""
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    monkeypatch.setenv("SCRIPT_LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("SCRIPT_MODEL", "claude-opus-5")
    monkeypatch.setenv("SEO_LLM_PROVIDER", "openai")
    monkeypatch.setenv("SEO_MODEL", "gpt-5.6-terra")

    script_engine = engine_for_operation("script_generation_youtube")
    seo_engine = engine_for_operation("seo_generation")
    assert script_engine == "anthropic:claude-opus-5"
    assert seo_engine == "openai:gpt-5.6-terra"

    # Changing the script model must not move the SEO scope.
    monkeypatch.setenv("SCRIPT_MODEL", "claude-sonnet-5")
    assert engine_for_operation("seo_generation") == seo_engine
    assert engine_for_operation("script_generation_youtube") != script_engine


def test_image_operations_follow_the_image_provider(monkeypatch):
    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "false")
    monkeypatch.delenv("LOCAL_IMAGE_MODE", raising=False)
    cloud = engine_for_operation("single_image_generation")

    monkeypatch.setenv("LOCAL_MODELS_ENABLED", "true")
    monkeypatch.setenv("LOCAL_IMAGE_MODEL", "flux2-klein-4b")
    local = engine_for_operation("single_image_generation")

    assert cloud != local
    assert local.startswith("local:")


def test_legacy_samples_fall_back_to_a_labelled_pooled_average(client, db_engine, monkeypatch):
    """An install upgrading into engine scoping keeps a determinate bar."""
    with Session(db_engine) as session:
        session.add(GenerationDuration(
            operation_type="script_generation_youtube", duration_seconds=90.0, engine="",
        ))
        session.commit()

    monkeypatch.setattr("api.generation.engine_for_operation", lambda _op: "anthropic:claude")
    body = _estimate(client)
    assert body["source"] == "pooled"
    assert body["average_seconds"] == 90.0


def test_recording_an_unclassified_operation_is_rejected(client):
    """The browser supplies its own operation_type, so the classification
    tables cannot be enforced by scanning the backend alone."""
    res = client.post("/api/generation/record-duration", json={
        "operation_type": "something_nobody_classified",
        "duration_seconds": 1.0,
    })
    assert res.status_code == 400
    assert "OPERATION_ENGINE_SCOPE" in res.json()["detail"]


def test_recording_a_classified_operation_still_works(client):
    res = client.post("/api/generation/record-duration", json={
        "operation_type": "batch_image_generation",
        "duration_seconds": 42.0,
        "scene_count": 6,
    })
    assert res.status_code == 200, res.text
    assert res.json()["recorded"] is True


def test_a_per_scene_baseline_scales_with_the_batch(client, monkeypatch):
    """A first local title-card batch of eight is not one card's worth of wait."""
    monkeypatch.setattr("api.generation.engine_for_operation", lambda _op: "local:flux2-klein-4b")
    one = client.get(
        "/api/generation/estimate?operation_type=batch_image_generation&scene_count=1"
    ).json()
    eight = client.get(
        "/api/generation/estimate?operation_type=batch_image_generation&scene_count=8"
    ).json()

    assert one["source"] == "baseline"
    assert eight["average_seconds"] == one["average_seconds"] * 8


def test_every_scoped_llm_task_is_a_real_task():
    """A typo would fall back to the global provider and silently pool the op."""
    from integrations.llm_client import LLM_TASKS

    tasks = {task for modality, task in OPERATION_ENGINE_SCOPE.values() if task is not None}
    assert tasks <= set(LLM_TASKS), sorted(tasks - set(LLM_TASKS))

    # And a text operation always names one.
    for operation, (modality, task) in OPERATION_ENGINE_SCOPE.items():
        if modality == "text":
            assert task is not None, f"{operation} is text-scoped but names no LLM task"
