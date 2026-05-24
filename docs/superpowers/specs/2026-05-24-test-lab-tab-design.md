# Test Lab Tab Design

## Purpose

Add a new `Test` tab between `Developer` and `Settings` for testing visual, animation, audio, character, and render settings against a single dummy scene before spending money on a full project. The tab should make it easy to run real generation, watch each stage, play the result in the app, inspect generated assets, and review the exact cost of the test.

The key requirement is behavioral parity with a real project. Test Lab runs may be hidden from normal project lists, but they must use the same production script models, project config, generation functions, asset conventions, usage tracking, and Remotion rendering behavior wherever possible.

## Scope

In scope:

- A top-level `Test` tab in the main navigation between `Developer` and `Settings`.
- Ten realistic dummy scene presets that resemble normal scriptwriter output rather than feature-specific fixtures.
- A dedicated Test Lab backend surface under `/api/test-lab/*`.
- Hidden real `Script` and `ProjectConfig` records for each run or reusable run workspace, excluded from normal project/dashboard lists.
- Real paid provider calls when selected by settings.
- Run history persisted across app restarts, capped at the last 20 runs.
- In-app playback of the rendered single-scene preview.
- Generated asset inspection for `Image`, `Video`, `Audio`, `Treatment Assets`, and final `Render`.
- Cost breakdown using the same `ApiUsage` accounting shape as project timelines.
- Character mode testing for both Eli-enabled and Eli-disabled/project-character flows.

Out of scope:

- Stock photo generation.
- Gameplay video generation.
- User-upload media paths.
- Changing script generation to deliberately write feature-targeted scenes. That may be explored later, but these dummy presets should stay realistic.

## Backend Design

Create `backend/api/test_lab.py` and include it from `backend/api/__init__.py`.

Core endpoints:

- `GET /api/test-lab/scenes`: return the ten dummy scene presets and their editable default settings.
- `POST /api/test-lab/runs`: start a test run and return a job id plus run id.
- `GET /api/test-lab/runs/{run_id}`: return run details, settings snapshot, logs, assets, render URL, and cost.
- `GET /api/test-lab/runs`: return persisted history, newest first, capped at 20.
- `GET /api/test-lab/runs/status/{job_id}`: poll the active background job.
- `DELETE /api/test-lab/runs`: clear Test Lab history and Test Lab-only artifacts.

Starting a run should:

1. Create or refresh a hidden test `Script` row and `ProjectConfig` row using the selected dummy preset and settings snapshot.
2. Mark the record as Test Lab-only so it never appears in normal project lists.
3. Persist a run manifest under `data/test-lab/runs/{run_id}.json`.
4. Run selected stages in production order: prepare workspace, project character reference when required, audio, visual source, visual treatment assets, FX, Eli when enabled, Remotion scene preview render, cost sync.
5. Append timestamped logs to the run manifest as stages start, complete, or fail.
6. Record generated asset URLs and final render URL in the run manifest.
7. Return cost data in the same breakdown shape used by `/api/scripts/{script_id}/cost`.

Hidden test records need a durable exclusion mechanism. The implementation can add a metadata field, status marker, or another local convention, but the normal project list must filter them out and tests must assert that behavior. The hidden records should still be valid enough for existing generation functions, character-reference gates, render cache checks, static asset serving, and `ApiUsage.script_id` attribution.

## Frontend Design

Add a `TestLabPage` and a `test-lab` view in `frontend/src/App.tsx`. The tab should follow the app’s dark Tailwind styling and use existing UI primitives where practical.

The page uses a three-column lab layout:

- Left: dummy scene selector. Each preset shows title, format, short narration preview, character hints, and useful tags such as `life-as-a` or `cinematic`.
- Middle: comprehensive settings editor, organized by tabs or grouped sections.
- Right: run status, playable preview, generated asset tiles, cost breakdown, and last-20 run history.

Settings groups:

- `Pipeline`: stage toggles. Render is on by default. Audio, visual generation, treatment assets, FX, Eli, and render can be run individually or together.
- `Format`: format id and format-specific metadata needed for realistic render behavior.
- `Character`: Eli enabled, project character mode, main character fields, style preset toggle, and reference generation/selection status.
- `Visual Source`: AI image and AI video provider/options that remain supported after stock/gameplay/upload removal.
- `Treatment`: full-frame, popup sequence, flipflop, visual layers, layer placement, timing, and treatment asset settings.
- `Motion + FX`: scene transition, drift, zoom punch, visual in/out, frame timings, and related micro-timeline fields.
- `Audio`: voice, model, voice settings, narration, and TTS narration override.
- `Subtitles`: subtitle highlight and timing-related controls.
- `Canvas`: visual canvas background, segment timer, and video-level visual toggles.
- `Advanced`: raw script/scene JSON override for edge cases.

Each regular setting should include a tooltip or short inline help text explaining what it changes and which generation/render stage it affects. The UI may be dense, but it should be organized enough that all valid combinations are reachable without burying important state.

## Dummy Scene Presets

The ten presets should be realistic one-scene mini scripts, not artificial feature fixtures. Each preset should include the same categories of fields a fresh project would normally have:

- title
- format id
- segment name and short name
- narration
- optional `tts_narration`
- visual prompt
- estimated duration
- `contains_person`
- visual beat and realistic frame directives when appropriate
- optional main character details
- canvas defaults
- subtitle and timer flags
- format metadata for life-as-a or cinematic chapter behavior when needed

The settings matrix, not the preset wording, should push a scene through different paths such as AI image, AI video, visual treatments, FX, Eli, subtitles, canvas colors, or project-character mode.

## Run History

Persist run manifests under `data/test-lab/runs`. Keep only the newest 20 runs. Each run manifest stores:

- run id
- hidden script id
- selected dummy scene id
- settings snapshot
- status
- started/completed timestamps
- duration
- stage logs
- generated asset URLs
- render URL
- cost total and breakdown
- error details when failed

Selecting a history item should reload its preview, assets, settings snapshot, logs, and cost without rerunning generation. A clear-history action should delete only Test Lab manifests and Test Lab artifacts, never normal project data.

## Cost Tracking

The backend should reuse `ApiUsage` records and the timeline cost breakdown shape:

- task
- service
- operation
- model
- call count
- input/output tokens
- characters
- images
- total cost

Because Test Lab runs use hidden real scripts, the preferred attribution mechanism is `ApiUsage.script_id` on the hidden test script id. If one hidden script is reused across multiple runs, the backend must snapshot usage ids or timestamps per run so each history entry reports only its own cost.

## Behavioral Parity Rules

- Use production pipeline functions rather than Test Lab-specific approximations.
- Use real `ScriptContent`, `Scene`, `ProjectConfig`, and render props.
- Respect the existing Eli-disabled project-character gate. In project-character mode, generate/use a Test Lab character reference before visual generation or block with a clear stage error.
- Render with the same Remotion path used by scene preview or full render, narrowed to the selected single-scene content.
- Generated AI video must appear as a `Video` asset. Anchor/source images, when present, appear under `Image`.
- Visual treatment generated layer images should be labeled `Treatment Assets`, not `Panels`.
- Test Lab hidden records must never appear in the project dashboard or normal project list.

## Testing Plan

Backend tests should cover:

- dummy preset payloads validate as production `ScriptContent`/`Scene` structures
- hidden Test Lab scripts are excluded from normal script listing
- run manifests persist and the history cap deletes older entries beyond 20
- stage selection runs the expected production phases in order with fakes/mocks
- project-character mode requires or creates the required reference before visual generation
- generated AI video is reported under `Video`, not `Image`
- cost aggregation returns the same shape as project cost breakdowns and is scoped to one run
- clear history deletes Test Lab data only

Frontend verification should include:

- TypeScript build
- visual check of the Test tab layout in desktop viewport
- run flow with mocked or low-cost backend behavior where possible
- playable preview rendering when a run completes

## Documentation

After implementation, update `AGENTS.md` with a Test Lab convention: Test Lab must preserve production pipeline behavior, remain hidden from normal project lists, and exclude removed stock/gameplay/upload media paths.
