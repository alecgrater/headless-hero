"""Tests for persisted YOLO run history (pipeline helpers + /api/yolo endpoints)."""

import json

import pytest
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool


def _build_inmemory_engine():
    import models.brand  # noqa: F401
    import models.script  # noqa: F401
    import models.project_config  # noqa: F401
    import models.publish  # noqa: F401
    import models.credential  # noqa: F401
    import models.settings  # noqa: F401
    import models.api_usage  # noqa: F401
    import models.generation_duration  # noqa: F401
    import models.style_preset_character  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _setup_app(monkeypatch):
    engine = _build_inmemory_engine()

    from models.brand import BrandProfile

    with Session(engine) as session:
        session.add(BrandProfile(id="default", name="Default", description="d", is_default=True))
        session.commit()

    import database

    monkeypatch.setattr(database, "engine", engine)

    from api import app
    from database import get_session

    def _override_get_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _override_get_session
    return engine, app


def _seed_script(engine, script_id: str) -> None:
    from models.script import Script, ScriptContent

    content = ScriptContent(title="t", segments=[])
    with Session(engine) as session:
        session.add(
            Script(
                id=script_id,
                brand_id="default",
                topic_title="t",
                script_json=content.model_dump_json(),
            )
        )
        session.commit()


def _run(run_id: str = "run-1", script_id: str = "script-1", **overrides):
    from pipeline.yolo_runs import YoloRunRecord, YoloStageRecord

    payload = {
        "run_id": run_id,
        "script_id": script_id,
        "started_at": "2026-09-14T00:00:00+00:00",
        "status": "running",
        "stages": [
            YoloStageRecord(
                key="audio",
                label="Generate Audio",
                status="done",
                started_at="2026-09-14T00:00:00+00:00",
                ended_at="2026-09-14T00:02:00+00:00",
                attempts=1,
            )
        ],
    }
    payload.update(overrides)
    return YoloRunRecord(**payload)


# ---------------------------------------------------------------- pipeline


def test_save_and_load_round_trip():
    from pipeline import yolo_runs

    yolo_runs.save_run("script-1", _run())
    loaded = yolo_runs.load_runs("script-1")

    assert len(loaded) == 1
    assert loaded[0].run_id == "run-1"
    assert loaded[0].stages[0].key == "audio"
    assert loaded[0].stages[0].duration_seconds == pytest.approx(120.0)


def test_save_run_upserts_by_run_id():
    from pipeline import yolo_runs

    yolo_runs.save_run("script-upsert", _run(script_id="script-upsert"))
    yolo_runs.save_run(
        "script-upsert",
        _run(script_id="script-upsert", status="completed", ended_at="2026-09-14T00:05:00+00:00"),
    )

    loaded = yolo_runs.load_runs("script-upsert")
    assert len(loaded) == 1
    assert loaded[0].status == "completed"


def test_save_run_caps_history_newest_first():
    from pipeline import yolo_runs

    for idx in range(yolo_runs.MAX_RUNS + 3):
        yolo_runs.save_run(
            "script-cap",
            _run(
                run_id=f"run-{idx}",
                script_id="script-cap",
                started_at=f"2026-09-14T00:{idx:02d}:00+00:00",
            ),
        )

    loaded = yolo_runs.load_runs("script-cap")
    assert len(loaded) == yolo_runs.MAX_RUNS
    # Newest first, oldest pruned.
    newest = yolo_runs.MAX_RUNS + 2
    assert [run.run_id for run in loaded] == [
        f"run-{idx}" for idx in range(newest, newest - yolo_runs.MAX_RUNS, -1)
    ]


def test_load_runs_tolerates_corrupt_file():
    from pipeline import yolo_runs

    path = yolo_runs.runs_path("script-corrupt")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")

    assert yolo_runs.load_runs("script-corrupt") == []


def test_load_runs_skips_unparseable_entries():
    from pipeline import yolo_runs

    path = yolo_runs.runs_path("script-partial")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"runs": [{"nope": True}, _run(script_id="script-partial").model_dump(mode="json")]}),
        encoding="utf-8",
    )

    loaded = yolo_runs.load_runs("script-partial")
    assert [run.run_id for run in loaded] == ["run-1"]


def test_runs_path_rejects_traversal():
    from pipeline import yolo_runs

    with pytest.raises(ValueError):
        yolo_runs.runs_path("../escape")


def test_stage_error_is_truncated():
    from pipeline.yolo_runs import YoloStageRecord

    stage = YoloStageRecord(key="images", label="Generate Images", error="x" * 5000)
    assert len(stage.error) == YoloStageRecord.MAX_ERROR_CHARS


def test_run_rejects_absurd_stage_count():
    from pipeline.yolo_runs import YoloRunRecord, YoloStageRecord

    stages = [YoloStageRecord(key=f"s{i}", label=f"S{i}") for i in range(YoloRunRecord.MAX_STAGES + 1)]
    with pytest.raises(ValueError):
        YoloRunRecord(
            run_id="r",
            script_id="s",
            started_at="2026-09-14T00:00:00+00:00",
            stages=stages,
        )


def test_duration_seconds_none_when_unfinished():
    from pipeline.yolo_runs import YoloStageRecord

    stage = YoloStageRecord(key="fx", label="Generate FX", started_at="2026-09-14T00:00:00+00:00")
    assert stage.duration_seconds is None


def test_concurrent_saves_do_not_lose_runs():
    """save_run is a read-modify-write on a threadpool; nothing may be dropped."""
    import threading

    from pipeline import yolo_runs

    # One fewer than MAX_RUNS so nothing is legitimately pruned.
    count = yolo_runs.MAX_RUNS - 1
    barrier = threading.Barrier(count)

    def write(idx: int) -> None:
        barrier.wait()
        yolo_runs.save_run(
            "script-threads",
            _run(
                run_id=f"run-{idx}",
                script_id="script-threads",
                started_at=f"2026-09-14T00:{idx:02d}:00+00:00",
            ),
        )

    threads = [threading.Thread(target=write, args=(idx,)) for idx in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    loaded = yolo_runs.load_runs("script-threads")
    assert {run.run_id for run in loaded} == {f"run-{idx}" for idx in range(count)}


def test_concurrent_saves_of_one_run_keep_the_file_parseable():
    """Interleaved updates to a single run must never corrupt the history file."""
    import threading

    from pipeline import yolo_runs

    statuses = ["running", "completed", "halted", "cancelled", "completed_with_failures"]
    barrier = threading.Barrier(len(statuses))

    def write(status: str) -> None:
        barrier.wait()
        yolo_runs.save_run(
            "script-one-run",
            _run(run_id="run-1", script_id="script-one-run", status=status),
        )

    threads = [threading.Thread(target=write, args=(status,)) for status in statuses]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    loaded = yolo_runs.load_runs("script-one-run")
    assert len(loaded) == 1
    assert loaded[0].status in statuses


# --------------------------------------------------------------------- api


def test_put_and_get_run(monkeypatch):
    from fastapi.testclient import TestClient

    engine, app = _setup_app(monkeypatch)
    _seed_script(engine, "api-script")

    with TestClient(app) as client:
        res = client.put(
            "/api/yolo/runs/api-script",
            json={
                "run": _run(script_id="api-script").model_dump(mode="json"),
                "log": {"level": "info", "message": "YOLO stage started"},
            },
        )
        assert res.status_code == 200
        assert res.json()["run"]["run_id"] == "run-1"

        listed = client.get("/api/yolo/runs/api-script")
        assert listed.status_code == 200
        assert [run["run_id"] for run in listed.json()["runs"]] == ["run-1"]

    app.dependency_overrides.clear()


def test_put_rejects_unknown_script(monkeypatch):
    from fastapi.testclient import TestClient

    _engine, app = _setup_app(monkeypatch)

    with TestClient(app) as client:
        res = client.put(
            "/api/yolo/runs/missing",
            json={"run": _run(script_id="missing").model_dump(mode="json")},
        )
        assert res.status_code == 404

    app.dependency_overrides.clear()


def test_get_unknown_script_is_404(monkeypatch):
    from fastapi.testclient import TestClient

    _engine, app = _setup_app(monkeypatch)

    with TestClient(app) as client:
        assert client.get("/api/yolo/runs/missing").status_code == 404

    app.dependency_overrides.clear()


def test_put_rejects_script_id_mismatch(monkeypatch):
    from fastapi.testclient import TestClient

    engine, app = _setup_app(monkeypatch)
    _seed_script(engine, "api-script-2")

    with TestClient(app) as client:
        res = client.put(
            "/api/yolo/runs/api-script-2",
            json={"run": _run(script_id="some-other-script").model_dump(mode="json")},
        )
        assert res.status_code == 400

    app.dependency_overrides.clear()
