"""Tests for /api/style endpoints."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from api import app
    return TestClient(app)


def test_list_presets_empty(client):
    response = client.get("/api/style/presets")
    assert response.status_code == 200
    # Initial state may be non-empty if other tests run first; just assert structure
    assert isinstance(response.json(), list)


def test_create_preset_returns_job_id(client):
    with patch("api.style.submit_preset_job", return_value="job-123") as mock_submit:
        response = client.post(
            "/api/style/presets",
            json={"prompt": "a reference sheet", "name": "test"},
        )
    assert response.status_code == 200
    assert response.json() == {"job_id": "job-123"}
    mock_submit.assert_called_once_with(prompt="a reference sheet", name="test")


def test_create_preset_rejects_empty_prompt(client):
    response = client.post(
        "/api/style/presets",
        json={"prompt": "", "name": "x"},
    )
    assert response.status_code == 400


def test_get_active_returns_null_when_unset(client):
    # Ensure unset
    client.put("/api/style/active", json={"preset_id": None})
    response = client.get("/api/style/active")
    assert response.status_code == 200
    assert response.json() is None


def test_set_active_then_get_active(client, tmp_path, monkeypatch):
    from pipeline import style_presets
    from sqlmodel import Session
    from database import engine
    from models.style_preset import StylePreset
    from datetime import datetime, timezone
    import uuid

    monkeypatch.setattr(style_presets, "DATA_DIR", tmp_path)

    # Insert a preset directly
    preset_id = f"test-preset-{uuid.uuid4().hex[:8]}"
    presets_dir = tmp_path / "style" / "presets"
    presets_dir.mkdir(parents=True)
    (presets_dir / f"{preset_id}.png").write_bytes(b"fakepng")
    with Session(engine) as session:
        session.add(StylePreset(
            id=preset_id, name="Test", prompt="x",
            created_at=datetime.now(timezone.utc),
        ))
        session.commit()

    # Set active
    response = client.put("/api/style/active", json={"preset_id": preset_id})
    assert response.status_code == 200

    # Get active
    response = client.get("/api/style/active")
    assert response.status_code == 200
    body = response.json()
    assert body is not None
    assert body["id"] == preset_id

    # Cleanup
    with Session(engine) as session:
        session.delete(session.get(StylePreset, preset_id))
        session.commit()
    client.put("/api/style/active", json={"preset_id": None})


def test_delete_preset_clears_active_if_was_active(client, tmp_path, monkeypatch):
    from pipeline import style_presets
    from sqlmodel import Session
    from database import engine
    from models.style_preset import StylePreset
    from datetime import datetime, timezone
    import uuid

    monkeypatch.setattr(style_presets, "DATA_DIR", tmp_path)
    preset_id = f"delete-me-{uuid.uuid4().hex[:8]}"
    presets_dir = tmp_path / "style" / "presets"
    presets_dir.mkdir(parents=True, exist_ok=True)
    (presets_dir / f"{preset_id}.png").write_bytes(b"fakepng")
    with Session(engine) as session:
        session.add(StylePreset(id=preset_id, name="x", prompt="x",
                                 created_at=datetime.now(timezone.utc)))
        session.commit()

    client.put("/api/style/active", json={"preset_id": preset_id})

    # Delete should also clear the active id
    response = client.delete(f"/api/style/presets/{preset_id}")
    assert response.status_code == 200

    response = client.get("/api/style/active")
    assert response.json() is None
