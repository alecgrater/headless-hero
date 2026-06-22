import base64
import io
import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.pool import StaticPool
from sqlmodel import SQLModel, Session, create_engine

from api import app
from database import get_session
from models.script import Scene, Script, ScriptContent, Segment, VisualLayer


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture
def client(db_engine, tmp_path, monkeypatch):
    try:
        from api import image_review as image_review_api

        monkeypatch.setattr(image_review_api, "DATA_DIR", tmp_path)
    except ImportError:
        pass

    def override_get_session():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _png_data_url(color=(255, 0, 0, 255)) -> str:
    buffer = io.BytesIO()
    Image.new("RGBA", (2, 2), color).save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _content() -> ScriptContent:
    return ScriptContent(
        title="Image Review",
        segments=[
            Segment(
                name="Opening",
                scenes=[
                    Scene(
                        id="scene_001",
                        narration="A worker studies a broken calendar.",
                        visual_prompt="A calendar with unreadable labels.",
                        visual_mode="multi_frame",
                        image_url="/static/projects/script-1/images/scene_001.png",
                        frame_urls=[
                            "/static/projects/script-1/images/scene_001_f0.png",
                            "/static/projects/script-1/images/scene_001_f1.png",
                        ],
                        visual_layers=[
                            VisualLayer(
                                id="calendar",
                                asset_kind="panel",
                                image_url="/static/projects/script-1/popup_crops/scene_001/calendar.png",
                                prompt="calendar panel",
                            )
                        ],
                    )
                ],
            )
        ],
    )


def _insert_script(engine) -> None:
    with Session(engine) as session:
        session.add(
            Script(
                id="script-1",
                brand_id="brand-1",
                topic_title="Image Review",
                script_json=_content().model_dump_json(),
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()


def _stored_content(engine) -> ScriptContent:
    with Session(engine) as session:
        record = session.get(Script, "script-1")
        assert record is not None
        return ScriptContent.model_validate(json.loads(record.script_json))


def test_list_image_review_assets_includes_scene_frames_and_layers(client, db_engine):
    _insert_script(db_engine)

    response = client.get("/api/image-review/script-1")

    assert response.status_code == 200
    assets = response.json()["assets"]
    assert [asset["asset_id"] for asset in assets] == [
        "scene:scene_001:image",
        "scene:scene_001:frame:0",
        "scene:scene_001:frame:1",
        "scene:scene_001:layer:calendar",
    ]
    assert all("/renders/thumbnails/" not in asset["current_url"] for asset in assets)
    assert assets[1]["asset_kind"] == "frame"
    assert assets[3]["asset_kind"] == "layer"
    assert assets[0]["segment_name"] == "Opening"
    assert assets[0]["reviewed"] is False


def test_save_image_review_edit_updates_frame_url_non_destructively(client, db_engine, tmp_path):
    _insert_script(db_engine)

    response = client.post(
        "/api/image-review/script-1/assets/scene:scene_001:frame:1/edit",
        json={"data_url": _png_data_url()},
    )

    assert response.status_code == 200
    payload = response.json()
    edited_url = payload["asset"]["current_url"]
    assert edited_url.startswith("/static/projects/script-1/image_review/scene_scene_001_frame_1/edit_")
    edited_path = tmp_path / edited_url.removeprefix("/static/")
    assert edited_path.exists()

    content = _stored_content(db_engine)
    scene = content.segments[0].scenes[0]
    assert scene.frame_urls[1] == edited_url
    assert scene.frame_urls[0] == "/static/projects/script-1/images/scene_001_f0.png"
    metadata = (scene.visual_source_metadata or {})["image_review"]["assets"]["scene:scene_001:frame:1"]
    assert metadata["original_url"] == "/static/projects/script-1/images/scene_001_f1.png"
    assert metadata["reviewed"] is True


def test_reset_image_review_asset_restores_original_url(client, db_engine):
    _insert_script(db_engine)
    save_response = client.post(
        "/api/image-review/script-1/assets/scene:scene_001:frame:1/edit",
        json={"data_url": _png_data_url()},
    )
    assert save_response.status_code == 200

    response = client.post("/api/image-review/script-1/assets/scene:scene_001:frame:1/reset")

    assert response.status_code == 200
    assert response.json()["asset"]["current_url"] == "/static/projects/script-1/images/scene_001_f1.png"
    assert response.json()["asset"]["reviewed"] is False
    content = _stored_content(db_engine)
    scene = content.segments[0].scenes[0]
    assert scene.frame_urls[1] == "/static/projects/script-1/images/scene_001_f1.png"


def test_save_image_review_rejects_unknown_asset_and_invalid_data_url(client, db_engine):
    _insert_script(db_engine)

    unknown = client.post(
        "/api/image-review/script-1/assets/scene:missing:image/edit",
        json={"data_url": _png_data_url()},
    )
    invalid = client.post(
        "/api/image-review/script-1/assets/scene:scene_001:image/edit",
        json={"data_url": "data:text/plain;base64,SGVsbG8="},
    )

    assert unknown.status_code == 404
    assert invalid.status_code == 422
