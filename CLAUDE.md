# Headless Hero — CLAUDE.md

## Self-Maintenance

**When a new convention, rule, or architectural decision is established during a session, update this file before committing.** Keep it current; it is the source of truth for how this project works.

**When adjusting the end-to-end project workflow, update the relevant in-app docs in the same change or explicitly determine whether a new doc page should be added.** Workflow changes should not live only in code, prompts, or memory.

## Forward-Only Design Bias

Prefer the simplest, best design for the product going forward over extra work that preserves old project compatibility or carries legacy baggage. Do not add migration shims, compatibility layers, fallback branches, or old-data support by default.

When a planned change may break existing local projects, exported assets, cached renders, saved settings, or older script JSON, call that risk out clearly before implementation so the user can verify the specific compatibility concern. After calling it out, still plan around the forward-looking design and ignore old-project support unless the user explicitly says that particular case must be preserved.

## Review Findings → Always Apply Fixes

**Any time code review produces findings — from the auto-commit loop, a manual `/review`, or pasted review output — immediately implement every recommended fix.** Do NOT just report findings or ask whether to apply them. Read, edit, commit, and push. Fix FAIL items first, then WARN items; skip findings explicitly marked "non-blocking" or "optional".

## Auto-commit Rule

**Every time a feature or fix is completed, run this full loop in one turn; do NOT stop, pause, or wait for user input:**

1. Stage the relevant files, write a descriptive commit message, and push to `main`
2. Dispatch a code review using the **Agent tool** (NOT `/review`, which produces visible output and ends the turn). Use `subagent_type: "superpowers:code-reviewer"` with this prompt:
   ```
   Review the most recent commit on the main branch of this project.
   Run `git diff HEAD~1..HEAD` to see the changes and `git show --stat HEAD` for context.
   Read the full affected files (not just the diff) to understand surrounding code.
   Check for: correctness bugs, error handling gaps, security issues, naive/aware datetime mismatches, unhandled promise rejections, race conditions, and style problems.
   Return a structured verdict: either LGTM or NEEDS CHANGES.
   If NEEDS CHANGES, provide a numbered list of findings with severity (FAIL/WARN), file:line, and a specific description of what's wrong and how to fix it.
   ```
   Agent results are invisible tool output, so you can process the review and continue without ending the turn.
3. **Process the review verdict internally. Do NOT output any review findings to the user.** Your next action after receiving the agent result MUST be either a tool call (Edit/Bash) to fix issues, or writing the final summary — never bare text about the review.
4. If the verdict is **NEEDS CHANGES**: immediately implement every required fix (FAIL items first, then WARN items). Commit as `fix: address review findings` and push.
5. Dispatch another code review agent. Repeat steps 3-4 until the verdict is **LGTM**.
6. Only after **LGTM** — surface a single summary to the user: what was built, what the review caught (briefly), and what was fixed.

**Why Agent instead of /review**: `/review` produces visible text, which Claude treats as a completed turn. Agent output stays invisible, allowing the loop to continue.

**This rule is non-negotiable**: every code change, no matter how small, must end with a commit on `main`, a push to remote `main`, and at least one subagent code review returning **LGTM**. No "I'll review it myself" or "too small to review" exceptions.

### Worktree-Driven Development

Worktree-driven development (via `superpowers:using-git-worktrees` or manual `git worktree add`) is allowed and encouraged for isolated feature work. **The auto-commit rule still applies:** merge the worktree branch back into `main`, push remote `main`, and run the subagent review loop against the merge commit or squashed commit on `main`. A worktree is not done until its changes are on remote `main` and have passed subagent review; finish integration in the same session.

## Project Overview

AI-powered Electron desktop app for creating faceless educational YouTube content. Full pipeline: idea → script → visuals → voice → video → publish.

**Stack:** Electron 41 + React 19/Vite/TypeScript/Tailwind 4 frontend + Python 3.12/FastAPI backend + Remotion 4 video rendering + FFmpeg internal audio processing + SQLite

## Dev Commands

```bash
npm run dev              # Start backend + frontend + electron (all three)
npm run dev:frontend     # Frontend only (Vite on :5173)
npm run dev:backend      # Backend only (uvicorn on :8420)
npm run test             # Backend pytest suite (shells into uv run --project backend pytest)
npm run test:backend     # Same as: uv run --project backend pytest
npm run test:frontend    # Frontend Vitest suite
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

Do not run `uv run pytest` from the repo root; the Python project and pytest dependency live in `backend/`. `npm run test` is fine because it shells into the backend project.

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
  src/scenes/      → Scene components per visual_mode (StaticImage, MultiFrame, Caption, TitleCard, ShortTitleCard, Subtitle, Video, plus StaticCanvas/TreatmentRenderer/VerticalSceneLayout)
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
- Most Settings panels use framed section headers: keep parent section titles/descriptions visually framed above controls with `text-xl font-semibold tracking-tight` headings inside the subtle rounded purple title box (`-ml-4 rounded-2xl border border-violet-500/40 bg-violet-500/5 px-4 py-3`), and keep embedded subsections and individual control/item labels smaller (`text-sm`) without the parent title box.
- Settings → Subtitles is intentionally a denser console layout: use a two-column section grid with the section explanation on the left and the control on the right, a compact segmented control for coverage, and a divided preview list for enabled styles. Do not wrap the Subtitles section labels in title boxes or turn each choice into a standalone card.

### Frontend State & Formatting
- No external state library — `useState()` at page level, pass down via props
- Double quotes, trailing commas, 2-space indentation

### Feature UX & Dev Observability
- When adding a feature, sizable behavior change, or any new UI element/option, check that the UI is the most intuitive representation of the behavior, including naming, placement, defaults, disabled states, and workflow fit.
- When designing or implementing frontend UI, use the available in-app browser/browser-preview tooling frequently during the work, not only at the end. Check the real running page after meaningful layout or interaction changes, inspect desktop and mobile-ish widths when relevant, and iterate until spacing, overflow, disabled states, loading/error states, and visual hierarchy look right in the browser.
- When adding any feature that introduces new scene visual functionality, add equivalent Test tab/Test Lab support in the same change so the behavior can be manually tested before generating a full script.
- Add concise hints, helper text, descriptions, or tooltips next to new controls when the behavior is not immediately obvious.
- Add success, warning, error, status, or info logs to the dev dashboard when the new behavior affects generation, rendering, export, integrations, caching, background jobs, or other pipeline-visible state.

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
Optional: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` (YouTube publishing), `RUNWAYML_API_SECRET` or `FAL_API_KEY` (AI video scenes)

Stored in DB via AppSettings, loaded into env at startup. Never commit `.env` files.

## Key Patterns

- **JSON blobs over migrations**: Script content stored as JSON TEXT in SQLite — no migration burden
- **Exports directory is the single final-media root**: User-facing exported assets live under the Settings → General → Storage `Exports` directory (default lives in `backend/config.DEFAULT_EXPORTS_DIR` — currently `~/Headless Hero Videos` for the dev user). Project folders use `{Exports}/[project] {Project Title}` with the project title sanitized for filesystem safety. Do not add a second export/download root.
- **Exported videos are deduped when possible**: Rendered MP4 exports should go through `pipeline.export_paths.copy_to_project_downloads`, which hardlinks same-drive video exports instead of byte-copying them. Keep the internal render path and user-facing export path compatible, and fall back to a normal copy only when hardlinking is unavailable (for example, cross-device exports).
- **Async rendering with polling**: Long renders run in background threads, frontend polls `/api/render/status/{job_id}`
- **IPC fallback**: Frontend works with or without Electron (direct HTTP to backend in dev)
- **Static file serving**: FastAPI mounts `/static/projects` → `data/projects/`
- **No auth**: Single-user desktop app
- **Test Lab mirrors production behavior**: The Test tab uses hidden real `Script` and `ProjectConfig` records plus the same production pipeline functions as normal projects. Keep Test Lab records out of project lists/dashboards, persist only the last 20 run manifests under `data/test-lab/runs`, and do not reintroduce removed stock photo, gameplay video, or user-upload media paths into Test Lab settings.
- **Test Lab visual mode changes preserve scene text**: Clicking a visual style/mode such as `captions`, `multi_frame`, `continuous`, `popup_sequence`, `flipflop`, or `stat_card` must not rewrite the current narration, visual prompt, caption text, or stat fields. Mode-specific demo text belongs in presets or explicit user edits, not automatic mode-switch defaults.
- **Short-form hook detection before render/export**: Before short-form render, rendered-status, export, or short-form SEO work, populate `ScriptContent.hook_scene_count` via `api.short_form_hooks.ensure_short_form_hook_scene_count`. If short #1 skips hook scenes, cache validity depends on the sidecar metadata in `data/projects/{script_id}/renders/shorts/0.json`; older unmarked short #1 renders must be treated as stale and re-rendered.
- **Segments must stand alone as shorts**: Scene narration must end each segment cleanly on that segment's topic because any segment may be exported as a standalone short. Keep whole-video recaps, subscribe requests, "come back next week", and other CTAs out of scene narration; `outro_cta` is metadata/editor copy unless a dedicated long-form outro pipeline is added.
- **Short-form SEO titles are deterministic**: Generated short-form upload titles must be `{project title} - {segment title}`. Use the script record topic title as the project title when available, falling back to `ScriptContent.title`.
- **Project title is canonical in `Script.topic_title`**: Timeline title edits go through `/api/scripts/{script_id}/title`; generic full-script saves preserve `Script.topic_title` and must not let stale `ScriptContent.title` values roll back a title edit.
- **Project title edits retitle existing exports**: When `/api/scripts/{script_id}/title` changes a title, move existing export folders and title-based long-form filenames to the new sanitized title, refresh exported SEO markdown, and rewrite deterministic short-form SEO titles as `{new project title} - {segment title}`. If the previous title folder is missing, discover the export folder by matching the script's exported short-form asset filenames, then repair it to the canonical title.
- **Title-card thumbnails have no subtitle/kicker text**: Keep `ScriptContent.card_subtitle` empty. Thumbnail text is limited to the main card title and segment label badges; Gemini/reference enhancement prompts must not add copied or invented secondary phrases.
- **Long-form thumbnail regeneration preserves versions**: `data/projects/{script_id}/renders/thumbnails/0.png` is the active/exported thumbnail, but regeneration must archive the previous active image as the next numbered sibling before replacing `0.png`. UI surfaces should expose saved variants so users can compare or flip through them instead of losing old thumbnails.
- **Life-as-a long-form thumbnail labels are time periods**: Split-progression thumbnail text must use two cached time-period labels, not `LEVEL` labels. The left label is one of `3 months in` through `8 months in`; the right label is one of `8 years in` through `15 years in`. Persist the exact labels in the thumbnail sidecar so rerenders stay stable, and reroll them only on forced/regenerate flows.
- **Life-as-a split thumbnails use close centered subjects**: In split-progression long-form thumbnails, each side's protagonist must be framed close to camera (medium-close / waist-up by default), centered within that side's panel, and large enough to read clearly on mobile. Avoid distant full-room compositions where the character is small or pushed into a back corner.
- **Life-as-a split thumbnail labels must pop**: Time-period labels should use saturated thumbnail-yellow/gold fill, extra-thick black outline, and strong shadow/highlight treatment for mobile readability. Avoid muted cream labels that blend into bright backgrounds.
- **Life-as-a split thumbnail cache tracks prompts**: Split-progression thumbnail cache validity depends on the clean source image, exact time labels, and the rendered prompt fingerprint. Prompt wording changes must regenerate the Gemini-enhanced thumbnail instead of reusing stale output.
- **Life-as-a shorts show visible part labels, not SEO suffixes**: Short-form life-as-a renders and thumbnails display `Part {current}/{total}` on the title card and directly above the thumbnail image. Upload/SEO titles remain deterministic `{project title} - {segment title}` with no `(Part ...)` suffix. Cached short renders and thumbnails are stale when their stored part indicator does not match the current segment count/index.
- **Life-as-a title-card narration stores descriptors only**: Chapter-card scene narration should omit `Level N` and contain only the descriptor phrase, for example `The occasional.`. The TTS layer is the single place that adds `Level N` for spoken audio, with a defensive guard for older scripts that already include a level prefix.
- **Short-form subtitles sit above app chrome**: Vertical Remotion subtitles are top-aligned in the bottom blurred band so the subtitle box touches the bottom edge of the main image, keeping captions clear of Shorts/Reels/TikTok UI overlays.
- **Subtitle text hides hyphens at render time**: Script narration and word timing data keep hyphens for ElevenLabs pacing, but every on-screen subtitle renderer must format display text with `formatSubtitleText` so ASCII hyphens and Unicode dash variants never appear in standard subtitles, `aha_subtitle` scenes, or subtitle frame directives.
- **Standard subtitles route style per scene without extra LLM calls**: Normal subtitle rendering supports scene-level treatments (`auto`, `clean`, `kinetic`, `burst`, `none`) so a video can switch between readable subtitles, kinetic word-card subtitles, and bigger payoff bursts by scene. Missing values default to deterministic renderer-side `auto` routing from narration/word timing/scene shape; do not add a separate LLM call just to choose subtitle style. Settings → Subtitles owns global coverage (`SUBTITLE_COVERAGE_MODE=all|punchy`) and enabled style gates (`SUBTITLE_STYLE_{CLEAN|KINETIC|BURST}_ENABLED`); render cache fingerprints must include these settings. `visual_mode="captions"`, title cards, and legacy subtitle scenes continue to suppress standard subtitles in favor of their own renderer-owned text.
- **Test Lab subtitle and timer settings mirror production**: Test Lab must not expose per-run controls for standard subtitle style, subtitle highlighting, or segment timer. It shows read-only subtitle settings from Settings → Subtitles and links there for edits. Test Lab hidden scripts keep subtitle highlighting enabled, while segment timer stays on for every Test Lab run.
- **External links open in Chrome**: Electron main-process URL opening must route through the Chrome opener so app links ignore the operating system default browser.
- **ElevenLabs expressiveness uses settings, not narration rewrites**: Do not reintroduce the old non-title narration dramatizer or LLM punctuation pass. Send normal scene narration as-written, except `eleven_v3` may add deterministic hidden TTS-only audio tags. Title-card TTS framing (`Level N — ...`) remains the only automatic punctuation/text addition outside v3 tags. Settings → Voices owns the default ElevenLabs model, stability, style, and speed.
- **Eleven v3 hidden tags stay conservative**: App-added `eleven_v3` delivery tags are limited to restrained narration cues: `[curious]`, `[serious]`, `[thoughtful]`, `[confident]`, and `[reflective]`. Do not automatically add nonverbal/effect tags such as `[sighs]`, `[laughs]`, `[chuckles]`, `[whispers]`, or `[shouts]`; those may sound human in isolated ElevenLabs tests but are too risky for bulk generated voiceover.
- **Headless Hero Narrator is the preferred default voice**: Settings → Voices should sort and auto-select `Headless Hero Narrator` before fallback voices. `Liam - Viral Short-Form Storyteller` is the stronger shorts-style fallback, and `Adam Greene` is the friendlier backup. Do not restore legacy Lucan-first voice selection.
- **Settings must only persist visible ElevenLabs controls**: Settings → Voices shows only the saved narrator voices (`Headless Hero Narrator`, `Liam - Viral Short-Form Storyteller`, and `Adam Greene`) in the default voice selector. Model selection is two buttons for v2/v3. V2 shows preset buttons (`Steady`, `More Human`, `Dramatic`, `Custom`) and exposes stability/style/speed sliders only for `Custom`. V3 shows only stability, matching ElevenLabs' v3 UI; backend and API payloads must not pass hidden v2-only speed/style settings when `eleven_v3` is selected.
- **Post-voiceover checks must not rewrite scripts**: Duration/timing diagnostics may log overlong high-energy scenes, but must not call an LLM to tighten narration, mutate `Scene.narration`, or revoice scenes automatically after the script has been generated. Fix pacing in script prompts/post-processing before voiceover, or through explicit editor actions.
- **Scene-length protection happens before voiceover**: If generated scenes are too long, split them deterministically on existing sentence boundaries before any voice, image, or render assets are created. Preserve narration text exactly; do not use a post-audio LLM rewrite to solve pacing.
- **OpenAI reasoning by task**: Structured JSON/classification tasks (`fx`, `seo`, `short_form_seo`, `media`, `eli`, `analysis`, `hook_detect`, `script_rating`) default to `openai_reasoning_effort="minimal"` to preserve visible output budget; narrative/planning tasks (`script`, `idea`, `hook`) default to `low`. These are user-configurable in Settings → AI Models via `OPENAI_REASONING_EFFORT_<TASK>` keys.
- **Full-script rating is persisted on ScriptContent**: After script generation, `pipeline.script_rating.rate_script` runs in a fresh LLM call using the `script_rating` task (OpenAI `gpt-5-mini` by default), validates the 14-criterion rubric, recomputes category averages/overall locally, and stores the result in `ScriptContent.script_rating`. Dashboard summaries expose `script_rating_overall`; timeline UI shows the category breakdown. Do not reintroduce the removed unused `pipeline/script_reviewer.py` pass/fail Gemini reviewer or `SCRIPT_REVIEW_RUBRIC`.
- **Anthropic uses direct API model IDs**: Claude model defaults and Settings values must use Anthropic API ids like `claude-opus-4-7`, `claude-sonnet-4-6`, and `claude-haiku-4-5-20251001`, not AWS Bedrock ids like `anthropic.claude-...-v1:0`. The script task defaults to Anthropic/Claude and should remain easy to configure from Settings → API Keys and Settings → AI Models.
- **ElevenLabs duration as timing source of truth**: Scene duration in the Remotion timeline is derived from the ElevenLabs-generated audio duration, not estimated or manually set
- **Visual storytelling arc in scriptwriter**: Script generation prompts are structured to produce a coherent visual narrative arc across scenes, not just talking-head descriptions
- **Scene visual mode is canonical**: Scene routing uses one persisted/rendered/API field, `visual_mode`, with values `video`, `full_frame`, `multi_frame`, `continuous`, `popup_sequence`, `flipflop`, `comparison_board`, `stat_card`, and `captions`. Script generation may emit `full_frame`, `multi_frame`, `continuous`, `popup_sequence`, `flipflop`, `comparison_board`, `stat_card`, and `captions`; `video` remains a post-voiceover media analyzer promotion. Do not write `media_source` or `visual_treatment` into normal scene JSON, API payloads, frontend state, or Remotion props. Legacy `media_source="ai_video"` and layered `visual_treatment` values may be accepted only as one-way load/request normalization for old local data, then immediately converted to `visual_mode`. New backend routing, asset generation, UI controls, tests, and docs must read/write `visual_mode`. Legacy `quick_cuts` and `montage` visual beats are compatibility aliases for `multi_frame`; `continuous` is a canonical mode for same-scene progression.
- **Stat card is renderer-owned single-statistic display**: `visual_mode="stat_card"` displays one giant headline `stat_value` plus optional supporting `stat_label` subtitle, with all readable text rendered by Remotion. The only generated asset is an optional transparent supporting icon cutout via a single `visual_layers` entry; no scene image, no frame sequence, no AI-video promotion. Standard subtitles and Eli are suppressed for the beat. Distribution is capped at MAX 1-2 per video and never back-to-back; use only when narration genuinely revolves around one decisive percentage, financial figure, population count, duration, distance, ranking, odds, risk factor, or scientific measurement.
- **New visual modes must start from the guardrail doc**: Before adding, renaming, or changing any scene `visual_mode`, read `docs/visual-mode-design-guardrails.md` and ensure the mode has a distinct purpose, routing rules, deterministic scene JSON shape, Remotion behavior, Test Lab coverage, cache invalidation, fallback behavior, export behavior, dev observability, tests, and no semantic conflict with existing modes.
- **`VideoFormat` is the declarative source of truth for script-type reference data**: The `VideoFormat` dataclass in `backend/pipeline/formats/` owns each script type's reference metadata, including `supported_visual_modes` and `reference_notes` (curated `FormatNote` gotchas grouped by category). These are surfaced through the existing `/api/formats` endpoint and rendered read-only by the Settings → Reference → "Script Types" page (`frontend/src/components/settings/script-types/`). Adding a new script type means registering its `VideoFormat` with these fields filled in — the comparison matrix and gotchas panel update automatically with no frontend edits. These fields are reference-only (NOT enforced during generation); keep `supported_visual_modes` consistent with actual prompt/routing behavior, and reflect any per-format visual-mode disablement (e.g. life-as-a omitting `captions`/`stat_card`) here so the reference stays accurate.
- **Captions visual mode is renderer-owned editorial text**: `visual_mode="captions"` is a static-canvas punch mode with optional side imagery plus large in-scene `caption_text` and red `caption_emphasis`. It is not standard subtitle rendering and must suppress normal bottom subtitles during the caption beat. Fresh script generation emits the fields in the existing script call; do not add a required extra LLM call or render readable caption text inside generated images. Legacy `aha_subtitle` visual beats normalize into `captions` for compatibility.
- **AI video scenes are routed, then generated from anchor images**: When `AI_VIDEO_ENABLED=true`, visual mode analysis may assign up to the larger of the requested animated scene count and `segment count × AI_VIDEO_SCENES_PER_SEGMENT` as `visual_mode="video"` (default two per segment). Generation first creates the normal styled scene image, then sends that anchor image to the configured `AI_VIDEO_PROVIDER` (`runway` by default, or `fal`) so motion preserves the existing visual format. Runway uses Gen-4 Turbo; Fal uses Wan 2.2 image-to-video turbo by default via `FAL_VIDEO_MODEL`. Track the follow-up to move candidate selection into script generation in `docs/ai-video-followups.md`.
- **AI video routing is segment-distributed and spaced**: Visual mode analysis should strongly target up to `AI_VIDEO_SCENES_PER_SEGMENT` eligible non-title-card video scenes per segment, skipping only segments with no suitable eligible motion candidates. Post-processing must preserve valid LLM choices but fill missing segment slots deterministically rather than accepting sparse video output, and must never leave two back-to-back scenes as `visual_mode="video"`.
- **Scene visual modes are AI-only**: The app no longer offers or assigns gameplay clips, stock photos, or user-uploaded scene media. Scene visual routing may use only first-party AI image, AI video, and layered AI asset modes; deprecated gameplay/stock/upload request fields must be ignored or coerced back to AI generation.
- **Media analysis requires voiceover durations**: Do not run media source analysis until every scene has generated voiceover timing (`audio_duration_seconds > 0`). AI-video eligibility depends on real audio length, so both UI and API flows must block analysis before voiceover exists.
- **Layered visual modes render over a global static canvas**: Every scene has a video-level `visual_canvas.background_color` beneath it. `full_frame`, `multi_frame`, `continuous`, and `video` cover the canvas through their normal media paths, while `popup_sequence`, `flipflop`, and `comparison_board` stage their own assets over the canvas. Remotion chooses layered renderers directly from `visual_mode`; do not reintroduce a `visual_treatment` render prop. Script generation may choose layered modes from scene intent, while post-voiceover layered mode analysis fills timing/layer assets for explicit layered modes and may infer missing layered opportunities only when timing data exists (`audio_duration_seconds > 0` and non-empty `word_timestamps` for non-title scenes).
- **Only media-backed modes generate normal scene images/frames**: `full_frame` generates a normal scene image, while `multi_frame` and `continuous` generate normal scene frame sequences. Layered modes have their own asset generation and render pipeline. Test Lab, batch image generation, manual visual regeneration, and export image phases must skip/clear `Scene.image_url` and `frame_urls` for `video`, `popup_sequence`, `flipflop`, and `comparison_board`, then generate only the mode-specific assets (`video_url`, `visual_layers`, popup cutouts, flip-flop cutouts, comparison cutouts, etc.).
- **Continuous frame references use generated frames only**: For `continuous` progression, frame 1 may use the active style preset image to establish house style, but later `reference_previous` frames must use the prior generated frame as their only image reference. Do not also attach the style preset image to continuation frames; the prior frame already carries the style, and extra style images can leak preset subjects/characters into object-only scenes. Continuation prompts must still include the shared scene brief plus explicit middle/final progression instructions so the event advances across frames.
- **Normal generated images are always full-bleed**: Any prompt path that can generate a normal scene image or sequence frame must include the shared full-bleed/no-border boundary rules from `pipeline.image_gen` and must not ask for framed panels, picture mats, poster edges, cards, borders, or margins. Popup-sequence chroma cutouts, flip-flop cutouts, and contact sheets may use isolated/cropping-specific layout rules, but they must still forbid frames, borders, labels, and text.
- **Popup cutout experiments separate anchors from item sheets**: Test Lab popup-crop work should generate the scene's anchored character/focus separately from the popup item sheet so the character can keep the active protagonist/reference style while items share a simpler icon/cutout style. Popup item sheets should arrange items left-to-right in the UI-specified order, use a flat chroma background color that does not appear in the subjects, then key out the sampled background and auto-trim each crop with padding.
- **Test Lab popup sequence fallback uses three panels**: When Test Lab is explicitly set to `popup_sequence` and no analyzer-produced `visual_layers` are available, derive three fallback panel assets from the single scene-level `visual_prompt`/narration, spaced left/center/right across the scene. Production analyzer output with its own layer count still wins when available.
- **Popup sequence renders use cropped cutouts, not generated panels**: `popup_sequence` scenes must generate one isolated anchor character/subject plus one contact-sheet image for the popup items, crop those into transparent cutouts, and persist the resulting cutout layers for Remotion. Do not call Gemini once per popup item to create full framed panel images; flip-flop also uses compatible cropped cutout states rather than full framed panels.
- **Popup sequence has no scene image layer**: Test Lab and production popup-sequence renders should not generate or depend on a full scene image. The visible render is the canvas color plus one clean standing anchor cutout and the cropped popup item cutouts.
- **Popup sequence items orbit clockwise**: In Remotion, `popup_sequence` keeps the anchor cutout fixed in the center while item cutouts pop in at their `enter_at_seconds` voiceover timings, then join a shared clockwise orbit around the anchor.
- **Popup sequence cutout wrappers stay invisible**: Remotion must not add wrapper backgrounds, clipping, borders, or box shadows around `asset_kind="cutout"` popup-sequence layers. Any visible shadow should come from the cutout artwork itself, not a rectangular layer container.
- **Flip-flop is cropped-subject character/body-language micro-animation**: Use `visual_mode="flipflop"` for same-subject cropped A/B micro-animation where compatible transparent character/body-language cutouts alternate over the canvas, such as talking mouth changes, head tilts, pointing, leaning, shrugging, pacing, holding an object, opening/closing, typing, stirring, sorting, or counting. Do not use flip-flop for generic contrast between different ideas, time periods, unrelated emotional states, full-environment changes, locations, or outcomes. Object-only flip-flops require explicit object-action narration.
- **Flip-flop cutouts alternate from frame zero over canvas**: Remotion must render flip-flop layers as transparent cutouts staged over `visual_canvas.background_color`, not full-bleed panels that cover the canvas. The scene should alternate across all available states from the first frame; `enter_at_seconds` may describe analysis timing but must not create an initial A-only hold before B starts participating.
- **Comparison board is renderer-owned contrast layout**: Use `visual_mode="comparison_board"` when narration contrasts two or three subjects, concepts, states, levels, choices, or outcomes such as Before vs After, Myth vs Reality, Rich vs Poor, Human vs Neanderthal, Prisoner vs Guard, Success vs Failure, or Good Choice vs Bad Choice. Generate transparent cutouts for the compared subjects only; Remotion owns columns, dividers, VS markers, arrows, badges, stat chips, and all readable labels. Avoid this mode for a single environment/event, ordinary item lists, same-subject micro-animation, or process progression.
- **Reusable crop cutouts go to the asset vault**: Any generated image that is cropped into a reusable transparent cutout, including Popup Crop Lab character anchors and item sheet crops, must save the cleaned cutout PNG under `data/projects/asset-vault/{characters,items}`. Keep v1 vault metadata filename-only: `{character|item}_{descriptive_slug}_{YYYYMMDD_HHMMSS}_{shortid}.png`; do not add JSON sidecars until reuse/search needs outgrow filenames.
- **Life-as-a uses long-form-only opening selection**: `life-as-a` projects use the same pre-script cold-open selection workflow as listicles, but with a life-as-a-specific opening prompt and rubric focused on second-person immersion, immediate role fantasy, stakes/discomfort, progression curiosity, and title alignment. These opening scenes are long-form-only and must be skipped from short #1 via the shared `hook_scene_count` prefix-trimming mechanism. Do not route life-as-a selected openings through listicle hook scoring/refinement.
- **Life-as-a scenes are short render beats**: Non-title `life-as-a` scenes target 5-9 seconds and one visual/narrative beat. The post-processor splits overlong scenes before voiceover. The short-scene seconds setting gates AI-video routing duration only; generated-image scenes may keep multiple frames whenever the visual beat calls for progression or quick contrast.
- **AI video can slow down only as a small safety net**: If an AI-generated video clip is shorter than scene narration, Remotion may slow the clip down only when the required duration increase is 25% or less. Larger gaps must fall back to the anchor image/full audio duration and log a warning instead of cutting the scene short.
- **Life-as-a protagonist visuals follow the active character mode**: In `life-as-a` scripts, any visible main subject/protagonist/role scene (for example a guard in "Your Life As A Guard") must depict the active recurring character as the visually dominant main character in that role. When Eli is enabled, this is Eli. When Eli is disabled, this is the active character selected for the active style preset and synced into `ScriptContent.main_character` for render compatibility. Secondary people may appear, but must be visually distinct from the active protagonist. Object-only or atmosphere shots may omit the protagonist. For `life-as-a`, AI video animation is eligible only for these active-protagonist scenes.
- **Eli-disabled image generation requires a preset-scoped character reference first**: When Eli is disabled, do not generate scene images, title/chapter images, thumbnails that use `generate_scene_image`, or AI-video anchor images until an active style preset exists and that preset has an active character with a reference image. Project generation syncs the preset-scoped character reference to `data/projects/{script_id}/character/reference.png` as an implementation detail. Never silently fall back to anonymous characters, Eli, or a character from another style preset in this mode.
- **Style preset characters are scoped to their preset**: Settings → Style Presets is the source of truth for both visual style presets and their characters. Characters are generated from the selected style preset, listed only under that preset, and can only be selected for projects using that preset. Do not reintroduce a separate global main-character tab or global character source of truth.
- **Character references keep originals and cutouts**: Character generation workflows persist both the original reference image and a transparent cropped cutout. The original reference remains canonical for image-model reference chaining and human review; the cutout is a derived compositing asset for Popup Crop Lab, Remotion layers, character walk-ons, thumbnails, and other staged visuals. Shared single-character background removal lives in `pipeline.character_assets`; do not add workflow-specific character removebg code.
- **Eli-disabled main characters inherit the selected preset style**: When Eli is turned off and a main character reference is generated, the character identity may differ by preset, but the reference image must match the selected style preset image. Never prompt these reference images as photorealistic, cinematic film stills, 3D renders, realistic lens effects, or painterly concept art unless the selected preset itself explicitly establishes that non-house style.
- **Style preset rows must be image-backed**: Settings style presets are valid only when both the `style_presets` row and `data/style/presets/{id}.png` exist. Read-only style preset API calls hide stale fileless rows without deleting database data; tests that generate presets must use an isolated test engine instead of writing fake rows into the dev `data/db.sqlite`.
- **AI-video scenes are not photo scenes in UI labels**: Any browsing/review UI that displays frame/photo counts must suppress those counts for `ai_video` scenes and should explicitly mark those rows as video scenes.
- **Video scenes end at clip duration**: Remotion scene props must cap video-backed scenes to the actual local clip duration when it is shorter than narration/audio duration. Do not silently loop clips or let Remotion hold the final frame while camera FX continue.

## Video Rendering (Remotion)

Remotion 4 (React-based frame-by-frame renderer) instead of FFmpeg filter graphs. Python writes scene data + FX config to JSON → invokes `npx remotion render` via subprocess → picks up output MP4. Renders entire video as a single `FullVideo` composition (enables native transitions and global timeline).

Export bundles must not generate or include standalone long-form audio MP3 files. Scene audio remains internal pipeline media for timing and video rendering only.

**FX**: AI-generated via Claude (not manually edited). Each scene has an optional `fx: SceneFX` field. Active effect: `zoom_punch`. FX timing adjustable via scene micro-timeline.

**Transitions**: Each scene has `transition_in` (cut, fade_black, flash_white, wipe). Claude assigns transitions alongside FX. `SceneTransition` component wraps visual+subtitle+Eli layers; audio plays through. All output is 1920x1080 YouTube 16:9.

## Eli Character Overlay

"Eli" is an optional recurring animated host character overlaid on videos (like a Twitch streamer webcam box). Pre-generated frame library (~150 poses × 2 mouth states) via Gemini with reference image chaining + rembg background removal. Character design spec in `backend/prompts/character.py`.

When Eli is disabled, the active style preset's scoped character takes the protagonist role instead — see the Eli-disabled / style-preset character rules in Key Patterns.

Claude generates per-scene animation documents (keyframe timelines selecting pose/expression per frame range). Mouth state derived from `phrase_timestamps`, not animation documents. Eli Remotion render component is **not yet implemented**.

## Scene Micro-Timeline

Per-scene micro-timeline in the preview panel for frame-precise visual timing control. Uses `forwardRef` imperative API for keyboard shortcuts. Conditional lanes: InOutLane (always), ImageLane (multi-frame), FxLane (zoom_punch), EliLane (eli keyframes). Timing fields (`frame_timings`, `visual_in_seconds`, `visual_out_seconds`) stored in script_json blob.
