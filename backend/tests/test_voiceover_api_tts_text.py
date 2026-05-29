"""Endpoint tests for hidden TTS-only narration preparation."""

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from models.script import Scene, Script, ScriptContent, Segment


def _client_with_script(monkeypatch, content: ScriptContent):
    import database as database_module
    from api import app

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(
            Script(
                id="script-tts",
                brand_id="brand-1",
                topic_title=content.title,
                script_json=content.model_dump_json(),
            )
        )
        session.commit()

    def _override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[database_module.get_session] = _override_get_session
    monkeypatch.setenv("ELEVENLABS_TTS_MODEL", "eleven_v3")
    monkeypatch.setenv("ELEVENLABS_STABILITY", "0.35")
    monkeypatch.setenv("ELEVENLABS_STYLE", "0.25")
    monkeypatch.setenv("ELEVENLABS_SPEED", "0.95")
    return TestClient(app), app, database_module.get_session


def test_single_voiceover_ignores_cached_dramatized_text_and_uses_saved_settings(monkeypatch):
    content = ScriptContent(
        title="Vault",
        segments=[
            Segment(
                name="Opening",
                scenes=[
                    Scene(
                        id="scene-1",
                        narration="The first lock failed.",
                        tts_narration="The first lock... FAILED!",
                        visual_prompt="A vault door",
                    )
                ],
            )
        ],
    )
    client, app, dependency = _client_with_script(monkeypatch, content)
    captured = {}

    def fake_generate_scene_audio(*, scene_id, narration, voice_id, script_id, model_id, voice_settings):
        captured.update(
            scene_id=scene_id,
            narration=narration,
            voice_id=voice_id,
            script_id=script_id,
            model_id=model_id,
            voice_settings=voice_settings,
        )
        return "/static/projects/script-tts/audio/scene-1.mp3", 1.2, [], []

    monkeypatch.setattr("api.voiceover.generate_scene_audio", fake_generate_scene_audio)

    try:
        response = client.post(
            "/api/voice/generate",
            json={
                "script_id": "script-tts",
                "scene_id": "scene-1",
                "narration": "The first lock failed.",
                "voice_id": "voice-1",
            },
        )
    finally:
        app.dependency_overrides.pop(dependency, None)

    assert response.status_code == 200
    assert captured["narration"] == "[serious] The first lock failed."
    assert captured["model_id"] == "eleven_v3"
    assert captured["voice_settings"] == {
        "stability": 0.35,
        "style": 0.25,
        "speed": 0.95,
    }


def test_batch_voiceover_keeps_title_card_framing_but_ignores_other_tts_narration(monkeypatch):
    content = ScriptContent(
        title="Vault",
        segments=[
            Segment(
                name="Opening",
                scenes=[
                    Scene(
                        id="title-1",
                        narration="The Setup",
                        tts_narration="The setup...",
                        visual_prompt="Title card",
                        is_title_card=True,
                    ),
                    Scene(
                        id="scene-1",
                        narration="The first lock failed.",
                        tts_narration="The first lock... FAILED!",
                        visual_prompt="A vault door",
                    ),
                ],
            )
        ],
    )
    client, app, dependency = _client_with_script(monkeypatch, content)
    captured = {}

    def fake_generate_batch_audio(*, scenes, voice_id, script_id, model_id, voice_settings):
        captured.update(
            scenes=scenes,
            voice_id=voice_id,
            script_id=script_id,
            model_id=model_id,
            voice_settings=voice_settings,
        )
        return [
            {
                "scene_id": item["scene_id"],
                "audio_url": f"/static/projects/script-tts/audio/{item['scene_id']}.mp3",
                "duration_seconds": 1.0,
                "word_timestamps": [],
                "phrase_timestamps": [],
                "error": None,
            }
            for item in scenes
        ]

    monkeypatch.setattr("api.voiceover.generate_batch_audio", fake_generate_batch_audio)
    try:
        response = client.post(
            "/api/voice/generate-batch",
            json={
                "script_id": "script-tts",
                "voice_id": "voice-1",
                "scenes": [
                    {"scene_id": "title-1", "narration": "stale title"},
                    {"scene_id": "scene-1", "narration": "The first lock failed."},
                ],
            },
        )
    finally:
        app.dependency_overrides.pop(dependency, None)

    assert response.status_code == 200
    assert captured["scenes"] == [
        {"scene_id": "title-1", "narration": "Level 1 — The Setup."},
        {"scene_id": "scene-1", "narration": "[serious] The first lock failed."},
    ]
