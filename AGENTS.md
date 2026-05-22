# Headless Hero — AGENTS.md

## Self-Maintenance

**When a new convention, rule, or architectural decision is established during a session, update this file to reflect it before committing.** Keep the document accurate and current — it is the source of truth for how this project works.

## Review Findings → Always Apply Fixes

**Any time a code review produces findings — whether from the auto-commit agent loop, a manual review run, or review output pasted by the user — immediately implement every recommended fix.** Do NOT just report findings and stop. Do NOT ask the user whether to apply them. Read the findings, edit the code, commit, and push. FAIL-severity items first, then WARN items (skip items explicitly marked "non-blocking" or "optional").

## Auto-commit Rule

**Every time a feature or fix is completed, run this entire loop in a single turn — do NOT stop, pause, or wait for user input at any step:**

1. Stage the relevant files, write a descriptive commit message, and push to `main`
2. Dispatch a code review using Codex's agent delegation tooling with this prompt template:
   ```
   Review the most recent commit on the main branch of this project.
   Run `git diff HEAD~1..HEAD` to see the changes and `git show --stat HEAD` for context.
   Read the full affected files (not just the diff) to understand surrounding code.
   Check for: correctness bugs, error handling gaps, security issues, naive/aware datetime mismatches, unhandled promise rejections, race conditions, and style problems.
   Return a structured verdict: either LGTM or NEEDS CHANGES.
   If NEEDS CHANGES, provide a numbered list of findings with severity (FAIL/WARN), file:line, and a specific description of what's wrong and how to fix it.
   ```
   Keep the review inside the tool flow so you can process the findings before writing the final user-facing summary.
3. **Process the review verdict internally. Do NOT output any review findings to the user.** Your next action after receiving the agent result MUST be either a tool call (Edit/Bash) to fix issues, or writing the final summary — never bare text about the review.
4. If the verdict is **NEEDS CHANGES**: immediately implement every required fix (FAIL items first, then WARN items). Commit as `fix: address review findings` and push.
5. Dispatch another code review agent. Repeat steps 3-4 until the verdict is **LGTM**.
6. Only after **LGTM** — surface a single summary to the user: what was built, what the review caught (briefly), and what was fixed.

**Why use delegated review**: Keep the review inside Codex's tool flow so you can apply findings and continue the loop without stopping at a visible review-only response.
 
## Project Overview

AI-powered Electron desktop app for creating faceless educational YouTube content. Full pipeline: idea → script → visuals → voice → video → publish.

**Stack:** Electron 41 + React 19/Vite/TypeScript/Tailwind 4 frontend + Python 3.12/FastAPI backend + Remotion 4 (video rendering) + FFmpeg + SQLite

## Dev Commands

```bash
npm run dev              # Start backend + frontend + electron (all three)
npm run dev:frontend     # Frontend only (Vite on :5173)
npm run dev:backend      # Backend only (uvicorn on :8420)
npm run test             # Backend pytest suite from repo root
npm run test:backend     # Same as: uv run --project backend pytest
cd frontend && npm run build  # Production frontend build
```

## Python — Always Use UV

**Never use `python`, `python3`, `pip`, or `pip3` directly.** All Python operations go through `uv`:

- `uv run python script.py` — run scripts
- `uv run --project backend pytest` — run backend tests from the repo root
- `cd backend && uv run pytest` — run backend tests from inside `backend/`
- `uv pip install pkg` — install packages
- `uv add pkg` — add project dependency
- `uv sync` — install from lockfile
- `uv venv` — create virtual environment

Do not run `uv run pytest` from the repo root; the Python project and pytest dependency live in `backend/`.

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
  integrations/    → Thin external API wrappers (Anthropic, Gemini, ElevenLabs, YouTube)
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
Optional: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` (YouTube publishing), `REPLICATE_API_TOKEN` (alternative image provider), `RUNWAYML_API_SECRET` or `FAL_API_KEY` (AI video scenes)

Stored in DB via AppSettings, loaded into env at startup. Never commit `.env` files.

## Key Patterns

- **JSON blobs over migrations**: Script content stored as JSON TEXT in SQLite — no migration burden
- **Exports directory is the single final-media root**: User-facing exported assets live under the Settings → General → Storage `Exports` directory, defaulting to `~/Headless Hero Videos`. Project folders use `{Exports}/[project] {Project Title}` with the project title sanitized for filesystem safety. Do not add a second export/download root.
- **Async rendering with polling**: Long renders run in background threads, frontend polls `/api/render/status/{job_id}`
- **IPC fallback**: Frontend works with or without Electron (direct HTTP to backend in dev)
- **Static file serving**: FastAPI mounts `/static/projects` → `data/projects/`
- **No auth**: Single-user desktop app
- **Short-form hook detection before render/export**: Before short-form render, rendered-status, export, or short-form SEO work, populate `ScriptContent.hook_scene_count` via `api.short_form_hooks.ensure_short_form_hook_scene_count`. If short #1 skips hook scenes, cache validity depends on the sidecar metadata in `data/projects/{script_id}/renders/shorts/0.json`; older unmarked short #1 renders must be treated as stale and re-rendered.
- **Segments must stand alone as shorts**: Script scene narration must end each segment cleanly on that segment's own topic because any segment may be exported as a standalone short. Keep whole-video recaps, subscribe requests, "come back next week", and other channel CTAs out of scene narration; `outro_cta` is metadata/editor copy unless a dedicated long-form-only outro pipeline is added.
- **Short-form SEO titles are deterministic**: Generated short-form upload titles must be `{project title} - {segment title}`. Use the script record topic title as the project title when available, falling back to `ScriptContent.title`.
- **Project title is canonical in `Script.topic_title`**: Timeline title edits go through `/api/scripts/{script_id}/title`; generic full-script saves preserve `Script.topic_title` and must not let stale `ScriptContent.title` values roll back a title edit.
- **Project title edits retitle existing exports**: When `/api/scripts/{script_id}/title` changes a title, existing export folders and title-based long-form filenames move to the new sanitized project title, exported SEO markdown is refreshed, and deterministic short-form SEO titles are rewritten as `{new project title} - {segment title}`. If the exact previous title folder is missing, discover the project export folder by matching the script's exported short-form asset filenames, then repair it to the canonical title.
- **Title-card thumbnails have no subtitle/kicker text**: Keep `ScriptContent.card_subtitle` empty. Thumbnail text is limited to the main card title and segment label badges; Gemini/reference enhancement prompts must not add copied or invented secondary phrases.
- **Long-form thumbnail regeneration preserves versions**: `data/projects/{script_id}/renders/thumbnails/0.png` is the active/exported thumbnail, but regeneration must archive the previous active image as the next numbered sibling before replacing `0.png`. UI surfaces should expose saved variants so users can compare or flip through them instead of losing old thumbnails.
- **Life-as-a long-form thumbnail labels are time periods**: Split-progression thumbnail text must use two cached time-period labels, not `LEVEL` labels. The left label is one of `3 months in` through `8 months in`; the right label is one of `8 years in` through `15 years in`. Persist the exact labels in the thumbnail sidecar so rerenders stay stable, and reroll them only on forced/regenerate flows.
- **Life-as-a split thumbnails use close centered subjects**: In split-progression long-form thumbnails, each side's protagonist must be framed close to camera (medium-close / waist-up by default), centered within that side's panel, and large enough to read clearly on mobile. Avoid distant full-room compositions where the character is small or pushed into a back corner.
- **Life-as-a split thumbnail labels must pop**: Time-period labels should use saturated thumbnail-yellow/gold fill, extra-thick black outline, and strong shadow/highlight treatment for mobile readability. Avoid muted cream labels that blend into bright backgrounds.
- **Life-as-a split thumbnail cache tracks prompts**: Split-progression thumbnail cache validity depends on the clean source image, exact time labels, and the rendered prompt fingerprint. Prompt wording changes must regenerate the Gemini-enhanced thumbnail instead of reusing stale output.
- **Life-as-a shorts show visible part labels, not SEO suffixes**: Short-form life-as-a renders and thumbnails display `Part {current}/{total}` on the title card and directly above the thumbnail image. Upload/SEO titles remain deterministic `{project title} - {segment title}` with no `(Part ...)` suffix. Cached short renders and thumbnails are stale when their stored part indicator does not match the current segment count/index.
- **Short-form subtitles sit above app chrome**: Vertical Remotion subtitles are top-aligned in the bottom blurred band so the subtitle box touches the bottom edge of the main image, keeping captions clear of Shorts/Reels/TikTok UI overlays.
- **Subtitle text hides hyphens at render time**: Script narration and word timing data keep hyphens for ElevenLabs pacing, but every on-screen subtitle renderer must format display text with `formatSubtitleText` so ASCII hyphens and Unicode dash variants never appear in standard subtitles, `aha_subtitle` scenes, or subtitle frame directives.
- **External links open in Chrome**: Electron main-process URL opening must route through the Chrome opener so app links ignore the operating system default browser.
- **OpenAI reasoning by task**: Structured JSON/classification tasks (`fx`, `seo`, `short_form_seo`, `media`, `eli`, `analysis`, `hook_detect`) default to `openai_reasoning_effort="minimal"` to preserve visible output budget; narrative/planning tasks (`script`, `idea`, `hook`) default to `low`. These are user-configurable in Settings → AI Models via `OPENAI_REASONING_EFFORT_<TASK>` keys.
- **Anthropic uses direct API model IDs**: Claude model defaults and Settings values must use Anthropic API ids like `claude-opus-4-7`, `claude-sonnet-4-6`, and `claude-haiku-4-5-20251001`, not AWS Bedrock ids like `anthropic.claude-...-v1:0`. The script task defaults to Anthropic/Claude and should remain easy to configure from Settings → API Keys and Settings → AI Models.
- **ElevenLabs duration as timing source of truth**: Scene duration in the Remotion timeline is derived from the ElevenLabs-generated audio duration, not estimated or manually set
- **Visual storytelling arc in scriptwriter**: Script generation prompts are structured to produce a coherent visual narrative arc across scenes, not just talking-head descriptions
- **AI video scenes are routed, then generated from anchor images**: When `AI_VIDEO_ENABLED=true`, media analysis may assign up to the larger of the requested animated scene count and `segment count × AI_VIDEO_SCENES_PER_SEGMENT` as `media_source="ai_video"` (default two per segment). Generation first creates the normal styled scene image, then sends that anchor image to the configured `AI_VIDEO_PROVIDER` (`runway` by default, or `fal`) so motion preserves the existing visual format. Runway uses Gen-4 Turbo; Fal uses Wan 2.2 image-to-video turbo by default via `FAL_VIDEO_MODEL`. Track the follow-up to move candidate selection into script generation in `docs/ai-video-followups.md`.
- **AI video routing is segment-distributed**: Media analysis should strongly target up to `AI_VIDEO_SCENES_PER_SEGMENT` eligible non-title-card AI video scenes per segment, skipping only segments with no suitable image-bearing motion candidates. Post-processing must preserve valid LLM choices but fill missing segment slots deterministically rather than accepting sparse AI video output.
- **Life-as-a protagonist visuals are Eli-led**: In `life-as-a` scripts, any visible main subject/protagonist/role scene (for example a guard in "Your Life As A Guard") must depict Eli as the visually dominant main character in that role. Secondary people may appear, but must be visually distinct from Eli. Object-only or atmosphere shots may omit Eli. For `life-as-a`, AI video animation is eligible only for these Eli-protagonist scenes.
- **Eli-disabled main characters still use the house art style**: When Eli is turned off and a project-specific main character reference is generated, the character identity may differ by topic, but the reference image must stay in the same Headless Hero flat 2D cartoon style as all other generated video art. Never prompt these reference images as photorealistic, cinematic film stills, 3D renders, or painterly concept art.
- **Video scenes are not photo scenes in UI labels**: Any browsing/review UI that displays frame/photo counts must suppress those counts for `ai_video`, `gameplay_video`, and uploaded-video scenes, and should explicitly mark those rows as video scenes.
- **Video scenes end at clip duration**: Remotion scene props must cap video-backed scenes to the actual local clip duration when it is shorter than narration/audio duration. Do not silently loop clips or let Remotion hold the final frame while camera FX continue.

## Video Rendering (Remotion)

Remotion 4 (React-based frame-by-frame renderer) instead of FFmpeg filter graphs. Python writes scene data + FX config to JSON → invokes `npx remotion render` via subprocess → picks up output MP4. Renders entire video as a single `FullVideo` composition (enables native transitions and global timeline).

Export bundles must not generate or include standalone long-form audio MP3 files. Scene audio remains internal pipeline media for timing and video rendering only.

**FX**: AI-generated via Codex (not manually edited). Each scene has an optional `fx: SceneFX` field. Active effect: `zoom_punch`. FX timing adjustable via scene micro-timeline.

**Transitions**: Each scene has `transition_in` (cut, fade_black, flash_white, wipe). Codex assigns transitions alongside FX. `SceneTransition` component wraps visual+subtitle+Eli layers; audio plays through. All output is 1920x1080 YouTube 16:9.

## Eli Character Overlay

"Eli" is a recurring animated host character overlaid on videos (like a Twitch streamer webcam box). Pre-generated frame library (~150 poses × 2 mouth states) via Gemini with reference image chaining + rembg background removal. Character design spec in `backend/prompts/character.md`.

Codex generates per-scene animation documents (keyframe timelines selecting pose/expression per frame range). Mouth state derived from `phrase_timestamps`, not animation documents. Eli Remotion render component is **not yet implemented**.

## Scene Micro-Timeline

Per-scene micro-timeline in the preview panel for frame-precise visual timing control. Uses `forwardRef` imperative API for keyboard shortcuts. Conditional lanes: InOutLane (always), ImageLane (multi-frame), FxLane (zoom_punch), EliLane (eli keyframes). Timing fields (`frame_timings`, `visual_in_seconds`, `visual_out_seconds`) stored in script_json blob.
