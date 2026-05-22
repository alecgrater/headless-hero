"""Verify eli_enabled flag is plumbed through script generation into ProjectConfig."""

import uuid

from sqlmodel import Session, select
from fastapi.testclient import TestClient

from api import app
from database import engine
from models.project_config import ProjectConfig


def test_project_config_row_written_with_eli_enabled_false(monkeypatch):
    """When script gen completes with eli_enabled=False, a ProjectConfig row exists."""
    from api import scripts as scripts_module

    def fake_run(job_id, target):
        # Run synchronously so we can assert post-state.
        target()

    monkeypatch.setattr(scripts_module, "run_in_background", fake_run)

    # Stub generate_script to avoid hitting Claude.
    def fake_generate_script(**kwargs):
        from models.script import ScriptContent, Segment

        return ScriptContent(title="t", segments=[Segment(name="seg-1", scenes=[])])

    monkeypatch.setattr(scripts_module, "generate_script", fake_generate_script)

    # Skip media analysis side effects: keep flags off so the branch is skipped.
    # Also stub hook scoring path's dependency just in case.

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

    with Session(engine) as session:
        script_row = session.exec(
            select(Script).where(Script.topic_title == unique_topic)
        ).first()
        assert script_row is not None, "Script row not written"
        cfg_row = session.exec(
            select(ProjectConfig).where(ProjectConfig.script_id == script_row.id)
        ).first()

    assert cfg_row is not None, "ProjectConfig row not written for new script"
    assert cfg_row.eli_enabled is False, f"Expected eli_enabled=False, got {cfg_row.eli_enabled}"


def test_project_config_row_defaults_to_eli_enabled_true(monkeypatch):
    """Omitting eli_enabled in the request defaults to True (legacy behavior)."""
    from api import scripts as scripts_module

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

    with Session(engine) as session:
        script_row = session.exec(
            select(Script).where(Script.topic_title == unique_topic)
        ).first()
        assert script_row is not None, "Script row not written"
        cfg_row = session.exec(
            select(ProjectConfig).where(ProjectConfig.script_id == script_row.id)
        ).first()

    assert cfg_row is not None, "ProjectConfig row not written for new script"
    assert cfg_row.eli_enabled is True
