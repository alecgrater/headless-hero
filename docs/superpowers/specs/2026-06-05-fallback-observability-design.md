# Fallback Observability Design

## Goal

Headless Hero has many intentional fallback paths: visual modes downgrade, image generation may produce placeholders, thumbnails may skip enhancement, hook detection may use a deterministic count, and renderers may suppress optional behavior. These fallbacks keep projects moving, but they can hide quality problems when they happen too often.

Add structured fallback observability so developers can answer:

- What fallback paths happened recently?
- How often did each fallback happen?
- Which scripts/scenes were affected?
- Are any fallback paths happening often enough that they need product or pipeline fixes?

This is a dev-health feature, not a new user workflow.

## Recommended Scope

Build the first dedicated health analytics surface in the existing Dev Dashboard. Start with fallback visibility only, but structure it so future analytics sections can reuse the pattern.

Do not broaden this pass into a full pipeline analytics dashboard. Cost, cache, model-performance, and project-readiness analytics are good follow-up surfaces, but fallback visibility has a sharper immediate quality-risk goal.

## Event Model

Add a small backend helper, tentatively `pipeline.fallback_observability.record_fallback`, that emits a standard log event through the existing SQLite dev logging pipeline.

The emitted log message should have a stable prefix and JSON payload:

```text
[FALLBACK] {"category":"visual_mode","event":"ai_video_downgraded","from":"video","to":"full_frame","reason":"Adjacent AI-video scene","script_id":"...","scene_id":"...","severity":"warn"}
```

Fields:

- `category`: broad area, such as `visual_mode`, `image_generation`, `thumbnail`, `hook_detection`, `subtitle_timing`, `render`, or `test_lab`.
- `event`: stable machine-readable fallback name.
- `reason`: human-readable reason.
- `from`: optional original mode/provider/state.
- `to`: optional fallback mode/provider/state.
- `script_id`: optional script/project id when available.
- `scene_id`: optional scene id when available.
- `segment_index`: optional zero-based segment index when useful.
- `severity`: `info`, `warn`, or `fail`.
- `metadata`: optional small JSON object for event-specific facts such as provider, cap, duration, cache marker, or asset path basename.

The helper should also choose the Python log level from `severity`:

- `info`: expected fallback, useful for counts.
- `warn`: quality-risk fallback that should be reviewed if frequent.
- `fail`: fallback saved the workflow from crashing but produced degraded or missing output.

Metadata must avoid secrets, OAuth data, full script text, full prompts, local absolute generated asset paths, and other sensitive payloads. Short IDs, basenames, visual modes, provider names, durations, counts, and concise reasons are acceptable.

## API

Add `/dev/api/fallbacks/stats` in `backend/dev/routes.py`.

Inputs:

- `hours`: default `24`, capped to a safe upper bound such as `168`.
- `category`: optional category filter.
- `limit`: default recent example limit.

Behavior:

- Query `DevLog` rows whose message starts with `[FALLBACK]`.
- Parse the JSON payload after the prefix.
- Ignore malformed payloads, but include a small `malformed_count` for debugging.
- Return aggregate counts and recent examples.

Response shape:

```json
{
  "window_hours": 24,
  "total": 14,
  "malformed_count": 0,
  "by_category": [{"category": "visual_mode", "count": 8}],
  "by_event": [{"event": "ai_video_downgraded", "category": "visual_mode", "count": 5}],
  "by_reason": [{"reason": "Adjacent AI-video scene", "count": 4}],
  "by_severity": {"info": 3, "warn": 10, "fail": 1},
  "hot_events": [
    {"event": "image_placeholder_created", "category": "image_generation", "count": 3, "severity": "fail"}
  ],
  "recent": [
    {
      "id": 123,
      "timestamp": "...",
      "logger_name": "pipeline.image_gen",
      "category": "image_generation",
      "event": "image_placeholder_created",
      "reason": "AI image generation failed and scraper fallback unavailable",
      "script_id": "...",
      "scene_id": "...",
      "severity": "fail"
    }
  ]
}
```

`hot_events` should initially be simple and explainable:

- any `fail` event in the window
- any `warn` event with count at least `3`
- any event count that is at least `50%` of total fallback events in the window when total is at least `4`

This is a heuristic, not a blocking quality gate.

## Dev Dashboard UI

Add a `Fallbacks` tab to `backend/dev/dashboard.html`.

The tab should include:

- Time-window selector: `1h`, `24h`, `7d`.
- Category selector.
- Summary cards: total fallback events, warn/fail count, most common category, hottest event.
- Counts by category.
- Counts by event.
- Top reasons.
- Recent examples table with time, severity, category, event, script, scene, reason, and module.

The UI should be dense and operational, matching the existing Dev Dashboard style. It should not add marketing copy or a large hero section.

When a recent example is clicked, reuse the existing log detail modal or show equivalent fields inline. The important part is being able to move from aggregate count to concrete examples quickly.

## Initial Instrumentation

Instrument high-signal fallback paths first:

1. `backend/pipeline/media_analyzer.py`
   - AI-video planned/assigned scenes downgraded to non-video.
   - Validator omitted a scene and the analyzer defaulted to planned mode or `full_frame`.
   - Adjacent AI-video assignment removed.

2. `backend/pipeline/image_gen.py`
   - AI image generation falls back to scraped web image.
   - AI image generation falls back to local placeholder.
   - Popup protagonist anchor unavailable and transparent fallback is used.

3. `backend/pipeline/hook_detector.py`
   - Hook detection LLM call fails and deterministic fallback count is used.
   - Hook detector response cannot be parsed and deterministic fallback count is used.

4. `backend/pipeline/thumbnail.py`
   - Gemini thumbnail enhancement falls back to the base image.
   - Split-progression thumbnail lacks enough source levels and uses the clean image.

5. `backend/pipeline/audio_alignment.py`
   - Word timings are estimated instead of aligned from provider data.

6. Test Lab visual-mode fallbacks where already implemented.

This first pass does not need to find every fallback in the repository. It needs a clear helper, dashboard surface, and enough instrumentation to catch common silent degradation.

## Testing

Backend tests:

- helper emits `[FALLBACK]` with parseable JSON and redacted/safe fields.
- stats endpoint counts events by category, event, reason, and severity.
- stats endpoint ignores malformed fallback log rows and reports `malformed_count`.
- hot event heuristics mark fail events and frequent warn events.

Frontend/dashboard tests are not currently formalized for `backend/dev/dashboard.html`. Cover the route/API behavior with backend tests, and manually verify the dashboard loads and renders the Fallbacks tab.

## Documentation And Conventions

Update `AGENTS.md` with a new convention:

Any new fallback that affects generation, rendering, export, integrations, caching, background jobs, or visual output should call the structured fallback helper. Free-text `logger.warning` is still fine for local detail, but it should not be the only observability for a meaningful fallback.

If the implementation changes the end-to-end project workflow, update the in-app docs. This change only adds dev observability and does not alter the user workflow, so no in-app workflow doc page is required for the initial implementation.

## Follow-Up Analytics Ideas

Keep these out of the first implementation unless they become trivial extensions:

- Pipeline stage success/failure rates.
- API cost outliers by project, model, provider, and stage.
- Cache reuse, stale invalidation, and regeneration rates.
- Model/provider parse failures and retry rates.
- Project readiness checks before publishing.
- Quality-risk rollups for placeholders, stale media, missing assets, and overlong scenes.

## Acceptance Criteria

- Structured fallback events are persisted in the existing `dev_logs` table.
- `/dev/api/fallbacks/stats` returns useful aggregates and recent examples.
- The Dev Dashboard has a Fallbacks tab that surfaces frequency, severity, hot events, and examples.
- At least the initial high-signal fallback paths are instrumented.
- Tests cover the helper and stats endpoint.
- `AGENTS.md` documents the fallback-observability convention.
