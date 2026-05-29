# Test Lab Visual Mode Controls Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild Test Lab settings around visual modes, remove old Test Lab-only voice/stage overrides, and make mode-specific scene prompts editable through structured controls.

**Architecture:** Keep the existing Test Lab hidden-script pipeline, but update its settings contract. Backend changes make `frame_directives` consumable, derive Eli from `eli_enabled`, remove the Character stage from the runner, and expose a voice summary. Frontend changes replace the current flat controls with accordion panels ordered Visual Mode, Character, Audio, Pipeline Stages, and Miscellaneous.

**Tech Stack:** React 19 + TypeScript + Tailwind 4, Vitest, FastAPI/Pydantic, SQLModel, pytest via `uv run --project backend pytest`.

---

### Task 1: Backend Settings Contract And Stage Cleanup

**Files:**
- Modify: `backend/pipeline/test_lab.py`
- Test: `backend/tests/test_test_lab.py`

- [ ] **Step 1: Write failing backend tests**

Add tests that assert top-level frame directives are copied into the hidden scene, the Character stage is absent, and Eli is derived from `eli_enabled`:

```python
def test_test_lab_preset_uses_top_level_frame_directives():
    from pipeline.test_lab import build_content_from_preset

    content = build_content_from_preset(
        "coffee-brain",
        {
            "visual_mode": "multi_frame",
            "frame_directives": [
                {
                    "prompt": "Custom frame one.",
                    "source": "ai_generated",
                    "transition": "cut",
                    "reference_previous": False,
                    "search_query": "",
                }
            ],
        },
    )

    scene = content.segments[0].scenes[0]
    assert scene.visual_mode == "multi_frame"
    assert len(scene.frame_directives) == 1
    assert scene.frame_directives[0].prompt == "Custom frame one."


def test_stage_defaults_no_longer_include_character_or_direct_eli_stage():
    from pipeline.test_lab import _stage_defaults

    defaults = _stage_defaults(
        {
            "eli_enabled": True,
            "stages": {"character": True, "eli": False, "audio": False, "visual": False, "render": False},
        }
    )

    assert "character" not in defaults
    assert "eli" not in defaults
    assert defaults["eli_derived"] is True
```

- [ ] **Step 2: Run backend tests and verify RED**

Run: `uv run --project backend pytest backend/tests/test_test_lab.py::test_test_lab_preset_uses_top_level_frame_directives backend/tests/test_test_lab.py::test_stage_defaults_no_longer_include_character_or_direct_eli_stage -q`

Expected: FAIL because `frame_directives` are ignored and `_stage_defaults` still returns `character`/`eli`.

- [ ] **Step 3: Implement settings/stage cleanup**

In `backend/pipeline/test_lab.py`:

- Copy top-level `settings["frame_directives"]` into `Scene.frame_directives` when no advanced scene override already provided directives.
- Remove `"character"` and `"eli"` from `_stage_defaults`.
- Add an `"eli_derived"` key or equivalent internal stage flag derived only from `eli_enabled`.
- Remove `("character", _stage_character_reference)` from the runner stage list.
- Keep `_stage_character_reference` only if other code still imports it; otherwise leave it unreachable from Test Lab.

- [ ] **Step 4: Run backend tests and verify GREEN**

Run: `uv run --project backend pytest backend/tests/test_test_lab.py::test_test_lab_preset_uses_top_level_frame_directives backend/tests/test_test_lab.py::test_stage_defaults_no_longer_include_character_or_direct_eli_stage -q`

Expected: PASS.

### Task 2: Voice Summary And Audio Source Of Truth

**Files:**
- Modify: `backend/api/test_lab.py`
- Modify: `backend/pipeline/test_lab.py`
- Test: `backend/tests/test_test_lab.py`

- [ ] **Step 1: Write failing backend tests**

Replace the old override-forwarding expectation with tests that legacy settings are ignored and `/api/test-lab/scenes` returns `voice_summary`:

```python
def test_stage_audio_uses_settings_voice_and_ignores_run_overrides(monkeypatch, tmp_path):
    engine, _app = _setup_app(monkeypatch, tmp_path)

    import pipeline.test_lab as test_lab
    import pipeline.voiceover as voiceover
    from models.app_settings import AppSetting
    from models.brand import BrandProfile

    with Session(engine) as session:
        brand = session.get(BrandProfile, "default")
        assert brand is not None
        brand.voice_id = "voice-default"
        session.add(brand)
        session.add(AppSetting(key="ELEVENLABS_TTS_MODEL", value="eleven_multilingual_v2"))
        session.add(AppSetting(key="ELEVENLABS_STABILITY", value="0.45"))
        session.add(AppSetting(key="ELEVENLABS_STYLE", value="0.15"))
        session.add(AppSetting(key="ELEVENLABS_SPEED", value="0.97"))
        script_id = test_lab.create_hidden_test_script(
            session,
            run_id="run-audio-settings",
            preset_id="coffee-brain",
            settings={},
        )
        session.commit()

    captured = {}

    def fake_generate_scene_audio(scene_id, narration, voice_id, script_id_arg, *, model_id, voice_settings):
        captured.update({"voice_id": voice_id, "model_id": model_id, "voice_settings": voice_settings})
        return "/static/projects/test/audio/scene.mp3", 4.2, [], []

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

    assert captured["voice_id"] == "voice-default"
    assert captured["model_id"] == "eleven_multilingual_v2"
    assert captured["voice_settings"]["stability"] == 0.45


def test_test_lab_scenes_endpoint_returns_voice_summary(monkeypatch, tmp_path):
    engine, app = _setup_app(monkeypatch, tmp_path)

    from models.app_settings import AppSetting
    from models.brand import BrandProfile

    with Session(engine) as session:
        brand = session.get(BrandProfile, "default")
        assert brand is not None
        brand.voice_id = "voice-default"
        session.add(brand)
        session.add(AppSetting(key="ELEVENLABS_TTS_MODEL", value="eleven_multilingual_v2"))
        session.add(AppSetting(key="ELEVENLABS_STABILITY", value="0.45"))
        session.add(AppSetting(key="ELEVENLABS_STYLE", value="0.15"))
        session.add(AppSetting(key="ELEVENLABS_SPEED", value="0.97"))
        session.commit()

    client = TestClient(app)
    try:
        response = client.get("/api/test-lab/scenes")
        assert response.status_code == 200
        summary = response.json()["voice_summary"]
        assert summary["voice_id"] == "voice-default"
        assert summary["model_id"] == "eleven_multilingual_v2"
        assert summary["delivery_preset"] == "More Human"
    finally:
        from database import get_session

        app.dependency_overrides.pop(get_session, None)
```

- [ ] **Step 2: Run backend tests and verify RED**

Run: `uv run --project backend pytest backend/tests/test_test_lab.py::test_stage_audio_uses_settings_voice_and_ignores_run_overrides backend/tests/test_test_lab.py::test_test_lab_scenes_endpoint_returns_voice_summary -q`

Expected: FAIL because override settings are still used and no voice summary is returned.

- [ ] **Step 3: Implement voice behavior**

In `backend/pipeline/test_lab.py`:

- Remove per-run voice override reads from `_voice_id_for_run` and `_stage_audio`.
- Call `resolve_tts_model_and_settings(None, None)` so Settings -> Voices stays authoritative.

In `backend/api/test_lab.py`:

- Add a helper that reads the default brand voice and settings keys.
- Return `voice_summary` from `/api/test-lab/scenes`.
- Keep v2/v3 visible settings aligned with Settings -> Voices: v3 stability only; v2 preset label plus custom values only when custom.

- [ ] **Step 4: Run backend tests and verify GREEN**

Run: `uv run --project backend pytest backend/tests/test_test_lab.py::test_stage_audio_uses_settings_voice_and_ignores_run_overrides backend/tests/test_test_lab.py::test_test_lab_scenes_endpoint_returns_voice_summary -q`

Expected: PASS.

### Task 3: Frontend Types And Settings Sanitization

**Files:**
- Modify: `frontend/src/types/testLab.ts`
- Modify: `frontend/src/components/test-lab/TestLabPage.tsx`
- Modify: `frontend/src/api.ts`
- Test: `frontend/src/components/test-lab/TestLabControls.test.ts`

- [ ] **Step 1: Write failing frontend tests**

Update tests to use stages without `character`/`eli`, add `frame_directives`, and assert run settings do not contain removed fields.

```ts
expect(settings.stages).not.toHaveProperty("character");
expect(settings.stages).not.toHaveProperty("eli");
expect(settings).not.toHaveProperty("voice_id");
expect(settings).not.toHaveProperty("voice_model_id");
expect(settings).not.toHaveProperty("voice_settings");
```

- [ ] **Step 2: Run frontend tests and verify RED**

Run: `npm run test:frontend -- TestLabControls.test.ts --run`

Expected: FAIL because types/default settings still include removed fields.

- [ ] **Step 3: Implement type cleanup**

Remove `character` and `eli` from `TestLabStages`, add `frame_directives` to `TestLabSettings`, remove voice override fields, and update `DEFAULT_SETTINGS` and `settingsForRun`.

- [ ] **Step 4: Run frontend tests and verify GREEN**

Run: `npm run test:frontend -- TestLabControls.test.ts --run`

Expected: PASS.

### Task 4: Accordion UI And Adaptive Visual Mode Controls

**Files:**
- Modify: `frontend/src/components/test-lab/TestLabControls.tsx`
- Test: `frontend/src/components/test-lab/TestLabControls.test.ts`

- [ ] **Step 1: Write failing component tests**

Add render tests for:

- Section order: Visual Mode, Character, Audio, Pipeline Stages, Miscellaneous.
- Accordion collapse/expand.
- Visual Mode section excludes canvas/subtitle/timer controls.
- Miscellaneous contains canvas/subtitle/timer controls.
- Mode-specific controls render for `flipflop`, `multi_frame`, `continuous`, `popup_sequence`, `comparison_board`, and `captions`.
- Pipeline does not expose Character or editable Eli toggles.

- [ ] **Step 2: Run frontend tests and verify RED**

Run: `npm run test:frontend -- TestLabControls.test.ts --run`

Expected: FAIL because the current component is still flat and ordered differently.

- [ ] **Step 3: Implement UI**

In `TestLabControls.tsx`:

- Replace `Panel` with collapsible accordion sections.
- Reorder sections.
- Move scene text into Visual Mode.
- Add structured controls for the current visual modes and a collapsed Advanced Mode Data drawer.
- Replace Audio inputs with a read-only `voice_summary` display.
- Remove Character from pipeline stages and render Eli as read-only derived status.
- Move canvas/subtitle/timer controls to Miscellaneous.

- [ ] **Step 4: Run frontend tests and verify GREEN**

Run: `npm run test:frontend -- TestLabControls.test.ts --run`

Expected: PASS.

### Task 5: Full Verification, Review Loop, Commit, Push

**Files:**
- Modify as needed based on test/review results.

- [ ] **Step 1: Run focused backend tests**

Run: `uv run --project backend pytest backend/tests/test_test_lab.py -q`

Expected: PASS.

- [ ] **Step 2: Run focused frontend tests**

Run: `npm run test:frontend -- TestLabControls.test.ts --run`

Expected: PASS.

- [ ] **Step 3: Run frontend build or broader check**

Run: `npm run test:frontend -- --run`

Expected: PASS.

- [ ] **Step 4: Commit and push**

Run:

```bash
git add backend/pipeline/test_lab.py backend/api/test_lab.py backend/tests/test_test_lab.py frontend/src/types/testLab.ts frontend/src/components/test-lab/TestLabPage.tsx frontend/src/components/test-lab/TestLabControls.tsx frontend/src/components/test-lab/TestLabControls.test.ts frontend/src/api.ts docs/superpowers/plans/2026-05-29-test-lab-visual-mode-controls.md
git commit -m "Update Test Lab visual mode controls"
git push origin main
```

- [ ] **Step 5: Delegated review loop**

Dispatch the repository-required code review agent for the most recent commit. If the verdict is `NEEDS CHANGES`, implement every FAIL/WARN finding, commit as `fix: address review findings`, push, and repeat until `LGTM`.
