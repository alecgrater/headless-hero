# Headless Hero — CLAUDE.md

## Self-Maintenance

**When a new convention, rule, or architectural decision is established during a session, update this file to reflect it before committing.** Keep the document accurate and current — it is the source of truth for how this project works.

## Auto-commit Rule

**Every time a feature or fix is completed, automatically commit and push the changes.** Do not wait for the user to ask — stage the relevant files, write a descriptive commit message, and push to `main`. Follow the commit message conventions below.

## Project Overview

AI-powered Electron desktop app for creating faceless educational YouTube content. Full pipeline: idea → script → visuals → voice → video → publish.

**Stack:** Electron 41 + React 19/Vite/TypeScript/Tailwind 4 frontend + Python 3.12/FastAPI backend + FFmpeg + SQLite

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
  components/      → Feature-grouped (brand/, storyboard/, etc.)
  types/           → TypeScript interfaces (one file per domain)
  api.ts           → API client with Electron IPC / fetch fallback
backend/
  api/             → FastAPI endpoints (routing, validation only)
  pipeline/        → Business logic (no web framework imports)
  integrations/    → Thin external API wrappers (Claude, Gemini, ElevenLabs, YouTube)
  models/          → SQLModel tables + Pydantic schemas (no logic)
  pipeline/modifiers/  → Content modifier plugin system
data/              → Runtime data (SQLite DB, generated assets) — gitignored
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
- Prefix: `/api/{feature}` (e.g., `/api/brands`, `/api/scripts`)
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

## Content Modifiers (Plugin System)

To add a new modifier:
1. Create class in `backend/pipeline/modifiers/` inheriting `ContentModifier`
2. Register in `backend/pipeline/modifiers/__init__.py`
3. It auto-appears in BrandForm UI and hooks into the pipeline

Available hooks: `modify_script_prompt()`, `modify_script_post()`, `modify_scene_pre_render()`, `get_render_override()`, `get_full_render_override()`, `get_router()`

## Git Conventions

### Commit Messages
- Imperative, present tense: "Add feature", "Fix bug", "Update behavior"
- Format: `{Add|Fix|Update|Remove|Refactor} {what} {optional context}`
- One feature or fix per commit
- Descriptive enough that another developer understands the change

Examples:
```
Add short-form video pipeline for YouTube Shorts, TikTok, and Instagram Reels
Fix download buttons navigating away from app instead of downloading
Update Real Media modifier to encourage mix of real footage and AI art
```

## Environment Variables

Required: `ANTHROPIC_API_KEY`, `GOOGLE_AI_KEY`, `ELEVENLABS_API_KEY`
Optional: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` (YouTube publishing)

Stored in DB via AppSettings, loaded into env at startup. Never commit `.env` files.

## Key Patterns

- **JSON blobs over migrations**: Script content stored as JSON TEXT in SQLite — no migration burden
- **Async rendering with polling**: Long renders run in background threads, frontend polls `/api/render/status/{job_id}`
- **IPC fallback**: Frontend works with or without Electron (direct HTTP to backend in dev)
- **Static file serving**: FastAPI mounts `/static/projects` → `data/projects/`
- **No auth**: Single-user desktop app
