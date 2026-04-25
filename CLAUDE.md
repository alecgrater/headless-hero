# Headless Hero — CLAUDE.md

## Self-Maintenance

**When a new convention, rule, or architectural decision is established during a session, update this file to reflect it before committing.** Keep the document accurate and current — it is the source of truth for how this project works.

## Auto-commit Rule

**Every time a feature or fix is completed, run this entire loop in a single turn — do NOT stop, pause, or wait for user input at any step:**

1. Stage the relevant files, write a descriptive commit message, and push to `main`
2. Run `/review` on the pushed commit
3. **Read the review verdict internally. Do NOT output the review findings to the user.** Do NOT end your turn after the review — continue immediately in the same response.
4. If the verdict is **NEEDS CHANGES**: immediately start implementing every required fix (FAIL items first, then WARN items). Do NOT describe the review to the user. Just fix the code, commit as `fix: address review findings`, and push.
5. Run `/review` again. Repeat step 3-4 until the verdict is **LGTM**.
6. Only after **LGTM** — surface a single summary to the user: what was built, what the review caught (briefly), and what was fixed.

**Critical**: The review output is for YOU to process, not for the user to read. After `/review` completes, your next action must be either implementing fixes (if NEEDS CHANGES) or writing the summary (if LGTM). Never stop between review and action.

## Project Overview

AI-powered Electron desktop app for creating faceless educational YouTube content. Full pipeline: idea → script → visuals → voice → video → publish.

**Stack:** Electron 41 + React 19/Vite/TypeScript/Tailwind 4 frontend + Python 3.12/FastAPI backend + Remotion 4 (video rendering) + FFmpeg (audio export) + SQLite

## Dev Commands

```bash
npm run dev              # Start backend + frontend + electron (all three)
npm run dev:frontend     # Frontend only (Vite on :5173)
npm run dev:backend      # Backend only (uvicorn on :8420)
cd frontend && npm run build  # Production frontend build
```

## Python — Always Use UV

**Never use `python`, `python3`, `pip`, or `pip3` directly.** All Python operations go through `uv`:

- `uv run python script.py` — run scripts
- `uv pip install pkg` — install packages
- `uv add pkg` — add project dependency
- `uv sync` — install from lockfile
- `uv venv` — create virtual environment

## Architecture

```
electron/          → Main process + IPC preload bridge
frontend/src/      → React 19 + TypeScript + Tailwind 4
  components/      → Feature-grouped (timeline/, settings/, etc.)
  types/           → TypeScript interfaces (one file per domain)
  api.ts           → API client with Electron IPC / fetch fallback
backend/
  api/             → FastAPI endpoints (routing, validation only)
  pipeline/        → Business logic (no web framework imports)
  integrations/    → Thin external API wrappers (Claude, Gemini, ElevenLabs, YouTube)
  models/          → SQLModel tables + Pydantic schemas (no logic)
  pipeline/modifiers/title_cards.py → Title card prompt injection + post-processing
  config.py          → Shared constants (DATA_DIR, FPS, dimensions)
  dev/               → Dev dashboard (routes, log handler, HTML)
remotion/          → Remotion 4 video rendering project (React + TypeScript)
  src/scenes/      → Scene components (StaticImage, MultiFrame, TitleCard, Subtitle)
  src/effects/     → Composable FX (camera, typography, transitions, overlays, structural)
  src/types.ts     → Input props types mirroring Python SceneFX models
data/              → Runtime data (SQLite DB, generated assets) — gitignored
docs/              → PRD, setup guide, superpowers skills
```

## Conventions

### Module Boundaries
- `api/` — FastAPI routers only. Validate input, call pipeline, return response. Use `Depends(get_session)` for DB.
- `pipeline/` — Pure business logic. No FastAPI imports. Orchestrate integrations.
- `integrations/` — Thin wrappers. Raise `RuntimeError` if API keys missing.
- `models/` — SQLModel tables + Pydantic schemas. No business logic.

### Project-Specific Naming
- Request/response schemas: `{Action}{Noun}Request` / `{Action}{Noun}Response`
- Event handlers: `handle{Action}` internally, `on{Action}` for props

### Frontend Styling
- Tailwind 4 utility classes only — no CSS files
- Dark theme: `bg-neutral-950/900`, `text-neutral-100/400`
- Accent colors: `violet-*`, `sky-*`, `emerald-*`
- Always include `hover:` + `transition-colors` for interactive elements

### Frontend State & Formatting
- No external state library — `useState()` at page level, pass down via props
- Double quotes, trailing commas, 2-space indentation

## Brand Profile

Single auto-created default brand (no multi-brand picker). All endpoints auto-resolve brand_id — no brand_id in request bodies.

## Git Conventions

### Commit Messages
- Imperative, present tense: "Add feature", "Fix bug", "Update behavior"
- Format: `{Add|Fix|Update|Remove|Refactor} {what} {optional context}`
- One feature or fix per commit
- Descriptive enough that another developer understands the change

Examples:
```
Fix download buttons navigating away from app instead of downloading
Strengthen no-text-in-images instructions across prompt chain
Remove legacy FFmpeg video rendering pipeline
```

## Environment Variables

Required: `ANTHROPIC_API_KEY`, `GOOGLE_AI_KEY`, `ELEVENLABS_API_KEY`
Optional: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` (YouTube publishing), `REPLICATE_API_TOKEN` (alternative image provider)

Stored in DB via AppSettings, loaded into env at startup. Never commit `.env` files.

## Key Patterns

- **JSON blobs over migrations**: Script content stored as JSON TEXT in SQLite — no migration burden
- **Async rendering with polling**: Long renders run in background threads, frontend polls `/api/render/status/{job_id}`
- **IPC fallback**: Frontend works with or without Electron (direct HTTP to backend in dev)
- **Static file serving**: FastAPI mounts `/static/projects` → `data/projects/`
- **No auth**: Single-user desktop app
- **ElevenLabs duration as timing source of truth**: Scene duration in the Remotion timeline is derived from the ElevenLabs-generated audio duration, not estimated or manually set
- **Visual storytelling arc in scriptwriter**: Script generation prompts are structured to produce a coherent visual narrative arc across scenes, not just talking-head descriptions

## Video Rendering (Remotion)

Remotion 4 (React-based frame-by-frame renderer) instead of FFmpeg filter graphs. FFmpeg still used for audio concat export only. Python writes scene data + FX config to JSON → invokes `npx remotion render` via subprocess → picks up output MP4. Renders entire video as a single `FullVideo` composition (enables native transitions and global timeline).

**FX**: AI-generated via Claude (not manually edited). Each scene has an optional `fx: SceneFX` field. Active effect: `zoom_punch`. FX timing adjustable via scene micro-timeline.

**Transitions**: Each scene has `transition_in` (cut, fade_black, flash_white, wipe). Claude assigns transitions alongside FX. `SceneTransition` component wraps visual+subtitle+Eli layers; audio plays through. All output is 1920x1080 YouTube 16:9.

## Eli Character Overlay

"Eli" is a recurring animated host character overlaid on videos (like a Twitch streamer webcam box). Pre-generated frame library (~150 poses × 2 mouth states) via Gemini with reference image chaining + rembg background removal. Character design spec in `backend/prompts/character.md`.

Claude generates per-scene animation documents (keyframe timelines selecting pose/expression per frame range). Mouth state derived from `phrase_timestamps`, not animation documents. Eli Remotion render component is **not yet implemented**.

## Scene Micro-Timeline

Per-scene micro-timeline in the preview panel for frame-precise visual timing control. Uses `forwardRef` imperative API for keyboard shortcuts. Conditional lanes: InOutLane (always), ImageLane (multi-frame), FxLane (zoom_punch), EliLane (eli keyframes). Timing fields (`frame_timings`, `visual_in_seconds`, `visual_out_seconds`) stored in script_json blob.
