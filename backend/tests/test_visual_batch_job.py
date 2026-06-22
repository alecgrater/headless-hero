import json

from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool

from models.script import Script, ScriptContent, Scene, Segment
from models.brand import BrandProfile
from pipeline.render_jobs import get_job


def _engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _content() -> ScriptContent:
    return ScriptContent(
        title="Batch Test",
        segments=[
            Segment(
                name="Segment",
                scenes=[
                    Scene(
                        id="scene_001",
                        narration="A scene.",
                        visual_prompt="A bright classroom",
                        visual_mode="full_frame",
                    )
                ],
            )
        ],
    )


def _insert_script(session: Session, script_id: str = "script-1") -> None:
    session.add(BrandProfile(id="brand-1", name="Default"))
    session.add(
        Script(
            id=script_id,
            brand_id="brand-1",
            topic_title="Batch Test",
            script_json=_content().model_dump_json(),
            status="draft",
        )
    )
    session.commit()


def _run_background_immediately(job_id: str, target):
    from pipeline.render_jobs import update_job

    update_job(job_id, status="running")
    try:
        target()
    except Exception as exc:
        update_job(job_id, status="failed", error=str(exc))


def test_visual_batch_job_uses_standard_path_when_toggle_off(monkeypatch):
    from api import visuals as visuals_api

    engine = _engine()
    calls = {"standard": 0, "batch": 0}

    def fake_standard(*_args, **_kwargs):
        calls["standard"] += 1
        return [{"scene_id": "scene_001", "image_url": "/static/projects/script-1/images/scene_001.png", "error": None}]

    def fake_batch(*_args, **_kwargs):
        calls["batch"] += 1
        return []

    monkeypatch.setenv("GOOGLE_IMAGE_BATCH_ENABLED", "false")
    monkeypatch.setattr(visuals_api, "_require_character_reference_ready", lambda session, script_id: None)
    monkeypatch.setattr(visuals_api, "run_in_background", _run_background_immediately)
    monkeypatch.setattr(visuals_api, "generate_batch", fake_standard)
    monkeypatch.setattr(visuals_api, "generate_batch_with_google_batch", fake_batch)

    with Session(engine) as session:
        _insert_script(session)
        response = visuals_api.start_visual_batch_job(
            visuals_api.GenerateBatchRequest(
                script_id="script-1",
                scenes=[visuals_api.BatchScene(scene_id="scene_001", visual_prompt="A bright classroom")],
            ),
            session=session,
        )

    assert calls == {"standard": 1, "batch": 0}
    job = get_job(response.job_id)
    assert job is not None
    assert job.status == "completed"


def test_visual_batch_job_uses_google_batch_when_toggle_on(monkeypatch):
    from api import visuals as visuals_api

    engine = _engine()
    calls = {"standard": 0, "batch": 0}

    def fake_standard(*_args, **_kwargs):
        calls["standard"] += 1
        return []

    def fake_batch(*_args, **_kwargs):
        calls["batch"] += 1
        return [{"scene_id": "scene_001", "image_url": "/static/projects/script-1/images/scene_001.png", "error": None}]

    monkeypatch.setenv("GOOGLE_IMAGE_BATCH_ENABLED", "true")
    monkeypatch.setattr(visuals_api, "_require_character_reference_ready", lambda session, script_id: None)
    monkeypatch.setattr(visuals_api, "run_in_background", _run_background_immediately)
    monkeypatch.setattr(visuals_api, "generate_batch", fake_standard)
    monkeypatch.setattr(visuals_api, "generate_batch_with_google_batch", fake_batch)

    with Session(engine) as session:
        _insert_script(session)
        response = visuals_api.start_visual_batch_job(
            visuals_api.GenerateBatchRequest(
                script_id="script-1",
                scenes=[visuals_api.BatchScene(scene_id="scene_001", visual_prompt="A bright classroom")],
            ),
            session=session,
        )

    assert calls == {"standard": 0, "batch": 1}
    job = get_job(response.job_id)
    assert job is not None
    assert job.status == "completed"


def test_visual_batch_job_does_not_fallback_to_standard_after_batch_failure(monkeypatch):
    from api import visuals as visuals_api

    engine = _engine()
    calls = {"standard": 0, "batch": 0}

    def fake_standard(*_args, **_kwargs):
        calls["standard"] += 1
        return []

    def fake_batch(*_args, **_kwargs):
        calls["batch"] += 1
        raise RuntimeError("batch failed")

    monkeypatch.setenv("GOOGLE_IMAGE_BATCH_ENABLED", "true")
    monkeypatch.setattr(visuals_api, "_require_character_reference_ready", lambda session, script_id: None)
    monkeypatch.setattr(visuals_api, "run_in_background", _run_background_immediately)
    monkeypatch.setattr(visuals_api, "generate_batch", fake_standard)
    monkeypatch.setattr(visuals_api, "generate_batch_with_google_batch", fake_batch)

    with Session(engine) as session:
        _insert_script(session)
        response = visuals_api.start_visual_batch_job(
            visuals_api.GenerateBatchRequest(
                script_id="script-1",
                scenes=[visuals_api.BatchScene(scene_id="scene_001", visual_prompt="A bright classroom")],
            ),
            session=session,
        )

    assert calls == {"standard": 0, "batch": 1}
    job = get_job(response.job_id)
    assert job is not None
    assert job.status == "failed"
    assert "batch failed" in (job.error or "")
