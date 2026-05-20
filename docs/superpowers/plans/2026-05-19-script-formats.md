# Script Formats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

## Context

Headless Hero today produces exactly one shape of video: an 8-segment, staccato-educational listicle. `SEGMENT_COUNT = 8` is hardcoded into the user message in `scriptwriter.py`, the system prompt prescribes a punchy mosaic style, ideation generates listicle-shaped titles, and the title-card system always composites an N-circle grid thumbnail.

We're adding a second format — **"Your Life As A..."** — a literary, second-person, level-by-level walk through a life path (4–7 levels), and we're refactoring the pipeline so a third format becomes mostly additive (a new module + a registry entry, not edits scattered across the codebase).

Source spec: `docs/superpowers/specs/2026-05-19-script-formats-design.md`. Read it before implementing.

**Goal:** Introduce a `format_id` concept that flows from ideation through script generation through rendering. Implement two formats (`youtube-listicle` and `life-as-a`), preserve existing behavior for old scripts, and produce an authoring guide so future format additions don't require re-reading the codebase.

**Architecture:** A `backend/pipeline/formats/` package holds a `VideoFormat` registry. Each format declares its prompts, generation flags (`supports_cold_open`, `supports_hook_scoring`, `supports_segmented_generation`), a `TitleCardStrategy` (composite-grid or cinematic-chapters), and a `VisualBeatRules` config. `generate_script()`, `generate_ideas()`, and the title-card pipeline become thin dispatchers over the registry. New `format_id` flows through the API; existing rows default to `youtube-listicle` via column default + defensive `resolve_format()`.

**Tech stack:** Python 3.12 / FastAPI / SQLModel / SQLite (uv-managed) backend, React 19 / TS / Tailwind 4 frontend, Remotion 4 renderer. All Python ops via `uv`. Tailwind utility classes only (no CSS files).

**Resolved open questions:**
- `life-as-a` uses **outline-then-levels segmented** generation (`supports_segmented_generation = True`).
- Chapter-card text overlay (`LEVEL N` / `THE DESCRIPTOR`) renders **in Remotion** via an extension to the existing `TitleCardScene` component (not a pre-rendered PNG).
- Tests are **light, mocked unit tests** matching the existing `backend/tests/` style.

## File map

**Backend — created:**
- `backend/pipeline/formats/__init__.py` — registry: `get_format`, `list_formats`, `resolve_format`
- `backend/pipeline/formats/base.py` — `VideoFormat` dataclass, `TitleCardStrategy` protocol, `VisualBeatRules`, `LevelMeta`
- `backend/pipeline/formats/youtube_listicle.py` — listicle format definition (wraps existing behavior)
- `backend/pipeline/formats/life_as_a.py` — new format definition
- `backend/pipeline/formats/title_cards/__init__.py`
- `backend/pipeline/formats/title_cards/composite_grid.py` — strategy wrapping current title_cards modifier behavior
- `backend/pipeline/formats/title_cards/cinematic_chapters.py` — new strategy
- `backend/api/formats.py` — `GET /api/formats` endpoint
- `backend/tests/pipeline/test_formats_registry.py` — registry resolution + defensive fallback
- `backend/tests/pipeline/test_life_as_a_post_processing.py` — life-as-a post-processing
- `docs/formats/AUTHORING.md` — Format Authoring Guide

**Backend — modified:**
- `backend/models/script.py` — `Script.format_id` column; `ScriptContent.format_id`, `cinematic_thumbnail_prompt`, `levels: list[LevelMeta] | None`; `LevelMeta` model; `format_id` on `GenerateIdeasRequest`/`GenerateScriptRequest`/`VideoIdea`
- `backend/database.py` — `_migrate_add_format_id_to_scripts()` migration, registered in `init_db()`
- `backend/prompts.py` — `LIFE_AS_A_SCRIPT_SYSTEM`, `LIFE_AS_A_IDEATION_SYSTEM`, `LIFE_AS_A_OUTLINE_INSTRUCTIONS`, `LIFE_AS_A_LEVEL_SCENES_INSTRUCTIONS`
- `backend/pipeline/scriptwriter.py` — accepts `format_id`, dispatches via `get_format()`, parameterizes `_fix_visual_monotony` over `VisualBeatRules`, conditionally invokes cold-open and hook-scoring
- `backend/pipeline/ideation.py` — accepts `format_id`, picks ideation prompt from registry, threads `format_id` onto returned `VideoIdea`
- `backend/api/ideas.py` — `format_id` on request, threaded through
- `backend/api/scripts.py` — `format_id` on request, persisted to `Script.format_id`; cold-open + hook-scoring gated by format flags
- `backend/api/__init__.py` — register the new formats router
- `backend/pipeline/remotion_render.py` — call `format.title_card_strategy.prepare_title_card_scene()` instead of importing the modifier directly
- `backend/api/visuals.py` — call `format.title_card_strategy.prepare_thumbnail()` instead of `ensure_title_card_images()` directly
- `backend/api/thumbnail.py` — same dispatch update for thumbnail generation
- `backend/models/__init__.py` (if it re-exports) — expose `LevelMeta`

**Remotion — modified:**
- `remotion/src/scenes/TitleCardScene.tsx` — accept optional `chapter_overlay` prop (`{level_number: int, descriptor: str}`); render two-line overlay when present
- `remotion/src/types.ts` — extend `Scene` input props with `chapter_overlay`

**Frontend — created:**
- `frontend/src/components/ideation/FormatSelector.tsx` — horizontal format-card row
- `frontend/src/components/script/CinematicChaptersPreview.tsx` — horizontal storyboard strip

**Frontend — modified:**
- `frontend/src/types/script.ts` — `format_id`, `levels`, `cinematic_thumbnail_prompt`, `LevelMeta` on `ScriptContent`; new `VideoFormat` type
- `frontend/src/types/idea.ts` — `format_id?: string` on `VideoIdea`
- `frontend/src/api.ts` — `getFormats()` function returning `VideoFormat[]`
- `frontend/src/components/ideation/IdeationPage.tsx` — render FormatSelector, persist selection in `localStorage`, send `format_id` in request, thread to `onUseIdea`
- `frontend/src/App.tsx` — pass `selectedIdea.format_id` to `ScriptGenerationPage`
- `frontend/src/components/script/ScriptGenerationPage.tsx` — fetch `/api/formats`, gate cold-open picker on `supports_cold_open`, swap "Segment N"→"Level N" via `format.level_label`, swap title-card preview UI by `title_card_strategy.kind`, send `format_id` to `/api/scripts/generate`
- `frontend/src/components/script/useScriptGeneration.ts` — accept `format_id`, gate cold-open phase

**Tests — created:** see `backend/tests/pipeline/test_formats_registry.py` and `backend/tests/pipeline/test_life_as_a_post_processing.py` above.

---

## Phase 1 — Schema, registry foundation, listicle wrapper

(See full task texts in the implementation log; tasks dispatched to subagents include the full per-task text.)

### Tasks

- Task 1: Add `format_id` to the Script table + ScriptContent
- Task 2: Format registry — base types and protocol
- Task 3: Registry tests — fallback and resolution
- Task 4: youtube-listicle format — wraps existing behavior
- Task 5: life-as-a prompts
- Task 6: life-as-a format definition + post-processor
- Task 7: cinematic-chapters strategy
- Task 8: life-as-a post-processing tests

## Phase 2 — Pipeline refactor (scriptwriter, ideation)

- Task 9: Refactor `_fix_visual_monotony` to take `VisualBeatRules`
- Task 10: Make `generate_script` format-aware
- Task 11: Make `generate_ideas` format-aware

## Phase 3 — API surface

- Task 12: `GET /api/formats` endpoint
- Task 13: Thread `format_id` through `/api/scripts/generate` and `/api/ideas/generate`
- Task 14: Title-card pipeline dispatches via strategy

## Phase 4 — Remotion overlay support

- Task 15: Add chapter-card text overlay to `TitleCardScene`

## Phase 5 — Frontend

- Task 16: Frontend types + format API client
- Task 17: Format selector on IdeationPage
- Task 18: Conditional UI on ScriptGenerationPage

## Phase 6 — Documentation

- Task 19: Format Authoring Guide

---

## Verification

- Backwards compat — no behavior change for existing scripts
- `youtube-listicle` end-to-end smoke (post-refactor)
- `life-as-a` end-to-end smoke
- Defensive fallback works (unknown format_id → composite-grid)
- All backend tests pass: `uv run pytest backend/tests/ -v`
- Frontend builds clean: `cd frontend && npm run build`
- Authoring guide is accurate

> Per-task implementation details are dispatched directly to subagents from the controller's task ledger; see commit history for the actual implementations.
