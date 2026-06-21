"""Tests for the Test Lab smoke-test diagnostics."""

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
    import pipeline.test_lab as test_lab_module

    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(scripts_module, "engine", engine)
    monkeypatch.setattr(test_lab_module, "DATA_DIR", tmp_path)

    from api import app
    from database import get_session

    def _override_get_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = _override_get_session
    return engine, app


def test_smoke_report_flags_blink_policy_warning():
    from pipeline.test_lab_smoke import SmokeTestOptions, run_smoke_test

    report = run_smoke_test(options=SmokeTestOptions(render_heavy=False, external_api=False))

    assert report.summary["fail"] == 0
    blink_rows = [check for check in report.checks if check.id == "blink-production-guardrail"]
    assert len(blink_rows) == 1
    assert blink_rows[0].status == "warn"
    assert "policy text still presents blink" in blink_rows[0].detail
    assert blink_rows[0].next_action


def test_smoke_report_fails_when_representative_mode_missing(monkeypatch):
    import pipeline.test_lab_smoke as smoke
    from pipeline.test_lab import TEST_LAB_PRESETS
    from pipeline.test_lab_smoke import SmokeTestOptions, run_smoke_test

    without_stat_card = [preset for preset in TEST_LAB_PRESETS if preset.visual_mode != "stat_card"]
    monkeypatch.setattr(smoke, "TEST_LAB_PRESETS", without_stat_card)
    monkeypatch.setattr(
        smoke,
        "VISUAL_TREATMENT_TEXT_DEFAULTS",
        {key: value for key, value in smoke.VISUAL_TREATMENT_TEXT_DEFAULTS.items() if key != "stat_card"},
    )

    report = run_smoke_test(options=SmokeTestOptions(render_heavy=False, external_api=False))

    row = next(check for check in report.checks if check.id == "representative-presets")
    assert row.status == "fail"
    assert "stat_card" in row.detail
    assert report.summary["fail"] == 1


def test_smoke_report_reads_voice_and_subtitle_summaries(monkeypatch, tmp_path):
    from models.settings import AppSetting
    from pipeline.test_lab_smoke import SmokeTestOptions, run_smoke_test

    engine, _app = _setup_app(monkeypatch, tmp_path)
    with Session(engine) as session:
        session.add(AppSetting(key="ELEVENLABS_TTS_MODEL", value="eleven_v3"))
        session.add(AppSetting(key="SUBTITLE_COVERAGE_MODE", value="punchy"))
        session.commit()

    report = run_smoke_test(engine=engine, options=SmokeTestOptions(render_heavy=False, external_api=False))

    voice_row = next(check for check in report.checks if check.id == "voice-settings")
    subtitle_row = next(check for check in report.checks if check.id == "subtitle-settings")
    assert voice_row.status == "pass"
    assert "eleven_v3" in voice_row.evidence
    assert subtitle_row.status == "pass"
    assert "Punchy scenes" in subtitle_row.evidence


def test_render_probes_cover_default_only_visual_modes(monkeypatch, tmp_path):
    import pipeline.test_lab_smoke as smoke
    from pipeline.test_lab import TestLabRunManifest
    from pipeline.test_lab_smoke import SmokeTestOptions, run_smoke_test

    captured: list[dict] = []

    def fake_run_test_lab(**kwargs):
        captured.append(kwargs)
        return [f"/static/projects/test-lab-{kwargs['run_id']}/renders/full_youtube.mp4"]

    def fake_load_run_manifest(run_id: str):
        return TestLabRunManifest(
            run_id=run_id,
            script_id=f"test-lab-{run_id}",
            preset_id="coffee-brain",
            status="completed",
            render_url=f"/static/projects/test-lab-{run_id}/renders/full_youtube.mp4",
        )

    monkeypatch.setattr(smoke, "run_test_lab", fake_run_test_lab)
    monkeypatch.setattr(smoke, "load_run_manifest", fake_load_run_manifest)
    engine, _app = _setup_app(monkeypatch, tmp_path)

    report = run_smoke_test(engine=engine, options=SmokeTestOptions(render_heavy=True, external_api=False))

    probed_modes = {call["settings"]["visual_mode"] for call in captured}
    assert probed_modes == set(smoke.REPRESENTATIVE_MODES)
    assert report.summary["fail"] == 0


def test_smoke_route_returns_report(monkeypatch, tmp_path):
    engine, app = _setup_app(monkeypatch, tmp_path)
    import api.test_lab as test_lab_api

    monkeypatch.setattr(test_lab_api, "_engine", lambda: engine)

    client = TestClient(app)
    response = client.post(
        "/api/test-lab/smoke-test",
        json={"render_heavy": False, "external_api": False},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"]
    assert data["summary"]["fail"] == 0
    assert any(check["id"] == "visual-mode-vocabulary" for check in data["checks"])
