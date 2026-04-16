# Headless Hero — CLAUDE.md

## Self-Maintenance

**When a new convention, rule, or architectural decision is established during a session, update this file to reflect it before committing.** Keep the document accurate and current — it is the source of truth for how this project works.

## Auto-commit Rule

**Every time a feature or fix is completed, automatically commit and push the changes.** Do not wait for the user to ask — stage the relevant files, write a descriptive commit message, and push to `main`. Follow the commit message conventions below.

### Post-commit: Gemini Code Review

After every feature or fix commit, run an automated Gemini code review:

```bash
gemini -p "$(cat ~/.claude/commands/review.md)"
```

Then:
1. Read the full Gemini output.
2. If the verdict is **LGTM** — report this to the user and continue.
3. If the verdict is **NEEDS CHANGES** — treat Gemini's numbered action list as a new task. Fix each item, then commit and push in a single follow-up commit. Do not run Gemini again on that follow-up commit.
4. Tell the user the Gemini verdict in one line: either "Gemini: LGTM" or "Gemini: NEEDS CHANGES — fixed [x, y, z]".
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

## Backend Conventions (Python)

### Type Annotations
Use modern Python 3.12 syntax — no `typing.List`, `typing.Optional`:
```python
def generate(niche: str, count: int = 10, brand: str | None = None) -> list[VideoIdea]:
```

### Naming
- Files: `snake_case.py`
- Classes: `PascalCase`
- Functions/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private: `_leading_underscore`
- Request/response schemas: `{Action}{Noun}Request` / `{Action}{Noun}Response`

### Module Boundaries
- `api/` — FastAPI routers only. Validate input, call pipeline, return response. Use `Depends(get_session)` for DB.
- `pipeline/` — Pure business logic. No FastAPI imports. Orchestrate integrations.
- `integrations/` — Thin wrappers. Raise `RuntimeError` if API keys missing.
- `models/` — SQLModel tables + Pydantic schemas. No business logic.

### Database Patterns
- SQLModel with `table=True` for DB tables
- UUIDs: `Field(default_factory=lambda: uuid.uuid4().hex, primary_key=True)`
- Timestamps: `Field(default_factory=lambda: datetime.now(timezone.utc))`
- Large content stored as JSON TEXT blobs (e.g., `script_json`), deserialized via Pydantic `model_validate(json.loads(...))`
- Queries: `select()` + `session.exec()`

### API Endpoints
- Prefix: `/api/{feature}` (e.g., `/api/brand`, `/api/scripts`)
- Always specify `response_model=`
- Status codes: 201 (create), 204 (delete), 404/422 (errors)
- Errors: `HTTPException(status_code=..., detail="...")`
- Background jobs: in-memory dict + threading, frontend polls status

### Logging
```python
logger = logging.getLogger(__name__)
```
Log progress and failures — not every variable.

### Imports
Order: stdlib → third-party → local. Group by functionality.

## Frontend Conventions (TypeScript/React)

### Component Structure
- Files: `PascalCase.tsx` for components, `camelCase.ts` for utilities
- Export: `export default function ComponentName() { ... }`
- Props: interface named `Props`, declared before component
- Event handlers: `handle{Action}` internally, `on{Action}` for props

### State Management
- No external state library — `useState()` at page level, pass down via props
- Page components own data fetching and state
- Presentational components receive data + callbacks via props

### Styling
- Tailwind 4 utility classes only — no CSS files
- Dark theme: `bg-neutral-950/900`, `text-neutral-100/400`
- Accent colors: `violet-*`, `sky-*`, `emerald-*`
- Always include `hover:` + `transition-colors` for interactive elements

### API Client
- `frontend/src/api.ts` — global client with Electron IPC / direct fetch fallback
- `assetUrl(path)` for static file URLs
- Global error interceptor shows toasts automatically

### TypeScript
- Strict mode enabled
- Interfaces for object shapes in `src/types/`
- No `any` — use proper types or `unknown`
- Double quotes, trailing commas, 2-space indentation

## Brand Profile

The app uses a **single auto-created default brand** (no multi-brand picker). The brand stores `voice_id` and `youtube_channel_id`. It's auto-created on backend startup via `ensure_default_brand()`.

- `GET /api/brand` — returns the single default brand
- `PUT /api/brand` — updates voice_id, youtube_channel_id, etc.
- All endpoints auto-resolve brand_id from the default brand (no brand_id in request bodies)

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

Video rendering uses **Remotion 4** (React-based frame-by-frame renderer) instead of FFmpeg filter graphs. FFmpeg is still used for audio concat export only.

### Data Bridge
Python writes scene data + FX config to JSON → invokes `npx remotion render` via subprocess → picks up output MP4. Orchestrated by `backend/pipeline/remotion_render.py`.

### Compositions
- **FullVideo** — Renders entire video as one composition (all segments sequenced with transitions)

### Scene Types
- `StaticImageScene` — Single image with zoom punch or parallax motion
- `MultiFrameScene` — N images with crossfade between them
- `TitleCardScene` — Spring zoom into circle target
- `SubtitleScene` — White text on black (aha_subtitle beat)

### FX System
Visual effects are AI-generated (no manual editing of the FX *assignment* itself). Each scene has an optional `fx: SceneFX` field. Active FX:
- **zoom_punch** — Quick zoom-in camera punch for emphasis

Standard phrase-based subtitles are rendered automatically from `word_timestamps` (no AI generation needed). Subtitle scenes (`aha_subtitle`) show text synced to voiceover timing.

FX are generated via Claude (`POST /api/fx/generate`) and can be regenerated per-scene (`POST /api/fx/regenerate`). The `backend/pipeline/fx_generator.py` sends scene context to Claude and parses the structured FX response.

FX *timing* (trigger frame, crossfade points, etc.) can be manually adjusted via the scene micro-timeline — see below.

### YouTube 16:9 Only
All video output is 1920x1080 YouTube format.

## Eli Character Overlay

"Eli" is a recurring animated host character overlaid on videos, like a Twitch streamer's webcam box in the corner. Character design spec lives in `backend/prompts/character.md`.

### Frame Library
Pre-generated library of ~150 character frames (150 pose/expression combos × 2 mouth states = ~300 total). Stored in `data/character/frames/` with a `manifest.json`. Generated via Gemini with reference image chaining for consistency. Background removal via `rembg`. **Chest-up framing** — head in upper third, shoulders and upper chest visible, cut off below chest (Twitch streamer webcam style).

#### Reference Selection Workflow
Two-step process in Settings → Character:
1. Generate 15 reference candidate images with subtle style variations (stored in `data/character/references/`)
2. Select one as the canonical reference → copied to `data/character/frames/selected_reference.png`
3. All frame generation and regeneration uses the selected reference for consistency

- `backend/pipeline/character_frames.py` — Frame generation pipeline + reference candidate generation/selection
- `backend/api/character.py` — `POST /api/character/generate-references`, `GET /api/character/references`, `POST /api/character/select-reference`, `POST /api/character/generate-frames`, `GET /api/character/frames`, `GET /api/character/status/{job_id}`, `POST /api/character/regenerate-frame`
- Settings UI: `frontend/src/components/settings/CharacterSection.tsx`

### Animation Documents
Claude generates per-scene keyframe timelines selecting which Eli pose to show at which frame range. Follows the same pattern as FX generation.

- `backend/pipeline/eli_animator.py` — Claude-powered animation director
- `backend/api/eli.py` — `POST /api/eli/generate`, `POST /api/eli/regenerate`
- Scene field: `eli_overlay: dict | None` in script_json (stores `EliOverlay` with `keyframes: list[EliKeyframe]`)
- Mouth state is NOT in animation documents — computed deterministically in Remotion from `word_timestamps`

### Render Layer Stack
1. Visual layer (StaticImage/MultiFrame/TitleCard/Subtitle)
2. ZoomPunch camera effect
3. **EliOverlay** (z-index: 5) — not yet implemented as a Remotion component
4. Subtitles (z-index: 10) — `remotion/src/effects/typography/Subtitles.tsx`
5. Audio layer
6. ChapterIndicator (z-index: 30)

### Gemini Reference Images
`google_image_client.py` supports `reference_image_path` — loads the image as a multi-modal Part for cross-frame character consistency.

## Scene Micro-Timeline

Per-scene micro-timeline in the preview panel for frame-precise visual timing control. Appears below the Remotion player when a scene with audio is selected. Design spec: `docs/superpowers/specs/2026-04-15-scene-micro-timeline-design.md`.

### Scene Timing Fields (stored in script_json blob)
- `frame_timings: list[float] | None` — seconds into scene when each frame starts; `None` = even split (default)
- `visual_in_seconds: float = 0.0` — visual appears this many seconds into the audio (black → fade in)
- `visual_out_seconds: float = 0.0` — visual ends this many seconds before audio ends (fade out → black)

All fields are backward-compatible — null/0 means use current auto-calculated behavior. No new API endpoints; changes flow through the existing `updateScene()` → auto-save pipeline.

### Architecture
- `frontend/src/components/timeline/SceneMicroTimeline.tsx` — Container with `forwardRef` imperative API for keyboard shortcuts
- `frontend/src/components/timeline/micro-timeline/shared.ts` — Shared types (`LaneProps`, `MarkerDragState`), time↔pixel helpers, word-snap utility
- `frontend/src/components/timeline/micro-timeline/InOutLane.tsx` — Draggable left/right handles for visual in/out
- `frontend/src/components/timeline/micro-timeline/ImageLane.tsx` — Draggable crossfade markers for multi-frame scenes
- `frontend/src/components/timeline/micro-timeline/FxLane.tsx` — Draggable zoom punch trigger marker
- `frontend/src/components/timeline/micro-timeline/EliLane.tsx` — Draggable Eli keyframe boundary markers

### Lane Visibility
Lanes appear conditionally based on scene content:
- **InOutLane** — Always visible (every scene can have visual trim)
- **ImageLane** — Only if `frame_urls.length > 1` (multi-frame scenes)
- **FxLane** — Only if `fx.zoom_punch` is set
- **EliLane** — Only if `eli_overlay.enabled` and has keyframes

### Interaction Patterns
- Markers snap to word boundaries by default; hold **Shift** to disable snap for sub-word precision
- Double-click In/Out handles to reset to zero
- Keyboard: `1-4` select lanes, `[`/`]` nudge 1 frame (Shift for 10), `S` split at playhead, `M` place marker, `Esc` deselect
- `?` or keyboard icon in header opens grouped shortcut cheat sheet (`ShortcutHelpOverlay`)
- Stale marker warning shown when audio is regenerated and manual timings exist

### Remotion Rendering
- `MultiFrameScene.tsx` — Uses `frame_timings` when provided instead of even-split calculation
- `SceneRenderer.tsx` — Wraps visual+subtitle layer in opacity div for `visual_in/out_seconds` fade; audio plays through unaffected
