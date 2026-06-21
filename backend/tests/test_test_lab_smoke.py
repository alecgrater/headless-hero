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
    import pipeline.test_lab_smoke as smoke_module

    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(scripts_module, "engine", engine)
    monkeypatch.setattr(test_lab_module, "DATA_DIR", tmp_path)
    monkeypatch.setattr(smoke_module, "DATA_DIR", tmp_path)

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
    assert blink_rows[0].status == "pass"
    assert "no longer encourages production selection" in blink_rows[0].detail


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
    from pipeline.test_lab import TEST_LAB_PRESETS, TestLabRunManifest
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
    full_frame_call = next(call for call in captured if call["settings"]["visual_mode"] == "full_frame")
    full_frame_preset = next(preset for preset in TEST_LAB_PRESETS if preset.id == full_frame_call["preset_id"])
    full_frame_narration = full_frame_call["settings"].get("narration") or full_frame_preset.narration
    assert full_frame_narration.strip()
    assert report.summary["fail"] == 0


def test_render_only_layered_probes_warn_without_external_assets(monkeypatch, tmp_path):
    import pipeline.test_lab_smoke as smoke
    from pipeline.test_lab import TestLabRunManifest
    from pipeline.test_lab_smoke import SmokeTestOptions, run_smoke_test

    def fake_run_test_lab(**kwargs):
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

    layered_rows = [
        check
        for check in report.checks
        if check.id in {"render-probe-popup_sequence", "render-probe-comparison_board", "render-probe-blink"}
    ]
    assert {row.status for row in layered_rows} == {"warn"}
    assert all("render-only" in row.detail for row in layered_rows)


def test_smoke_report_sums_probe_manifest_costs(monkeypatch, tmp_path):
    import pipeline.test_lab_smoke as smoke
    from pipeline.test_lab import TestLabRunManifest
    from pipeline.test_lab_smoke import SmokeTestOptions, run_and_save_smoke_test, load_smoke_report

    def fake_run_test_lab(**kwargs):
        return [f"/static/projects/test-lab-{kwargs['run_id']}/renders/full_youtube.mp4"]

    def fake_load_run_manifest(run_id: str):
        total_cost = 0.0123 if "full-frame" in run_id else 0.0044
        return TestLabRunManifest(
            run_id=run_id,
            script_id=f"test-lab-{run_id}",
            preset_id="coffee-brain",
            status="completed",
            render_url=f"/static/projects/test-lab-{run_id}/renders/full_youtube.mp4",
            total_cost=total_cost,
        )

    monkeypatch.setattr(smoke, "REPRESENTATIVE_MODES", ("full_frame", "captions"))
    monkeypatch.setattr(smoke, "run_test_lab", fake_run_test_lab)
    monkeypatch.setattr(smoke, "load_run_manifest", fake_load_run_manifest)
    engine, _app = _setup_app(monkeypatch, tmp_path)

    report = run_and_save_smoke_test(engine=engine, options=SmokeTestOptions(render_heavy=True, external_api=True))

    assert report.total_cost == 0.0167
    assert load_smoke_report(report.id).total_cost == 0.0167


def test_smoke_report_counts_failed_probe_manifest_cost(monkeypatch, tmp_path):
    import pipeline.test_lab_smoke as smoke
    from pipeline.test_lab import TestLabRunManifest
    from pipeline.test_lab_smoke import SmokeTestOptions, run_smoke_test

    def fake_run_test_lab(**_kwargs):
        raise RuntimeError("render failed after paid asset generation")

    def fake_load_run_manifest(run_id: str):
        return TestLabRunManifest(
            run_id=run_id,
            script_id=f"test-lab-{run_id}",
            preset_id="coffee-brain",
            status="failed",
            total_cost=0.0456,
        )

    monkeypatch.setattr(smoke, "REPRESENTATIVE_MODES", ("full_frame",))
    monkeypatch.setattr(smoke, "run_test_lab", fake_run_test_lab)
    monkeypatch.setattr(smoke, "load_run_manifest", fake_load_run_manifest)
    engine, _app = _setup_app(monkeypatch, tmp_path)

    report = run_smoke_test(engine=engine, options=SmokeTestOptions(render_heavy=True, external_api=True))

    row = next(check for check in report.checks if check.id == "render-probe-full_frame")
    assert row.status == "fail"
    assert report.total_cost == 0.0456


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


def test_smoke_route_persists_history_and_loads_saved_report(monkeypatch, tmp_path):
    engine, app = _setup_app(monkeypatch, tmp_path)
    import api.test_lab as test_lab_api

    monkeypatch.setattr(test_lab_api, "_engine", lambda: engine)

    client = TestClient(app)
    created = client.post(
        "/api/test-lab/smoke-tests",
        json={"render_heavy": False, "external_api": False},
    )

    assert created.status_code == 200
    report_id = created.json()["id"]

    listed = client.get("/api/test-lab/smoke-tests")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["reports"]] == [report_id]
    assert listed.json()["reports"][0]["summary"] == created.json()["summary"]

    loaded = client.get(f"/api/test-lab/smoke-tests/{report_id}")
    assert loaded.status_code == 200
    assert loaded.json()["id"] == report_id
    assert loaded.json()["checks"] == created.json()["checks"]


def test_smoke_export_brief_is_ready_for_codex(monkeypatch, tmp_path):
    engine, app = _setup_app(monkeypatch, tmp_path)
    import api.test_lab as test_lab_api

    monkeypatch.setattr(test_lab_api, "_engine", lambda: engine)

    client = TestClient(app)
    created = client.post(
        "/api/test-lab/smoke-tests",
        json={"render_heavy": False, "external_api": False},
    )
    report_id = created.json()["id"]

    exported = client.get(f"/api/test-lab/smoke-tests/{report_id}/export")

    assert exported.status_code == 200
    data = exported.json()
    assert data["report_id"] == report_id
    assert "Please fix the Headless Hero Smoke Test issues below." in data["markdown"]
    assert f"Smoke Test Report `{report_id}`" in data["markdown"]
    assert "- Total cost: $0.0000" in data["markdown"]
    assert "## Warnings" in data["markdown"]
    assert "blink-production-guardrail" in data["markdown"]
    assert "Blink is disabled for production routing" in data["markdown"]
