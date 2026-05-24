"""Verify eli_enabled flag is plumbed through script generation into ProjectConfig."""

import uuid

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select
from fastapi.testclient import TestClient

from api import app
import database as database_module
from api import scripts as scripts_module
from models.brand import BrandProfile
from models.project_config import ProjectConfig
from models.settings import AppSetting


@pytest.fixture
def isolated_engine(monkeypatch):
    """Swap the production SQLite engine for an in-memory one and seed a default brand.

    Patches both `database.engine` and the already-imported `api.scripts.engine`
    reference, and overrides the FastAPI `get_session` dependency so request
    handlers also see the in-memory DB. Without this, the test would write
    Script + ProjectConfig rows into the dev `data/db.sqlite`.
    """
    # StaticPool ensures the same in-memory SQLite database is shared across
    # every Session opened against this engine (default NullPool would give
    # each connection its own empty :memory: DB).
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    # Seed a default brand so get_default_brand_id() inside the endpoint succeeds.
    with Session(engine) as session:
        session.add(BrandProfile(name="Test Brand"))
        session.commit()

    monkeypatch.setattr(database_module, "engine", engine)
    monkeypatch.setattr(scripts_module, "engine", engine)

    def _override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[database_module.get_session] = _override_get_session
    try:
        yield engine
    finally:
        app.dependency_overrides.pop(database_module.get_session, None)


def test_project_config_row_written_with_eli_enabled_false(monkeypatch, isolated_engine):
    """When script gen completes with eli_enabled=False, a ProjectConfig row exists."""

    def fake_run(job_id, target):
        # Run synchronously so we can assert post-state.
        target()

    monkeypatch.setattr(scripts_module, "run_in_background", fake_run)

    # Stub generate_script to avoid hitting Claude.
    def fake_generate_script(**kwargs):
        from models.script import ScriptContent, Segment

        return ScriptContent(title="t", segments=[Segment(name="seg-1", scenes=[])])

    monkeypatch.setattr(scripts_module, "generate_script", fake_generate_script)

    unique_topic = f"eli-flag-test-{uuid.uuid4().hex}"

    client = TestClient(app)
    res = client.post(
        "/api/scripts/generate",
        json={
            "topic": unique_topic,
            "format_id": "youtube-listicle",
            "eli_enabled": False,
        },
    )
    assert res.status_code == 200, res.text

    # fake_run executed synchronously, so the Script row should exist now.
    from models.script import Script

    with Session(isolated_engine) as session:
        script_row = session.exec(
            select(Script).where(Script.topic_title == unique_topic)
        ).first()
        assert script_row is not None, "Script row not written"
        cfg_row = session.exec(
            select(ProjectConfig).where(ProjectConfig.script_id == script_row.id)
        ).first()

    assert cfg_row is not None, "ProjectConfig row not written for new script"
    assert cfg_row.eli_enabled is False, f"Expected eli_enabled=False, got {cfg_row.eli_enabled}"


def test_project_config_row_defaults_to_eli_enabled_false(monkeypatch, isolated_engine):
    """Omitting eli_enabled in a new script request uses the app default of False."""

    def fake_run(job_id, target):
        target()

    monkeypatch.setattr(scripts_module, "run_in_background", fake_run)

    def fake_generate_script(**kwargs):
        from models.script import ScriptContent, Segment

        return ScriptContent(title="t", segments=[Segment(name="seg-1", scenes=[])])

    monkeypatch.setattr(scripts_module, "generate_script", fake_generate_script)

    unique_topic = f"eli-flag-default-{uuid.uuid4().hex}"

    client = TestClient(app)
    res = client.post(
        "/api/scripts/generate",
        json={
            "topic": unique_topic,
            "format_id": "youtube-listicle",
        },
    )
    assert res.status_code == 200, res.text

    from models.script import Script

    with Session(isolated_engine) as session:
        script_row = session.exec(
            select(Script).where(Script.topic_title == unique_topic)
        ).first()
        assert script_row is not None, "Script row not written"
        cfg_row = session.exec(
            select(ProjectConfig).where(ProjectConfig.script_id == script_row.id)
        ).first()

    assert cfg_row is not None, "ProjectConfig row not written for new script"
    assert cfg_row.eli_enabled is False


def test_project_config_row_uses_saved_eli_enabled_default(monkeypatch, isolated_engine):
    """Omitting eli_enabled honors the persisted ELI_ENABLED_DEFAULT setting."""

    def fake_run(job_id, target):
        target()

    monkeypatch.setattr(scripts_module, "run_in_background", fake_run)

    def fake_generate_script(**kwargs):
        from models.script import ScriptContent, Segment

        return ScriptContent(title="t", segments=[Segment(name="seg-1", scenes=[])])

    monkeypatch.setattr(scripts_module, "generate_script", fake_generate_script)

    unique_topic = f"eli-flag-saved-default-{uuid.uuid4().hex}"
    with Session(isolated_engine) as session:
        session.add(AppSetting(key="ELI_ENABLED_DEFAULT", value="true"))
        session.commit()

    client = TestClient(app)
    res = client.post(
        "/api/scripts/generate",
        json={
            "topic": unique_topic,
            "format_id": "youtube-listicle",
        },
    )
    assert res.status_code == 200, res.text

    from models.script import Script

    with Session(isolated_engine) as session:
        script_row = session.exec(
            select(Script).where(Script.topic_title == unique_topic)
        ).first()
        assert script_row is not None, "Script row not written"
        cfg_row = session.exec(
            select(ProjectConfig).where(ProjectConfig.script_id == script_row.id)
        ).first()

    assert cfg_row is not None, "ProjectConfig row not written for new script"
    assert cfg_row.eli_enabled is True
