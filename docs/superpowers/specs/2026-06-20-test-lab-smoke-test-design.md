# Test Lab Smoke Test Design

## Goal

Add a one-click Test Lab tab that exercises the highest-risk project-generation surfaces after recent visual-mode work and returns a clear pass/warn/fail report with next actions.

## User Experience

The Test Lab gets a new `Smoke Test` tab next to `Scene Pipeline`, `Popup Crop`, and `Blink`. The tab has one primary button, `Run Smoke Test`, plus compact toggles for expensive probes:

- `Render-heavy probes` defaults on because the feature exists to catch render failures.
- `External API asset generation` defaults off so the first pass can avoid unnecessary provider cost.

The result view shows a checklist grouped by area, with `pass`, `warn`, or `fail` status, a short detail, optional evidence, optional render/run links, and a specific next action. A summary row counts passes, warnings, and failures.

Every smoke test report is saved under `data/test-lab/smoke-tests` so reports remain browsable after reload. The tab shows saved reports in newest-first order. Selecting an old report reloads its full checklist without rerunning diagnostics.

Each saved report can be re-exported as a Markdown fix brief. The brief starts with a direct request to fix the Headless Hero Smoke Test issues, then includes report id, timestamps, options, summary counts, failures, warnings, passed checks, run ids, render URLs, evidence, next actions, and raw report JSON. This is the preferred format for passing smoke-test results back into Codex.

## Backend Architecture

Create `backend/pipeline/test_lab_smoke.py` as the smoke-test orchestrator. It owns the diagnostic catalog and keeps API routing thin. The first version performs deterministic local checks and optionally launches a small set of existing Test Lab runs through `run_test_lab`.

The API adds:

- `POST /api/test-lab/smoke-tests`
- `GET /api/test-lab/smoke-tests`
- `GET /api/test-lab/smoke-tests/{report_id}`
- `GET /api/test-lab/smoke-tests/{report_id}/export`

The legacy `POST /api/test-lab/smoke-test` path remains as an alias for existing callers. The request accepts booleans for render-heavy probes and external API probes. The response is a serializable report with an id, started/completed timestamps, summary counts, and check rows.

## Checks

The first version checks:

- Visual-mode vocabulary includes the expected production modes.
- Blink remains guarded from production routing: production blink actions are empty, prompt guidance says not to choose blink, and policy text that still encourages blink is reported as a warning.
- Test Lab has presets for representative modes: `full_frame`, `captions`, `popup_sequence`, `comparison_board`, `stat_card`, and `blink`.
- Voice and subtitle summaries are readable from settings.
- Active style preset character availability is reported as pass or warning, not failure.
- Optional render-heavy probes run representative existing Test Lab presets and verify manifests complete and expose expected assets/render URLs.
- Optional external probes may create/reuse the blink fixture and render contexts once the user opts in.

## Error Handling

Each check catches its own exception and records a failed row. The endpoint itself should only fail for malformed requests or unexpected top-level infrastructure errors. Provider-consuming probes are opt-in and clearly labeled.

## Testing

Backend tests cover:

- Report shape and summary counts.
- Blink guardrail warning detection.
- Missing representative preset failure.
- API route returns the service result.

Frontend tests cover:

- Smoke Test tab appears.
- Clicking `Run Smoke Test` calls the endpoint with default options.
- Pass/warn/fail rows and recommended actions render.
- Saved reports are loaded, browsable, and re-exportable.
- Copy Fix Brief writes the backend-generated Markdown to the clipboard.

## Documentation

The in-app Workflow docs mention Test Lab -> Smoke Test as the broad readiness pass and direct users to copy the saved fix brief before continuing project media generation when issues appear.
