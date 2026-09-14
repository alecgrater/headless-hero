# Two-Style Subtitles — Implementation Plan

Design: `docs/superpowers/specs/2026-09-14-two-style-subtitles-design.md`

**Execution mode: inline.** The plan is near-literal, and the tasks are one tightly
coupled edit chain — two threshold constants, one style enum, and one settings key set
that must stay consistent across Python, Remotion TS, and the frontend simultaneously.
Re-establishing that shared context per subagent would be pure waste, and the whole-diff
`code-reviewer` pass at the end supplies the independent quality gate either way.

---

## Task 1 — Backend: thresholds, style set, routing inputs

`backend/pipeline/remotion_render.py`

- `SUBTITLE_STYLES = ("clean", "kinetic")`
- `SUBTITLE_ROUTER_VERSION = "standard-subtitle-router-v2"`
- Add `KINETIC_MAX_WORDS = 6`, `KINETIC_MAX_SPAN_SECONDS = 3.0`
- `subtitle_settings_from_env()` — drop the per-style env loop for `clean` (always on)
  and `burst` (gone); read only `SUBTITLE_STYLE_KINETIC_ENABLED`. Emit
  `{coverage, enabled_styles, kinetic_max_words, kinetic_max_span_seconds}`.
- `_subtitle_punch_score()` — delete the burst-cue term and the ≤190/≤240 ms pace terms;
  keep the short-and-terminal-punctuation term and the visual-mode term.
- Add `resolve_subtitle_style(scene, settings)` mirroring the router, for the log line.
- `render_full_video()` — emit one `logger.info` with the clean/kinetic/suppressed split.

`backend/models/script.py`
- `SubtitleStyle = Literal["auto", "clean", "kinetic", "none"]`
- `SUBTITLE_STYLES = {"auto", "clean", "kinetic", "none"}` (so stored `"burst"` → `"auto"`)

## Task 2 — Backend: settings + identity

`backend/api/settings.py`
- `SUBTITLE_STYLE_KEYS = {"kinetic": "SUBTITLE_STYLE_KINETIC_ENABLED"}`
- Remove `SUBTITLE_STYLE_CLEAN_ENABLED` / `SUBTITLE_STYLE_BURST_ENABLED` from the key
  lists and `_DEFAULTS`.

`backend/pipeline/identity.py`
- Drop the two removed keys from the export allowlist; keep coverage + kinetic.

## Task 3 — Remotion: router

`remotion/src/effects/typography/subtitleRouting.ts`
- `SUBTITLE_ROUTER_VERSION = "standard-subtitle-router-v2"`
- Delete `BURST_CUES`, `FAST_WORD_MS`, `DENSE_WORD_COUNT`.
- `KINETIC_MAX_WORDS = 6`, `KINETIC_MAX_SPAN_SECONDS = 3.0` as fallback defaults;
  prefer the values off `settings`.
- `resolveSubtitleStyle` — suppression unchanged; explicit style wins; else
  `words <= max && span <= maxSpan ? kinetic : clean`, then clamp via a collapsed
  `resolveDisabledFallback` (kinetic disabled → clean).

`remotion/src/types.ts`
- `SubtitleStyle` loses `"burst"`; `SubtitleSettingsConfig` gains the two thresholds.

## Task 4 — Remotion: overlay

`remotion/src/effects/typography/Subtitles.tsx`
- `loadFont` from `@remotion/google-fonts/Inter`; one shared `fontFamily` handle.
- `SUBTITLE_BASE_SIZE = 52` (horizontal), vertical derived from the same base.
- Delete `BurstSubtitleOverlay`.
- `CleanSubtitleOverlay` — keep the plate; emphasis via `transform` + colour only.
- `KineticSubtitleOverlay` — rewrite as K2 (1.25× size, no plate, staggered y-offset
  entrance, harder pop, tighter tracking), porting the prototype CSS.
- **Invariant:** no per-word `fontSize`/`fontWeight` variation within a phrase.

## Task 5 — Frontend: types + settings UI

`frontend/src/types/script.ts` — `SubtitleStyle` loses `"burst"`.

`frontend/src/components/settings/SubtitlesSection.tsx`
- Replace the three-style list with coverage + a single "Kinetic accents" toggle;
  update the preview list and copy to describe the two-style behaviour and the rule.

## Task 6 — Test Lab

- `backend/pipeline/test_lab.py` — `_subtitle_style_from_settings` validates against the
  new set.
- `frontend/src/components/test-lab/TestLabControls.tsx` — drop any burst option.

## Task 7 — Tests

Update/extend per the design's Testing section:
`SubtitleRouting.test.ts`, `SubtitleOverlay.test.tsx`, `SubtitlesSection.test.tsx`,
`backend/tests/pipeline/test_remotion_render.py`, `backend/tests/test_identity_snapshot.py`,
plus a regression that `subtitle_style: "burst"` loads as `"auto"`.

## Task 8 — Docs

- `CLAUDE.md` Subtitles section — rewrite for the two-style catalogue, the rule, the
  threshold ownership, and the no-reflow invariant.
- Settings → Reference / docs components mentioning three styles, if any.

## Task 9 — Verify, commit, review

`npm run test:backend`, `npm run test:frontend`, `cd frontend && npm run build`,
`npx tsc --noEmit` in `remotion/`. Then commit + push to `main`, and run the
`code-reviewer` loop to LGTM.
