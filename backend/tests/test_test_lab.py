"""Tests for the Test Lab hidden project and run APIs."""

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool


def _build_inmemory_engine():
    import models.api_usage  # noqa: F401
    import models.brand  # noqa: F401
    import models.content_profile  # noqa: F401
    import models.credential  # noqa: F401
    import models.generation_duration  # noqa: F401
    import models.idea  # noqa: F401
    import models.project_config  # noqa: F401
    import models.publish  # noqa: F401
    import models.script  # noqa: F401
    import models.settings  # noqa: F401
    import models.style_preset  # noqa: F401
    import models.style_preset_character  # noqa: F401
    import models.trending  # noqa: F401

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def _setup_app(monkeypatch, tmp_path):
    engine = _build_inmemory_engine()

    from models.brand import BrandProfile

    with Session(engine) as session:
        session.add(BrandProfile(id="default", name="Headless Hero", description="", is_default=True))
        session.commit()

    import api.scripts as scripts_module
    import database

    try:
        import pipeline.test_lab as test_lab_module
    except ModuleNotFoundError:
        test_lab_module = None

    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(scripts_module, "engine", engine)
    if test_lab_module is not None:
        monkeypatch.setattr(test_lab_module, "DATA_DIR", tmp_path)

    from api import app
    from database import get_session

    def _override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    return engine, app


def _seed_script(engine, script_id: str, *, is_test_lab: bool, title: str | None = None):
    from models.script import Scene, Script, ScriptContent, Segment

    content = ScriptContent(
        title=f"Script {script_id}",
        segments=[
            Segment(
                name="Segment",
                scenes=[
                    Scene(
                        id=f"{script_id}-scene",
                        narration="A single line of narration.",
                        visual_prompt="A clean flat cartoon scene.",
                        duration_estimate_seconds=6,
                    )
                ],
            )
        ],
    )
    with Session(engine) as session:
        session.add(
            Script(
                id=script_id,
                brand_id="default",
                format_id="youtube-listicle",
                topic_title=title or f"Script {script_id}",
                topic_description="",
                script_json=content.model_dump_json(),
                is_test_lab=is_test_lab,
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()


def test_list_scripts_excludes_test_lab_scripts(monkeypatch, tmp_path):
    engine, app = _setup_app(monkeypatch, tmp_path)
    _seed_script(engine, "normal-1", is_test_lab=False)
    _seed_script(engine, "test-lab-1", is_test_lab=True)

    client = TestClient(app)

    from database import get_session

    try:
        response = client.get("/api/scripts")

        assert response.status_code == 200
        ids = [item["id"] for item in response.json()]
        assert ids == ["normal-1"]
    finally:
        app.dependency_overrides.pop(get_session, None)


def test_generate_dedup_ignores_recent_test_lab_scripts(monkeypatch, tmp_path):
    engine, app = _setup_app(monkeypatch, tmp_path)
    _seed_script(engine, "test-lab-same-topic", is_test_lab=True, title="Same Topic")

    import api.scripts as scripts_api
    from pipeline.render_jobs import get_job

    monkeypatch.setattr(scripts_api, "run_in_background", lambda _job_id, _fn: None)
    client = TestClient(app)

    try:
        response = client.post(
            "/api/scripts/generate",
            json={
                "topic": "Same Topic",
                "description": "",
                "format_id": "youtube-listicle",
            },
        )

        assert response.status_code == 200
        job = get_job(response.json()["job_id"])
        assert job is not None
        assert job.status == "pending"
        assert job.output_urls == []
    finally:
        from database import get_session

        app.dependency_overrides.pop(get_session, None)


def test_test_lab_presets_validate_as_script_content():
    from models.script import ScriptContent
    from pipeline.test_lab import TEST_LAB_PRESETS, build_content_from_preset

    assert len(TEST_LAB_PRESETS) == 10
    for preset in TEST_LAB_PRESETS:
        content = build_content_from_preset(preset.id, {})
        validated = ScriptContent.model_validate(content.model_dump())
        assert validated.segments
        assert validated.segments[0].scenes
        assert validated.segments[0].scenes[0].narration
        assert validated.segments[0].scenes[0].visual_prompt


def test_test_lab_scenes_endpoint_returns_presets(monkeypatch, tmp_path):
    _engine, app = _setup_app(monkeypatch, tmp_path)
    client = TestClient(app)

    try:
        response = client.get("/api/test-lab/scenes")

        assert response.status_code == 200
        data = response.json()
        assert len(data["presets"]) == 10
        assert data["presets"][0]["id"]
    finally:
        from database import get_session

        app.dependency_overrides.pop(get_session, None)


def test_test_lab_scenes_endpoint_returns_active_default_character(monkeypatch, tmp_path):
    engine, app = _setup_app(monkeypatch, tmp_path)

    import pipeline.main_character as main_character

    monkeypatch.setattr(main_character, "DATA_DIR", tmp_path)

    from models.settings import AppSetting
    from models.style_preset import StylePreset
    from models.style_preset_character import StylePresetCharacter

    preset_id = "preset-a"
    character_id = "character-a"
    (tmp_path / "style" / "presets").mkdir(parents=True)
    (tmp_path / "style" / "presets" / f"{preset_id}.png").write_bytes(b"fakepng")
    (tmp_path / "style" / "presets" / preset_id / "characters").mkdir(parents=True)
    (tmp_path / "style" / "presets" / preset_id / "characters" / f"{character_id}.png").write_bytes(b"fakepng")

    with Session(engine) as session:
        session.add(StylePreset(id=preset_id, name="House style", prompt="flat 2d"))
        session.add(
            StylePresetCharacter(
                id=character_id,
                style_preset_id=preset_id,
                name="Mara",
                appearance="A cheerful explorer in a yellow jacket.",
                vibe="Bright and curious.",
                reference_image_url=f"/static/style/presets/{preset_id}/characters/{character_id}.png",
            )
        )
        session.add(AppSetting(key="ACTIVE_STYLE_PRESET_ID", value=preset_id))
        session.add(AppSetting(key=main_character.active_style_preset_character_key(preset_id), value=character_id))
        session.commit()

    client = TestClient(app)

    try:
        response = client.get("/api/test-lab/scenes")

        assert response.status_code == 200
        data = response.json()
        assert data["default_main_character"]["name"] == "Mara"
        assert (
            data["default_main_character"]["reference_image_url"]
            == f"/static/style/presets/{preset_id}/characters/{character_id}.png"
        )
    finally:
        from database import get_session

        app.dependency_overrides.pop(get_session, None)


def test_start_test_lab_run_returns_run_and_job(monkeypatch, tmp_path):
    engine, app = _setup_app(monkeypatch, tmp_path)

    import api.test_lab as test_lab_api

    def fake_background(job_id, fn):
        fn()

    monkeypatch.setattr(test_lab_api, "run_in_background", fake_background)

    client = TestClient(app)
    try:
        response = client.post(
            "/api/test-lab/runs",
            json={
                "preset_id": "coffee-brain",
                "settings": {
                    "stages": {"audio": False, "visual": False, "render": False, "eli": False, "fx": False, "treatment_assets": False},
                },
            },
        )

        assert response.status_code == 200
        body = response.json()
        assert body["run_id"]
        assert body["job_id"]

        history = client.get("/api/test-lab/runs")
        assert history.status_code == 200
        assert history.json()["runs"][0]["preset_id"] == "coffee-brain"
    finally:
        from database import get_session

        app.dependency_overrides.pop(get_session, None)


def test_test_lab_status_includes_run_id_without_output_urls(monkeypatch, tmp_path):
    engine, app = _setup_app(monkeypatch, tmp_path)

    import api.test_lab as test_lab_api

    def fake_background(job_id, fn):
        fn()

    monkeypatch.setattr(test_lab_api, "run_in_background", fake_background)

    client = TestClient(app)
    try:
        response = client.post(
            "/api/test-lab/runs",
            json={
                "preset_id": "coffee-brain",
                "settings": {
                    "stages": {
                        "audio": False,
                        "visual": False,
                        "render": False,
                        "eli": False,
                        "fx": False,
                        "treatment_assets": False,
                    },
                },
            },
        )

        assert response.status_code == 200
        body = response.json()

        status = client.get(f"/api/test-lab/runs/status/{body['job_id']}")
        assert status.status_code == 200
        status_body = status.json()
        assert status_body["output_urls"] == []
        assert status_body["run_id"] == body["run_id"]
    finally:
        from database import get_session

        app.dependency_overrides.pop(get_session, None)


def test_test_lab_advanced_script_recomputes_ai_video_enabled():
    from pipeline.test_lab import build_content_from_preset

    content = build_content_from_preset(
        "coffee-brain",
        {
            "advanced_script": {
                "segments": [
                    {
                        "name": "The caffeine switch",
                        "scenes": [
                            {
                                "id": "coffee-brain-scene-1",
                                "narration": "Caffeine blocks the sleepy signal.",
                                "visual_prompt": "Flat 2D cartoon coffee mug powering up a brain.",
                                "media_source": "ai_video",
                            }
                        ],
                    }
                ],
            }
        },
    )

    assert content.segments[0].scenes[0].media_source == "ai_video"
    assert content.ai_video_enabled is True


def test_test_lab_preset_uses_visual_canvas_background_setting():
    from pipeline.test_lab import build_content_from_preset

    content = build_content_from_preset(
        "coffee-brain",
        {"visual_canvas": {"background_color": "#123456"}},
    )

    assert content.visual_canvas.background_color == "#123456"


def test_test_lab_preset_uses_visual_treatment_setting():
    from pipeline.test_lab import build_content_from_preset

    content = build_content_from_preset("coffee-brain", {"visual_treatment": "flipflop"})

    assert content.segments[0].scenes[0].visual_treatment == "flipflop"


def test_test_lab_advanced_script_keeps_top_level_visual_treatment_when_scene_omits_it():
    from pipeline.test_lab import build_content_from_preset

    content = build_content_from_preset(
        "coffee-brain",
        {
            "visual_treatment": "flipflop",
            "advanced_script": {
                "segments": [
                    {
                        "name": "x",
                        "scenes": [
                            {
                                "id": "adv",
                                "narration": "n",
                                "visual_prompt": "p",
                                "duration_estimate_seconds": 5,
                                "is_title_card": False,
                            }
                        ],
                    }
                ],
            },
        },
    )

    assert content.segments[0].scenes[0].visual_treatment == "flipflop"


def test_test_lab_preset_main_character_is_not_mutated_by_content():
    from pipeline.test_lab import TEST_LAB_PRESETS, build_content_from_preset

    preset = next(item for item in TEST_LAB_PRESETS if item.id == "life-scribe")
    assert preset.main_character is not None
    original_name = preset.main_character.name

    content = build_content_from_preset("life-scribe", {"main_character": preset.main_character.model_dump()})
    assert content.main_character is not None
    content.main_character.name = "Mutated Rowan"

    assert preset.main_character.name == original_name


def test_test_lab_preset_does_not_fall_back_to_dummy_character():
    from pipeline.test_lab import build_content_from_preset

    content = build_content_from_preset("life-scribe", {})

    assert content.main_character is None


def test_test_lab_rejects_unsafe_run_ids(monkeypatch, tmp_path):
    import pytest
    from pydantic import ValidationError

    import pipeline.test_lab as test_lab

    monkeypatch.setattr(test_lab, "DATA_DIR", tmp_path)

    for run_id in ("", "../oops"):
        with pytest.raises(ValidationError):
            test_lab.TestLabRunManifest(
                run_id=run_id,
                script_id="script-1",
                preset_id="life-scribe",
            )
        with pytest.raises(ValueError):
            test_lab.manifest_path(run_id)

    assert not (tmp_path / "test-lab" / "oops.json").exists()
    assert not (tmp_path / "oops.json").exists()


def test_test_lab_history_is_capped_to_20(monkeypatch, tmp_path):
    import pipeline.test_lab as test_lab

    monkeypatch.setattr(test_lab, "DATA_DIR", tmp_path)

    for i in range(25):
        manifest = test_lab.TestLabRunManifest(
            run_id=f"run-{i:02d}",
            script_id=f"script-{i:02d}",
            preset_id="life-scribe",
            status="completed",
            settings={},
        )
        test_lab.save_run_manifest(manifest)

    history = test_lab.list_run_history()

    assert len(history) == 20
    assert history[0].run_id == "run-24"
    assert history[-1].run_id == "run-05"
    assert not (tmp_path / "test-lab" / "runs" / "run-00.json").exists()


def test_create_hidden_test_script_creates_script_and_project_config(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    from models.project_config import ProjectConfig
    from models.script import Script, ScriptContent
    from pipeline.test_lab import create_hidden_test_script

    with Session(engine) as session:
        script_id = create_hidden_test_script(
            session,
            run_id="run-create",
            preset_id="life-scribe",
            settings={
                "eli_enabled": False,
                "style_preset_enabled": True,
                "main_character": {
                    "name": "Test",
                    "appearance": "cartoon explorer",
                    "vibe": "curious",
                },
            },
        )
        session.commit()

        script = session.get(Script, script_id)
        cfg = session.get(ProjectConfig, script_id)

    assert script is not None
    assert script.is_test_lab is True
    assert script.topic_title == "Your Life as a Medieval Scribe"
    assert cfg is not None
    assert cfg.eli_enabled is False
    content = ScriptContent.model_validate_json(script.script_json)
    assert content.main_character is not None
    assert content.main_character.name == "Test"


def test_create_hidden_test_script_uses_active_style_preset_character(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.main_character as main_character
    import pipeline.test_lab as test_lab
    from models.settings import AppSetting
    from models.script import Script, ScriptContent
    from models.style_preset import StylePreset
    from models.style_preset_character import StylePresetCharacter

    monkeypatch.setattr(main_character, "DATA_DIR", tmp_path)
    monkeypatch.setattr(test_lab, "DATA_DIR", tmp_path)

    preset_id = "preset-a"
    character_id = "character-a"
    (tmp_path / "style" / "presets").mkdir(parents=True)
    (tmp_path / "style" / "presets" / f"{preset_id}.png").write_bytes(b"fakepng")
    (tmp_path / "style" / "presets" / preset_id / "characters").mkdir(parents=True)
    (tmp_path / "style" / "presets" / preset_id / "characters" / f"{character_id}.png").write_bytes(b"fakepng")

    with Session(engine) as session:
        session.add(StylePreset(id=preset_id, name="House style", prompt="flat 2d"))
        session.add(
            StylePresetCharacter(
                id=character_id,
                style_preset_id=preset_id,
                name="Mara",
                appearance="A cheerful explorer in a yellow jacket.",
                vibe="Bright and curious.",
                reference_image_url=f"/static/style/presets/{preset_id}/characters/{character_id}.png",
            )
        )
        session.add(AppSetting(key="ACTIVE_STYLE_PRESET_ID", value=preset_id))
        session.add(AppSetting(key=main_character.active_style_preset_character_key(preset_id), value=character_id))
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-active-character",
            preset_id="life-scribe",
            settings={"eli_enabled": False},
        )
        session.commit()

        script = session.get(Script, script_id)

    assert script is not None
    content = ScriptContent.model_validate_json(script.script_json)
    assert content.main_character is not None
    assert content.main_character.name == "Mara"


def test_create_hidden_test_script_coerces_raw_boolean_settings(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    from models.project_config import ProjectConfig
    from pipeline.test_lab import create_hidden_test_script

    with Session(engine) as session:
        script_id = create_hidden_test_script(
            session,
            run_id="run-coerce",
            preset_id="life-scribe",
            settings={
                "eli_enabled": None,
                "style_preset_enabled": "false",
            },
        )
        session.commit()

        cfg = session.get(ProjectConfig, script_id)

    assert cfg is not None
    assert cfg.eli_enabled is True
    assert cfg.style_preset_enabled is False


def test_stage_character_reference_blocks_eli_disabled_without_selected_reference(monkeypatch, tmp_path):
    import pytest

    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.test_lab as test_lab

    with Session(engine) as session:
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-character-blocked",
            preset_id="life-scribe",
            settings={"eli_enabled": False},
        )
        session.commit()

    manifest = test_lab.TestLabRunManifest(
        run_id="run-character-blocked",
        script_id=script_id,
        preset_id="life-scribe",
        status="running",
    )
    ctx = test_lab.TestLabRunContext(
        engine=engine,
        run_id="run-character-blocked",
        script_id=script_id,
        preset_id="life-scribe",
        settings={"eli_enabled": False},
        manifest=manifest,
        job_id=None,
    )

    with pytest.raises(RuntimeError, match="Active style preset is missing"):
        test_lab._stage_character_reference(ctx)


def test_stage_character_reference_uses_active_preset_character(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.main_character as main_character
    import pipeline.test_lab as test_lab
    from models.settings import AppSetting
    from models.style_preset import StylePreset
    from models.style_preset_character import StylePresetCharacter

    monkeypatch.setattr(main_character, "DATA_DIR", tmp_path)
    monkeypatch.setattr(test_lab, "DATA_DIR", tmp_path)

    with Session(engine) as session:
        preset_id = "preset-a"
        character_id = "character-a"
        preset_image = tmp_path / "style" / "presets" / f"{preset_id}.png"
        preset_image.parent.mkdir(parents=True, exist_ok=True)
        preset_image.write_bytes(b"preset")
        character_ref = tmp_path / "style" / "presets" / preset_id / "characters" / f"{character_id}.png"
        character_ref.parent.mkdir(parents=True, exist_ok=True)
        character_ref.write_bytes(b"preset-main-character")
        session.add(
            StylePreset(
                id=preset_id,
                name="Mara",
                prompt="bright illustrated style",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.add(
            StylePresetCharacter(
                id=character_id,
                style_preset_id=preset_id,
                name="Mara",
                appearance="A cartographer in a green jacket.",
                vibe="Inventive and calm.",
                reference_image_url=f"/static/style/presets/{preset_id}/characters/{character_id}.png",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.add(AppSetting(key="ACTIVE_STYLE_PRESET_ID", value=preset_id))
        session.add(
            AppSetting(
                key=main_character.active_style_preset_character_key(preset_id),
                value=character_id,
            )
        )
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-preset-character",
            preset_id="life-scribe",
            settings={"eli_enabled": False},
        )
        session.commit()

    manifest = test_lab.TestLabRunManifest(
        run_id="run-preset-character",
        script_id=script_id,
        preset_id="life-scribe",
        status="running",
    )
    ctx = test_lab.TestLabRunContext(
        engine=engine,
        run_id="run-preset-character",
        script_id=script_id,
        preset_id="life-scribe",
        settings={"eli_enabled": False},
        manifest=manifest,
        job_id=None,
    )

    test_lab._stage_character_reference(ctx)

    project_ref = tmp_path / "projects" / script_id / "character" / "reference.png"
    assert project_ref.read_bytes() == b"preset-main-character"
    assert ctx.manifest.assets[-1].url == f"/static/projects/{script_id}/character/reference.png"


def test_stage_audio_forwards_voice_model_and_settings(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.test_lab as test_lab
    import pipeline.voiceover as voiceover
    from models.brand import BrandProfile
    from models.script import ScriptContent

    with Session(engine) as session:
        brand = session.get(BrandProfile, "default")
        assert brand is not None
        brand.voice_id = "voice-default"
        session.add(brand)
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-audio-settings",
            preset_id="coffee-brain",
            settings={},
        )
        session.commit()

    captured = {}

    def fake_generate_scene_audio(scene_id, narration, voice_id, script_id_arg, *, model_id, voice_settings):
        captured.update(
            {
                "scene_id": scene_id,
                "narration": narration,
                "voice_id": voice_id,
                "script_id": script_id_arg,
                "model_id": model_id,
                "voice_settings": voice_settings,
            }
        )
        return (
            "/static/projects/test/audio/scene.mp3",
            4.2,
            [{"word": "Caffeine", "start_ms": 0, "end_ms": 500}],
            [{"text": "Caffeine", "start_ms": 0, "end_ms": 500}],
        )

    monkeypatch.setattr(voiceover, "generate_scene_audio", fake_generate_scene_audio)

    manifest = test_lab.TestLabRunManifest(
        run_id="run-audio-settings",
        script_id=script_id,
        preset_id="coffee-brain",
        status="running",
    )
    ctx = test_lab.TestLabRunContext(
        engine=engine,
        run_id="run-audio-settings",
        script_id=script_id,
        preset_id="coffee-brain",
        settings={
            "voice_id": "voice-override",
            "voice_model_id": "eleven_turbo_v2_5",
            "voice_settings": {"stability": 0.33, "similarity_boost": 0.75},
        },
        manifest=manifest,
        job_id=None,
    )

    test_lab._stage_audio(ctx)

    assert captured["voice_id"] == "voice-override"
    assert captured["model_id"] == "eleven_turbo_v2_5"
    assert captured["voice_settings"] == {"stability": 0.33, "similarity_boost": 0.75}
    with Session(engine) as session:
        record, content = test_lab._load_content_for_script(session, script_id)
        _ = record
        saved = ScriptContent.model_validate(content)
    assert saved.segments[0].scenes[0].audio_url == "/static/projects/test/audio/scene.mp3"


def test_cost_breakdown_scopes_to_script_id(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    from models.api_usage import ApiUsage
    from pipeline.test_lab import build_cost_breakdown

    with Session(engine) as session:
        session.add(
            ApiUsage(
                script_id="test-script",
                service="elevenlabs",
                operation="tts",
                model="eleven_multilingual_v2",
                characters=100,
                cost_estimate=0.01,
            )
        )
        session.add(
            ApiUsage(
                script_id="other-script",
                service="google_ai",
                operation="image_gen",
                model="gemini",
                images=1,
                cost_estimate=0.03,
            )
        )
        session.add(
            ApiUsage(
                script_id="test-script",
                service="google_ai",
                operation="image_gen",
                model="gemini",
                images=1,
                cost_estimate=0.02,
            )
        )
        session.commit()

        cost = build_cost_breakdown(session, "test-script")

    assert cost["total_cost"] == 0.03
    assert {item["service"] for item in cost["breakdown"]} == {"elevenlabs", "google_ai"}


def test_cost_breakdown_total_uses_raw_usage_sum(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    from models.api_usage import ApiUsage
    from pipeline.test_lab import build_cost_breakdown

    with Session(engine) as session:
        session.add(
            ApiUsage(
                script_id="test-script",
                service="elevenlabs",
                operation="tts",
                model="eleven_multilingual_v2",
                cost_estimate=0.00004,
            )
        )
        session.add(
            ApiUsage(
                script_id="test-script",
                service="google_ai",
                operation="image_gen",
                model="gemini",
                cost_estimate=0.00004,
            )
        )
        session.commit()

        cost = build_cost_breakdown(session, "test-script")

    assert cost["total_cost"] == 0.0001
    assert sum(item["total_cost"] for item in cost["breakdown"]) == 0.0


def test_run_test_lab_phases_uses_selected_order_and_classifies_assets(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.test_lab as test_lab

    calls = []

    def fake_audio(ctx):
        calls.append("audio")
        ctx.manifest.assets.append(test_lab.TestLabAsset(kind="audio", label="Voiceover", url="/static/projects/test/audio/scene.mp3"))

    def fake_visual(ctx):
        calls.append("visual")
        ctx.manifest.assets.append(test_lab.TestLabAsset(kind="video", label="AI video", url="/static/projects/test/videos/scene.mp4"))
        ctx.manifest.assets.append(test_lab.TestLabAsset(kind="image", label="Anchor image", url="/static/projects/test/images/scene.png"))

    def fake_render(ctx):
        calls.append("render")
        ctx.manifest.render_url = "/static/projects/test/renders/full_youtube.mp4"
        ctx.manifest.assets.append(test_lab.TestLabAsset(kind="render", label="Remotion render", url=ctx.manifest.render_url))

    monkeypatch.setattr(test_lab, "_stage_audio", fake_audio)
    monkeypatch.setattr(test_lab, "_stage_visual", fake_visual)
    monkeypatch.setattr(test_lab, "_stage_treatment_assets", lambda ctx: calls.append("treatment"))
    monkeypatch.setattr(test_lab, "_stage_fx", lambda ctx: calls.append("fx"))
    monkeypatch.setattr(test_lab, "_stage_eli", lambda ctx: calls.append("eli"))
    monkeypatch.setattr(test_lab, "_stage_render", fake_render)

    output_urls = test_lab.run_test_lab(
        engine=engine,
        run_id="run-phases",
        preset_id="coffee-brain",
        settings={
            "media_source": "ai_video",
            "stages": {
                "audio": True,
                "visual": True,
                "treatment_assets": True,
                "fx": True,
                "eli": True,
                "render": True,
            },
        },
        job_id=None,
    )

    manifest = test_lab.load_run_manifest("run-phases")

    assert calls == ["audio", "visual", "treatment", "fx", "eli", "render"]
    assert output_urls == ["/static/projects/test/renders/full_youtube.mp4"]
    assert manifest.status == "completed"
    assert [asset.kind for asset in manifest.assets] == ["audio", "video", "image", "render"]


def test_stage_treatment_assets_respects_explicit_treatment(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.image_gen as image_gen
    import pipeline.test_lab as test_lab
    import pipeline.visual_treatments as visual_treatments
    from models.script import ScriptContent

    with Session(engine) as session:
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-explicit-treatment",
            preset_id="coffee-brain",
            settings={
                "visual_treatment": "flipflop",
                "advanced_script": {
                    "segments": [
                        {
                            "name": "The caffeine switch",
                            "scenes": [
                                {
                                    "id": "coffee-brain-scene-1",
                                    "narration": "Caffeine blocks the sleepy signal.",
                                    "visual_prompt": "Flat 2D cartoon coffee mug powering up a brain.",
                                    "visual_treatment": "flipflop",
                                    "visual_layers": [
                                        {
                                            "id": "panel-a",
                                            "type": "image",
                                            "asset_kind": "panel",
                                            "prompt": "A simple panel.",
                                        }
                                    ],
                                }
                            ],
                        }
                    ],
                },
            },
        )
        session.commit()

    monkeypatch.setattr(
        visual_treatments,
        "analyze_visual_treatments",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should not analyze explicit treatment")),
    )

    def fake_generate_visual_layer_panels(scene_id, layers, script_id_arg, **_kwargs):
        assert scene_id == "coffee-brain-scene-1"
        assert script_id_arg == script_id
        assert layers[0]["id"] == "panel-a"
        return [{**layers[0], "image_url": "/static/projects/test/layers/panel-a.png"}]

    monkeypatch.setattr(image_gen, "generate_visual_layer_panels", fake_generate_visual_layer_panels)

    manifest = test_lab.TestLabRunManifest(
        run_id="run-explicit-treatment",
        script_id=script_id,
        preset_id="coffee-brain",
        status="running",
    )
    ctx = test_lab.TestLabRunContext(
        engine=engine,
        run_id="run-explicit-treatment",
        script_id=script_id,
        preset_id="coffee-brain",
        settings={},
        manifest=manifest,
        job_id=None,
    )

    test_lab._stage_treatment_assets(ctx)

    with Session(engine) as session:
        record, content = test_lab._load_content_for_script(session, script_id)
        _ = record
        saved = ScriptContent.model_validate(content)

    scene = saved.segments[0].scenes[0]
    assert scene.visual_treatment == "flipflop"
    assert scene.visual_layers
    assert scene.visual_layers[0].image_url == "/static/projects/test/layers/panel-a.png"
    assert [asset.kind for asset in manifest.assets] == ["treatment_asset"]


def test_stage_treatment_assets_analyzes_empty_selected_layer_treatment(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.image_gen as image_gen
    import pipeline.test_lab as test_lab
    import pipeline.visual_treatments as visual_treatments
    from models.script import ScriptContent, VisualLayer
    from pipeline.visual_treatments import VisualTreatmentAssignment

    with Session(engine) as session:
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-empty-selected-treatment",
            preset_id="coffee-brain",
            settings={
                "visual_treatment": "popup_sequence",
                "visual_layers": [],
            },
        )
        record, content = test_lab._load_content_for_script(session, script_id)
        scene = content.segments[0].scenes[0]
        scene.audio_duration_seconds = 6.0
        scene.word_timestamps = [{"word": "Caffeine", "start_ms": 0, "end_ms": 500}]
        record.script_json = content.model_dump_json()
        session.add(record)
        session.commit()

    def fake_analyze(content, *, script_id):
        scene = content.segments[0].scenes[0]
        return [
            VisualTreatmentAssignment(
                scene_id=scene.id,
                visual_treatment="flipflop",
                visual_layers=[
                    VisualLayer(
                        id="generated-layer",
                        prompt="Generated layer prompt.",
                        placement="center",
                    )
                ],
            )
        ]

    def fake_generate_visual_layer_panels(scene_id, layers, script_id_arg, **_kwargs):
        assert scene_id == "coffee-brain-scene-1"
        assert script_id_arg == script_id
        assert layers[0]["id"] == "generated-layer"
        return [{**layers[0], "image_url": "/static/projects/test/layers/generated-layer.png"}]

    monkeypatch.setattr(visual_treatments, "analyze_visual_treatments", fake_analyze)
    monkeypatch.setattr(image_gen, "generate_visual_layer_panels", fake_generate_visual_layer_panels)

    manifest = test_lab.TestLabRunManifest(
        run_id="run-empty-selected-treatment",
        script_id=script_id,
        preset_id="coffee-brain",
        status="running",
    )
    ctx = test_lab.TestLabRunContext(
        engine=engine,
        run_id="run-empty-selected-treatment",
        script_id=script_id,
        preset_id="coffee-brain",
        settings={"visual_treatment": "popup_sequence", "visual_layers": []},
        manifest=manifest,
        job_id=None,
    )

    test_lab._stage_treatment_assets(ctx)

    with Session(engine) as session:
        record, content = test_lab._load_content_for_script(session, script_id)
        _ = record
        saved = ScriptContent.model_validate(content)

    scene = saved.segments[0].scenes[0]
    assert scene.visual_treatment == "popup_sequence"
    assert scene.visual_layers
    assert scene.visual_layers[0].image_url == "/static/projects/test/layers/generated-layer.png"
    assert [asset.kind for asset in manifest.assets] == ["treatment_asset"]


def test_stage_treatment_assets_uses_fallback_for_explicit_layer_treatment_without_audio(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.image_gen as image_gen
    import pipeline.test_lab as test_lab
    import pipeline.visual_treatments as visual_treatments
    from models.script import ScriptContent

    with Session(engine) as session:
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-treatment-no-audio",
            preset_id="coffee-brain",
            settings={
                "visual_treatment": "popup_sequence",
                "visual_layers": [],
            },
        )
        session.commit()

    monkeypatch.setattr(
        visual_treatments,
        "analyze_visual_treatments",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("should use fallback without timing")),
    )

    def fake_generate_visual_layer_panels(scene_id, layers, script_id_arg, **_kwargs):
        assert scene_id == "coffee-brain-scene-1"
        assert script_id_arg == script_id
        assert [layer["id"] for layer in layers] == ["coffee-brain-scene-1_popup_1", "coffee-brain-scene-1_popup_2"]
        return [
            {**layers[0], "image_url": "/static/projects/test/layers/popup-1.png"},
            {**layers[1], "image_url": "/static/projects/test/layers/popup-2.png"},
        ]

    monkeypatch.setattr(image_gen, "generate_visual_layer_panels", fake_generate_visual_layer_panels)

    manifest = test_lab.TestLabRunManifest(
        run_id="run-treatment-no-audio",
        script_id=script_id,
        preset_id="coffee-brain",
        status="running",
    )
    ctx = test_lab.TestLabRunContext(
        engine=engine,
        run_id="run-treatment-no-audio",
        script_id=script_id,
        preset_id="coffee-brain",
        settings={"visual_treatment": "popup_sequence", "visual_layers": []},
        manifest=manifest,
        job_id=None,
    )

    test_lab._stage_treatment_assets(ctx)

    with Session(engine) as session:
        record, content = test_lab._load_content_for_script(session, script_id)
        _ = record
        saved = ScriptContent.model_validate(content)

    scene = saved.segments[0].scenes[0]
    assert scene.visual_treatment == "popup_sequence"
    assert [layer.image_url for layer in scene.visual_layers] == [
        "/static/projects/test/layers/popup-1.png",
        "/static/projects/test/layers/popup-2.png",
    ]
    assert [asset.kind for asset in manifest.assets] == ["treatment_asset", "treatment_asset"]


def test_stage_render_wires_cancel_check_and_progress(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.remotion_render as remotion_render
    import pipeline.test_lab as test_lab
    from pipeline.render_jobs import create_job, get_job

    with Session(engine) as session:
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-render-hooks",
            preset_id="coffee-brain",
            settings={},
        )
        session.commit()

    job = create_job(scene_count=1)
    manifest = test_lab.TestLabRunManifest(
        run_id="run-render-hooks",
        script_id=script_id,
        preset_id="coffee-brain",
        status="running",
    )
    ctx = test_lab.TestLabRunContext(
        engine=engine,
        run_id="run-render-hooks",
        script_id=script_id,
        preset_id="coffee-brain",
        settings={},
        manifest=manifest,
        job_id=job.id,
        progress_start=0.5,
        progress_end=0.75,
    )
    observed = {}

    def fake_render_full_video(**kwargs):
        observed["cancel_check"] = kwargs["cancel_check"]
        observed["on_progress"] = kwargs["on_progress"]
        kwargs["cancel_check"]()
        kwargs["on_progress"](0.4, "Rendering video with Remotion...")
        return "/static/projects/test-lab-run/renders/full_youtube.mp4"

    monkeypatch.setattr(remotion_render, "render_full_video", fake_render_full_video)

    test_lab._stage_render(ctx)

    updated_job = get_job(job.id)
    assert callable(observed["cancel_check"])
    assert callable(observed["on_progress"])
    assert updated_job is not None
    assert updated_job.progress == 0.6
    assert updated_job.current_step == "Rendering video with Remotion..."
    assert manifest.render_url == "/static/projects/test-lab-run/renders/full_youtube.mp4"


def test_run_test_lab_persists_failed_manifest_when_setup_fails(monkeypatch, tmp_path):
    import pytest

    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.test_lab as test_lab

    with pytest.raises(ValueError):
        test_lab.run_test_lab(
            engine=engine,
            run_id="run-bad-preset",
            preset_id="missing-preset",
            settings={},
            job_id=None,
        )

    manifest = test_lab.load_run_manifest("run-bad-preset")
    assert manifest.status == "failed"
    assert manifest.logs[-1].level == "error"
    assert "Unknown Test Lab preset" in manifest.logs[-1].message


def test_run_test_lab_preserves_cancelled_job_status(monkeypatch, tmp_path):
    import pytest

    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.test_lab as test_lab
    from pipeline.render_jobs import cancel_job, create_job, get_job

    job = create_job(scene_count=1)

    def fake_audio(ctx):
        cancel_job(ctx.job_id)
        test_lab._check_cancelled(ctx)

    monkeypatch.setattr(test_lab, "_stage_audio", fake_audio)

    with pytest.raises(RuntimeError, match="cancelled"):
        test_lab.run_test_lab(
            engine=engine,
            run_id="run-cancelled",
            preset_id="coffee-brain",
            settings={
                "stages": {
                    "audio": True,
                    "visual": False,
                    "treatment_assets": False,
                    "fx": False,
                    "eli": False,
                    "render": False,
                },
            },
            job_id=job.id,
        )

    updated_job = get_job(job.id)
    manifest = test_lab.load_run_manifest("run-cancelled")
    assert updated_job is not None
    assert updated_job.status == "cancelled"
    assert manifest.status == "cancelled"
    assert "cancelled" in manifest.logs[-1].message
