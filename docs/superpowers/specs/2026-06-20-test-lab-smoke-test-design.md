# Test Lab Smoke Test Design

## Goal

Add a one-click Test Lab tab that exercises the highest-risk project-generation surfaces after recent visual-mode work and returns a clear pass/warn/fail report with next actions.

## User Experience

The Test Lab gets a new `Smoke Test` tab next to `Scene Pipeline`, `Popup Crop`, and `Blink`. The tab has one primary button, `Run Smoke Test`, plus compact toggles for expensive probes:

- `Render-heavy probes` defaults on because the feature exists to catch render failures.
- `External API asset generation` defaults off so the first pass can avoid unnecessary provider cost.

The result view shows a checklist grouped by area, with `pass`, `warn`, or `fail` status, a short detail, optional evidence, optional render/run links, and a specific next action. A summary row counts passes, warnings, and failures.

## Backend Architecture

Create `backend/pipeline/test_lab_smoke.py` as the smoke-test orchestrator. It owns the diagnostic catalog and keeps API routing thin. The first version performs deterministic local checks and optionally launches a small set of existing Test Lab runs through `run_test_lab`.

The API adds:

- `POST /api/test-lab/smoke-test`

The request accepts booleans for render-heavy probes and external API probes. The response is a serializable report with an id, started/completed timestamps, summary counts, and check rows.

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

## Documentation

No in-app workflow page is required for the first version because the feature is self-contained inside Test Lab and does not change the production project workflow. The Test Lab UI text explains the scope directly.
