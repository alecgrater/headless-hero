"""Verify Eli endpoints reject calls for projects with eli_enabled=False."""

from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool


def _build_inmemory_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Trigger imports of all model modules first
    from models import brand, project_config, script  # noqa: F401
    SQLModel.metadata.create_all(engine)
    return engine


def _setup_app(monkeypatch):
    engine = _build_inmemory_engine()

    from models.brand import BrandProfile
    from models.project_config import ProjectConfig
    from models.script import Script, ScriptContent

    with Session(engine) as session:
        session.add(
            BrandProfile(id="default", name="Default", description="d", is_default=True)
        )
        session.add(
            Script(
                id="guard-1",
                brand_id="default",
                format_id="youtube-listicle",
                topic_title="t",
                topic_description="",
                script_json=ScriptContent(title="t", segments=[]).model_dump_json(),
            )
        )
        session.add(ProjectConfig(script_id="guard-1", eli_enabled=False))
        session.commit()

    import database
    import api.scripts as scripts_module
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(scripts_module, "engine", engine)

    from api import app
    from database import get_session

    def _override_get_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = _override_get_session
    return engine, app


def test_eli_generate_rejected_when_disabled(monkeypatch):
    _, app = _setup_app(monkeypatch)
    from fastapi.testclient import TestClient
    client = TestClient(app)
    res = client.post("/api/eli/generate", json={"script_id": "guard-1"})
    assert res.status_code == 400
    assert "disabled" in res.json()["detail"].lower()

    from database import get_session
    app.dependency_overrides.pop(get_session, None)


def test_eli_regenerate_rejected_when_disabled(monkeypatch):
    _, app = _setup_app(monkeypatch)
    from fastapi.testclient import TestClient
    client = TestClient(app)
    res = client.post(
        "/api/eli/regenerate",
        json={"script_id": "guard-1", "scene_id": "any"},
    )
    assert res.status_code == 400
    assert "disabled" in res.json()["detail"].lower()

    from database import get_session
    app.dependency_overrides.pop(get_session, None)
