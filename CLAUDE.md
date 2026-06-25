# Headless Hero — CLAUDE.md

## Self-Maintenance

- When a new convention, rule, or architectural decision is established in a session, update this file before committing. It is the source of truth for how this project works.
- When the end-to-end workflow changes, update the relevant in-app docs in the same change (or decide a new doc page is needed). Workflow changes must not live only in code, prompts, or memory.

## Forward-Only Design Bias

Prefer the simplest best design going forward over preserving old-project compatibility. Do not add migration shims, compatibility layers, fallback branches, or old-data support by default. If a change may break existing local projects, exported assets, cached renders, saved settings, or older script JSON, call out that specific risk before implementing — then still design forward-looking and ignore old-project support unless the user explicitly says that case must be preserved.

## Review Findings → Always Apply Fixes

Whenever code review produces findings (auto-commit loop, manual `/review`, or pasted output), immediately implement every recommended fix — do not just report or ask. Fix FAIL items first, then WARN; skip findings marked "non-blocking" or "optional".

## Auto-commit Rule

Every time a feature or fix is completed, run this full loop in ONE turn — do NOT stop, pause, or wait for user input:

1. Stage relevant files, write a descriptive commit message, push to `main`.
2. Dispatch a code review via the **Agent tool** (NOT `/review`, which produces visible output and ends the turn), `subagent_type: "superpowers:code-reviewer"`, with a prompt asking it to: review the most recent commit (`git diff HEAD~1..HEAD`, `git show --stat HEAD`), read the full affected files, check for correctness bugs, error-handling gaps, security issues, naive/aware datetime mismatches, unhandled promise rejections, race conditions, and style problems, and return either `LGTM` or `NEEDS CHANGES` with a numbered list of findings (severity FAIL/WARN, file:line, fix).
3. Process the verdict internally — do NOT output any findings to the user. Your next action MUST be a tool call (Edit/Bash) to fix, or the final summary — never bare text about the review.
4. If **NEEDS CHANGES**: implement every fix (FAIL first, then WARN), commit as `fix: address review findings`, push.
5. Dispatch another review agent; repeat 3–4 until **LGTM**.
6. Only after **LGTM**, surface one summary: what was built, what review caught, what was fixed.

Non-negotiable: every change, however small, ends with a commit on `main`, a push to remote `main`, and at least one subagent review returning **LGTM**. No self-review or "too small" exceptions.

**Worktree-Driven Development**: Isolated feature work via worktrees is encouraged, but the auto-commit rule still applies — merge back to `main`, push remote `main`, and run the review loop against the merge/squash commit. A worktree is not done until its changes are on remote `main` and have passed review, finished in the same session.

## Project Overview

AI-powered Electron desktop app for faceless educational YouTube content. Pipeline: idea → script → visuals → voice → video → publish.

**Stack:** Electron 41 + React 19/Vite/TS/Tailwind 4 frontend + Python 3.12/FastAPI backend + Remotion 4 rendering + FFmpeg (internal audio only) + SQLite.

## Dev Commands

```bash
npm run dev              # backend + frontend + electron
npm run dev:frontend     # Vite on :5173
npm run dev:backend      # uvicorn on :8420
npm run test             # backend pytest (shells into uv run --project backend pytest)
npm run test:backend     # uv run --project backend pytest
npm run test:frontend    # frontend Vitest
cd frontend && npm run build
```

## Python — Always Use UV

Never use `python`, `python3`, `pip`, or `pip3` directly. Use `uv`:
- `uv run python script.py` — run scripts
- `uv run --project backend pytest` — backend tests from repo root
- `cd backend && uv run pytest` — backend tests from inside `backend/`
- `uv pip install pkg` / `uv add pkg` / `uv sync` / `uv venv`

Do not run `uv run pytest` from repo root (the project and pytest live in `backend/`); `npm run test` is fine.

## Architecture

```
electron/          → Main process + IPC preload bridge
frontend/src/      → React 19 + TS + Tailwind 4
  components/      → Feature-grouped (timeline/, settings/, etc.)
  types/           → TS interfaces (one file per domain)
  api.ts           → API client (Electron IPC / fetch fallback)
backend/
  api/             → FastAPI endpoints (routing, validation only)
  pipeline/        → Business logic (no web framework imports)
  integrations/    → Thin external API wrappers (Claude, Gemini, ElevenLabs, YouTube)
  models/          → SQLModel tables + Pydantic schemas (no logic)
  pipeline/modifiers/title_cards.py → Title card prompt injection + post-processing
  config.py        → Shared constants (DATA_DIR, FPS, dimensions)
  dev/             → Dev dashboard (routes, log handler, HTML)
remotion/          → Remotion 4 rendering project (React + TS)
  src/scenes/      → Scene components per visual_mode (StaticImage, MultiFrame, Caption, TitleCard, ShortTitleCard, Subtitle, Video, + StaticCanvas/TreatmentRenderer/VerticalSceneLayout)
  src/effects/     → Composable FX (camera, typography, transitions, overlays, structural)
  src/types.ts     → Input props mirroring Python SceneFX models
data/              → Runtime data (SQLite DB, generated assets) — gitignored
docs/              → PRD, setup guide, superpowers skills
```

## Conventions

**Module boundaries**: `api/` = FastAPI routers only (validate, call pipeline, return; `Depends(get_session)` for DB). `pipeline/` = pure business logic, no FastAPI imports. `integrations/` = thin wrappers, raise `RuntimeError` on missing keys. `models/` = SQLModel tables + Pydantic schemas, no logic.

**Naming**: schemas `{Action}{Noun}Request`/`{Action}{Noun}Response`; handlers `handle{Action}` internally, `on{Action}` for props.

**Frontend styling**:
- Tailwind 4 utilities only — no CSS files. Dark theme `bg-neutral-950/900`, `text-neutral-100/400`. Accents `violet-*`, `sky-*`, `emerald-*`. Interactive elements always get `hover:` + `transition-colors`.
- Most Settings panels use framed section headers: parent titles/descriptions framed in the rounded purple title box (`-ml-4 rounded-2xl border border-violet-500/40 bg-violet-500/5 px-4 py-3`) with `text-xl font-semibold tracking-tight` headings; embedded subsections and control labels are smaller (`text-sm`) without the title box.
- Settings → Subtitles is intentionally a denser console layout: two-column section grid (explanation left, control right), compact segmented control for coverage, divided preview list for enabled styles. No title boxes around Subtitles labels; don't turn each choice into a card.

**Frontend state & formatting**: no external state library — `useState()` at page level, pass via props. Double quotes, trailing commas, 2-space indent.

**Editor navigation**: the project editor (`TimelinePage.tsx`) navigates via a vertical left rail (`ProjectNavRail`, same pattern as `SettingsPage.tsx`), grouped into `SCRIPT` / `LONG FORM` / `SHORT FORM` sections — not horizontal button rows and not a Long/Short toggle. Format is implied by the group, not a separate control. The rail drives the existing `viewerFormat`/`viewerAsset`/`activeTab` state (SCRIPT items leave `viewerFormat` untouched; LONG/SHORT items set it). New editor destinations are added as rail items in `NAV_GROUPS`, with active-state resolution centralized in `resolveActiveNavKey`. Project stats and utilities live in a horizontal `ProjectUtilityBar` under the pipeline rows (not in the rail, not a modal): plain stats via `UtilityStat`, and click-to-expand stats (Duration → per-segment durations, Cost → cost breakdown, Exports → exported files, Uploaded → distribution toggles) via `StatPopover`, plus the Canvas color picker and Open Exports button. There is no Project Details modal — those breakdowns are reached only through the bar's `StatPopover`s, each refreshing its data on open.

**Feature UX & dev observability**:
- For any new feature/behavior change/UI element, ensure the UI is the most intuitive representation (naming, placement, defaults, disabled states, workflow fit).
- Use in-app browser/preview tooling frequently while building UI (not just at the end); check real running page at desktop and mobile-ish widths; iterate on spacing, overflow, disabled/loading/error states, hierarchy.
- Any new scene visual functionality gets equivalent Test tab/Test Lab support in the same change.
- Add concise hints/tooltips next to non-obvious controls.
- Add dev-dashboard logs (success/warn/error/status/info) when new behavior affects generation, rendering, export, integrations, caching, or background jobs.

## Brand Profile

Single auto-created default brand (no picker). All endpoints auto-resolve `brand_id` — never put it in request bodies.

## Git Conventions

Commit messages: imperative present tense, `{Add|Fix|Update|Remove|Refactor} {what} {context}`, one feature/fix per commit, descriptive enough for another dev. Examples: "Fix download buttons navigating away from app instead of downloading", "Remove legacy FFmpeg video rendering pipeline".

## Environment Variables

Required: `ANTHROPIC_API_KEY`, `GOOGLE_AI_KEY`, `ELEVENLABS_API_KEY`. Optional: `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` (YouTube), `RUNWAYML_API_SECRET` or `FAL_API_KEY` (AI video). Stored in DB via AppSettings, loaded into env at startup. Never commit `.env`.

## Key Patterns

### Storage, export, infra
- **JSON blobs over migrations**: script content stored as JSON TEXT in SQLite.
- **Exports dir is the single final-media root**: user-facing exports live under Settings → General → Storage `Exports` (default `backend/config.DEFAULT_EXPORTS_DIR`, currently `~/Headless Hero Videos`). Project folders are `{Exports}/[project] {Project Title}` (title sanitized). No second export root.
- **Exported videos dedupe**: rendered MP4 exports go through `pipeline.export_paths.copy_to_project_downloads`, which hardlinks same-drive exports; fall back to a copy only when hardlinking is unavailable (cross-device). Keep internal render path and export path compatible.
- **Async rendering with polling**: long renders run in background threads; frontend polls `/api/render/status/{job_id}`.
- **IPC fallback**: frontend works with or without Electron (direct HTTP in dev).
- **Static serving**: FastAPI mounts `/static/projects` → `data/projects/`.
- **No auth**: single-user desktop app.
- **External links open in Chrome**: Electron main-process URL opening routes through the Chrome opener, ignoring OS default browser.

### Test Lab
- **Mirrors production**: uses hidden real `Script`/`ProjectConfig` records and the same production pipeline functions. Keep Test Lab records out of project lists/dashboards, persist only the last 20 run manifests under `data/test-lab/runs`, and never reintroduce stock-photo/gameplay/upload media paths.
- **Mode switch preserves scene text**: clicking a visual mode (`captions`, `multi_frame`, `continuous`, `popup_sequence`, `stat_card`) must not rewrite narration, visual prompt, caption text, or stat fields. Mode-specific demo text belongs in presets/explicit edits.
- **Subtitle/timer settings mirror production**: no per-run controls for subtitle style, highlighting, or segment timer; show read-only Settings → Subtitles values with a link to edit. Hidden scripts keep subtitle highlighting on; segment timer is always on.

### Title / SEO / project title
- **Segments stand alone as shorts**: each segment's narration ends cleanly on its own topic. Keep whole-video recaps, subscribe/"come back next week"/CTAs out of scene narration; `outro_cta` is metadata/editor copy.
- **Short-form SEO titles are deterministic**: `{project title} - {segment title}`. Use the script record topic title as project title, falling back to `ScriptContent.title`.
- **Project title canonical in `Script.topic_title`**: timeline title edits go through `/api/scripts/{script_id}/title`; generic full-script saves preserve `Script.topic_title` and must not let stale `ScriptContent.title` roll back a title edit.
- **Title edits retitle existing exports**: move export folders and title-based long-form filenames to the new sanitized title, refresh exported SEO markdown, rewrite short-form SEO titles. If the previous folder is missing, discover it by matching exported short-form asset filenames, then repair to canonical.
- **Short-form hook detection before render/export**: before short-form render/rendered-status/export/SEO, populate `ScriptContent.hook_scene_count` via `api.short_form_hooks.ensure_short_form_hook_scene_count`. If short #1 skips hook scenes, cache validity depends on the sidecar `data/projects/{script_id}/renders/shorts/0.json`; older unmarked short #1 renders are stale.

### Thumbnails
- **Title-card thumbnails have no subtitle/kicker**: keep `ScriptContent.card_subtitle` empty; thumbnail text is the main card title + segment label badges only. Enhancement prompts must not add copied/invented secondary phrases.
- **Long-form regeneration preserves versions**: `renders/thumbnails/0.png` is active/exported; regeneration archives the previous active as the next numbered sibling before replacing `0.png`. UI exposes saved variants.
- **Life-as-a long-form thumbnail labels are time periods**: two cached time-period labels, not `LEVEL`. Left ∈ `3 months in`…`8 months in`; right ∈ `8 years in`…`15 years in`. Persist exact labels in the sidecar; reroll only on forced/regenerate.
- **Life-as-a split thumbnails use close centered subjects**: each side's protagonist framed medium-close/waist-up, centered in its panel, large enough for mobile. Avoid distant full-room compositions.
- **Life-as-a split labels must pop**: saturated yellow/gold fill, thick black outline, strong shadow/highlight. No muted cream labels.
- **Life-as-a split thumbnail cache** tracks clean source image + exact labels + rendered prompt fingerprint; prompt wording changes regenerate.

### Subtitles
- **Short-form subtitles sit above app chrome**: vertical Remotion subtitles top-aligned in the bottom blurred band, box touching the bottom edge of the main image, clear of Shorts/Reels/TikTok overlays.
- **Subtitle text hides hyphens at render time**: narration/word-timing keep hyphens for ElevenLabs pacing, but every on-screen subtitle renderer formats display text with `formatSubtitleText` so ASCII/Unicode dashes never appear (standard subtitles, `aha_subtitle`, subtitle frame directives).
- **Standard subtitles route style per scene without extra LLM calls**: scene-level treatments `auto`/`clean`/`kinetic`/`burst`/`none`. Missing values default to deterministic renderer-side `auto` routing (no separate LLM call). Settings → Subtitles owns global coverage (`SUBTITLE_COVERAGE_MODE=all|punchy`) and style gates (`SUBTITLE_STYLE_{CLEAN|KINETIC|BURST}_ENABLED`); render cache fingerprints must include them. `visual_mode="captions"`, title cards, and legacy subtitle scenes suppress standard subtitles for their own text.

### Voiceover (ElevenLabs)
- **Duration is the timing source of truth**: Remotion scene duration derives from generated audio duration, not estimates.
- **Expressiveness uses settings, not narration rewrites**: no non-title dramatizer or LLM punctuation pass. Send narration as-written, except `eleven_v3` may add deterministic hidden TTS-only tags. Title-card TTS framing (`Level N — …`) is the only automatic text addition outside v3 tags. Settings → Voices owns default model, stability, style, speed.
- **v3 hidden tags stay conservative**: only `[curious]`, `[serious]`, `[thoughtful]`, `[confident]`, `[reflective]`. Never auto-add nonverbal/effect tags (`[sighs]`, `[laughs]`, `[whispers]`, etc.).
- **Headless Hero Narrator is the preferred default**: Settings → Voices sorts/auto-selects it first; `Liam - Viral Short-Form Storyteller` is the shorts fallback, `Adam Greene` the friendlier backup. No legacy Lucan-first selection.
- **Persist only visible controls**: default voice selector shows only those three saved voices. Model = two buttons (v2/v3). V2 shows presets (`Steady`/`More Human`/`Dramatic`/`Custom`), sliders only for `Custom`. V3 shows only stability; backend/API must not pass v2-only speed/style when `eleven_v3`.
- **Post-voiceover checks don't rewrite scripts**: timing diagnostics may log overlong scenes but must not call an LLM to tighten/mutate `Scene.narration` or revoice. Fix pacing in prompts/post-processing before voiceover or via explicit editor actions.
- **Scene-length protection before voiceover**: split overlong scenes deterministically on existing sentence boundaries before any voice/image/render assets; preserve narration text exactly. No post-audio LLM rewrite. When an overlong beat is a single sentence with no `.!?` boundary (e.g. a comma/em-dash run-on list), `life_as_a._split_life_as_a_scenes` falls back to clause delimiters (`— – ; : ,`, kept attached to each clause so joined chunks reproduce the text exactly); a sentence with no clause delimiters either stays whole. Decision history + rejected alternatives + open gaps: `docs/ai-video-scene-duration.md`.
- **Media analysis requires voiceover durations**: don't run media-source analysis until every scene has `audio_duration_seconds > 0` (AI-video eligibility needs real audio length). UI and API both block analysis before voiceover.

### LLM tasks / models
- **OpenAI reasoning by task**: structured JSON/classification (`fx`, `seo`, `short_form_seo`, `media`, `eli`, `analysis`, `hook_detect`, `script_rating`) default `openai_reasoning_effort="minimal"`; narrative/planning (`script`, `idea`, `hook`) default `low`. User-configurable via `OPENAI_REASONING_EFFORT_<TASK>`.
- **Full-script rating persisted on ScriptContent**: after generation, `pipeline.script_rating.rate_script` runs a fresh `script_rating` call (OpenAI `gpt-5-mini` default), validates the 14-criterion rubric, recomputes averages locally, stores in `ScriptContent.script_rating`. Dashboard exposes `script_rating_overall`; timeline shows category breakdown. Do not reintroduce the removed `pipeline/script_reviewer.py` or `SCRIPT_REVIEW_RUBRIC`.
- **Anthropic uses direct API model IDs**: `claude-opus-4-7`, `claude-sonnet-4-6`, `claude-haiku-4-5-20251001` — not Bedrock ids. Script task defaults to Claude, configurable from Settings → API Keys / AI Models.

### Visual modes (canonical routing)
- **`visual_mode` is canonical**: one persisted/rendered/API field with values `video`, `full_frame`, `multi_frame`, `continuous`, `popup_sequence`, `comparison_board`, `stat_card`, `captions`. Script generation may emit all but `video` (a post-voiceover media-analyzer promotion). Never write `media_source` or `visual_treatment` into scene JSON/API/frontend/Remotion props. Legacy `media_source="ai_video"` and `visual_treatment` are accepted only as one-way load/request normalization, then converted. Legacy `quick_cuts`/`montage` alias to `multi_frame`; `continuous` is canonical for same-scene progression. Legacy `flipflop`/`blink` modes normalize to `full_frame` (blink is now a renderer-owned overlay, not a mode — see Blink section).
- **New modes start from the guardrail doc**: before adding/renaming/changing any mode, read `docs/visual-mode-design-guardrails.md` and ensure a distinct purpose, routing, deterministic JSON shape, Remotion behavior, Test Lab coverage, cache invalidation, fallback, export, dev observability, tests, and no conflict with existing modes.
- **`VideoFormat` is the source of truth for script-type reference data**: the dataclass in `backend/pipeline/formats/` owns `supported_visual_modes` and `reference_notes` (curated `FormatNote` gotchas), surfaced via `/api/formats` and the read-only Settings → Reference → "Script Types" page (`frontend/src/components/settings/script-types/`). New script type = register a `VideoFormat` with these filled. Reference-only (not enforced) — keep consistent with actual routing and reflect per-format disablement (e.g. life-as-a omitting `captions`/`stat_card`).
- **Scene visual modes are AI-only**: no gameplay clips, stock photos, or user uploads. Deprecated gameplay/stock/upload fields are ignored or coerced back to AI generation.
- **Visual storytelling arc**: script generation prompts produce a coherent visual narrative arc across scenes, not just talking-head descriptions.

### Media-backed modes (images / frames / video)
- **Only media-backed modes generate scene images/frames**: `full_frame` → one scene image; `multi_frame`/`continuous` → frame sequences. Layered modes have their own asset pipeline — Test Lab, batch gen, manual regen, and export image phases must skip/clear `Scene.image_url`/`frame_urls` for `video`, `popup_sequence`, `comparison_board`, then generate only mode-specific assets.
- **Continuous frame references use generated frames only**: frame 1 may use the style preset image; later `reference_previous` frames use only the prior generated frame (no preset image, to avoid leaking preset subjects). Continuation prompts include the shared scene brief + explicit middle/final progression instructions.
- **Normal generated images are full-bleed**: any path generating a scene image/frame includes the shared full-bleed/no-border rules from `pipeline.image_gen` — no framed panels, mats, poster edges, cards, borders, margins. Cutout/contact-sheet paths may use isolated crop layout but still forbid frames, borders, labels, text.
- **Captions = renderer-owned editorial text**: `captions` is a static-canvas punch mode with optional side imagery + large `caption_text` and red `caption_emphasis`. Not standard subtitles; suppresses bottom subtitles during the beat. Fields emitted in the existing script call (no extra LLM call, no readable caption text inside generated images). Legacy `aha_subtitle` normalizes into `captions`.
- **Stat card = renderer-owned single statistic**: `stat_card` shows one giant `stat_value` + optional `stat_label`, all text rendered by Remotion. Only generated asset = optional transparent supporting icon cutout via one `visual_layers` entry — no scene image, no frames, no video promotion. Subtitles and Eli suppressed. MAX 1–2 per video, never back-to-back; use only when narration revolves around one decisive figure (percentage, money, population, duration, distance, ranking, odds, risk, measurement).

### AI video
- **Routed, then generated from anchor images**: when `AI_VIDEO_ENABLED=true`, analysis assigns up to max(requested count, segment count × `AI_VIDEO_SCENES_PER_SEGMENT`) as `visual_mode="video"` (default 2/segment). Generation first makes the normal styled scene image, then sends it to `AI_VIDEO_PROVIDER` (`runway` Gen-4 Turbo default, or `fal` Wan 2.2 i2v — non-turbo `fal-ai/wan/v2.2-a14b/image-to-video` via `FAL_VIDEO_MODEL`, sized per-scene with `num_frames`) so motion preserves the visual format. Follow-up to move selection into script generation: `docs/ai-video-followups.md`. **Why clip length / image-fallback / scene-splitting are the way they are (full decision history + rejected alternatives + open gaps): `docs/ai-video-scene-duration.md` — read it before touching fal duration, the renderer fallback, the routing ceiling, or the life-as-a splitter.**
- **Segment-distributed and spaced**: strongly target up to `AI_VIDEO_SCENES_PER_SEGMENT` eligible non-title-card video scenes per segment, skipping only segments with no candidates. Post-processing preserves valid LLM choices, fills missing slots deterministically, and never leaves two back-to-back `video` scenes.
- **Slowdown only as a small safety net**: if a clip is shorter than narration, Remotion may slow it only when the needed increase is ≤25%; larger gaps fall back to the anchor image/full audio duration and log a warning.
- **Video scenes end at clip duration**: cap video-backed scenes to actual local clip duration when shorter than narration. No silent looping or held final frame while camera FX continue.
- **AI-video scenes aren't photo scenes in UI**: any UI showing frame/photo counts suppresses them for `ai_video` scenes and marks those rows as video.
- **On-screen characters stay silent**: the animation prompt (`pipeline.video_gen._build_animation_prompt`) instructs that any depicted character is a silent subject, not the narrator — mouths closed and still, with no talking/speaking/lip-sync/mouth movement in both the positive directive and `_NEGATIVE_MOTION_GUIDANCE`. The narration is the only voice; visible lip movement reads as a second speaker.

### Layered modes (canvas, popup, comparison)
- **Render over a global static canvas**: every scene has video-level `visual_canvas.background_color`. `full_frame`/`multi_frame`/`continuous`/`video` cover it via media; `popup_sequence`/`comparison_board` stage assets over it. Canvas-revealing modes may use shared `renderer_context` (`plain`, `desk`, `classroom`, `office`, `kitchen`, `shop`, `lab`, `street`) for simple deterministic context behind cutouts (no full environment image). Remotion chooses renderers from `visual_mode` (no `visual_treatment` prop). Script generation may choose layered modes from intent; post-voiceover analysis fills timing/layer assets and may infer missing layered opportunities only when timing exists (`audio_duration_seconds > 0` + non-empty `word_timestamps` for non-title scenes).
- **Popup cutout experiments separate anchors from item sheets**: generate the anchored character/focus separately from the popup item sheet (character keeps protagonist/reference style; items share a simpler icon style). Item sheets arrange items left-to-right in UI order over a flat chroma background absent from the subjects, then key it out and auto-trim each crop with padding.
- **Popup sequence uses cropped cutouts, not generated panels**: generate one isolated anchor + one contact-sheet of items, crop into transparent cutouts, persist cutout layers. Never call Gemini per item for framed panels.
- **Popup sequence has no scene image layer**: visible render = canvas color + one clean standing anchor cutout + cropped item cutouts.
- **Test Lab popup fallback uses three panels**: when explicitly `popup_sequence` with no analyzer `visual_layers`, derive three fallback panel assets from the scene `visual_prompt`/narration, spaced left/center/right. Production analyzer output wins when present.
- **Popup items orbit clockwise**: anchor cutout stays centered; item cutouts pop in at `enter_at_seconds` then join a shared clockwise orbit.
- **Popup cutout wrappers stay invisible**: no wrapper backgrounds, clipping, borders, or box shadows around `asset_kind="cutout"` layers; any shadow comes from the artwork.
- **Comparison board = renderer-owned contrast layout**: use when narration contrasts 2–3 subjects/concepts/states/choices/outcomes (Before vs After, Myth vs Reality, etc.). Generate transparent cutouts for the compared subjects only; Remotion owns columns, dividers, VS markers, arrows, badges, stat chips, and all labels. Avoid for a single environment/event, ordinary lists, same-subject micro-animation, or process progression.

### Blink (full-frame overlay only)
- **One mechanism — a renderer-drawn closed-eye overlay on the normal full-frame image.** Blink is NOT a selectable `visual_mode` and NOT a generated cutout/state pipeline (both deleted). After a `full_frame` image is generated, `pipeline.full_frame_blink.build_full_frame_blink_metadata` runs the shared detector and, when the anchor passes strict safety validation, stores `visual_source_metadata.full_frame_blink = {enabled, action:"blink", anchor}`. It is **auto-enabled** — no 50% deterministic gate and no manual review (`project_blink_review` is removed).
- **Aggressive suppression, quality over coverage.** Many scenes won't blink. `full_frame_blink_quality_rejection_reason` rejects on eye asymmetry, vertical misalignment, out-of-range absolute eye size, bad separation, or an overlay that would span the nose; the renderer (`blinkBlinkEyeOverlayGeometry` / `resolveBlinkOverlayAnchor`) drives every extent from the detected eye box, hard-caps lid/mask width so marks can't cross the nose or read as a bar, and suppresses entirely when eye sizes are missing/unsafe. Never ship an ugly blink.
- **Render via `StaticImageScene`** over the base image. Timing is seeded by `scene.id` (irregular, short pulses). Legacy `visual_mode="blink"` JSON coerces to `full_frame` (`models.script.normalize_visual_mode`); stale `state_a`/`state_b` cutout layers are dropped by `_coerce_legacy_blink_scene`. Bump `BLINK_RENDERER_VERSION` (in `subtitle_render_fingerprint`) to invalidate prior blink renders.
- **Test Lab is a thin harness over production**: selecting blink runs a normal `full_frame` image + the same `build_full_frame_blink_metadata` path; `BlinkAuditLab` visualizes detection over a real script's full_frame scenes. No cutout/state generation, no Blink Review tab.

### Characters / asset vault
- **Reusable crop cutouts go to the asset vault**: any image cropped into a reusable transparent cutout (incl. Popup Crop Lab anchors/items) saves the cleaned PNG under `data/projects/asset-vault/{characters,items}`. v1 metadata is filename-only: `{character|item}_{slug}_{YYYYMMDD_HHMMSS}_{shortid}.png` — no JSON sidecars until reuse/search needs outgrow filenames.
- **Character references keep originals and cutouts**: persist both the original reference (canonical for reference chaining + human review) and a transparent cropped cutout (compositing asset). Shared single-character background removal lives in `pipeline.character_assets` — no workflow-specific removebg.
- **Style preset characters are scoped to their preset**: Settings → Style Presets is the source of truth for presets and their characters. Characters are generated from the selected preset, listed only under it, and selectable only for projects using that preset. No separate global main-character tab/source.
- **Eli-disabled image gen requires a preset-scoped character reference first**: with Eli off, don't generate scene/title/chapter images, `generate_scene_image` thumbnails, or AI-video anchors until an active style preset exists with an active character that has a reference image. Project generation syncs that reference to `data/projects/{script_id}/character/reference.png`. Never silently fall back to anonymous characters, Eli, or another preset's character.
- **Eli-disabled main characters inherit the preset style**: identity may differ by preset, but the reference image must match the selected style preset image. Never prompt these as photorealistic/cinematic/3D/painterly unless the preset itself establishes that non-house style.
- **Style preset rows must be image-backed**: valid only when both the `style_presets` row and `data/style/presets/{id}.png` exist. Read-only preset API hides stale fileless rows without deleting DB data; preset-generating tests use an isolated test engine, never writing fake rows into dev `data/db.sqlite`.

### Life-as-a format
- **Long-form-only opening selection**: uses the same pre-script cold-open workflow as listicles but with a life-as-a opening prompt/rubric (second-person immersion, role fantasy, stakes/discomfort, progression curiosity, title alignment). Openings are long-form-only — skipped from short #1 via the shared `hook_scene_count` prefix trimming. Don't route them through listicle hook scoring/refinement.
- **Scenes are short render beats**: non-title scenes target 5–9s and one beat; post-processor splits overlong scenes before voiceover (on sentence boundaries, falling back to clause delimiters for single-sentence run-ons — see Scene-length protection). The short-scene seconds setting gates AI-video routing duration only; generated-image scenes may keep multiple frames for progression/contrast.
- **Protagonist visuals follow the active character mode**: any visible main-subject/role scene depicts the active recurring character as the visually dominant protagonist in that role — Eli when enabled, else the active preset character (synced into `ScriptContent.main_character`). Secondary people must be visually distinct; object/atmosphere shots may omit the protagonist. AI-video animation is eligible only for active-protagonist scenes.
- **Shorts show visible part labels, not SEO suffixes**: short renders/thumbnails display `Part {current}/{total}` on the title card and above the thumbnail; upload/SEO titles stay deterministic `{project title} - {segment title}` with no `(Part …)` suffix. Cached short renders/thumbnails are stale when the stored part indicator mismatches the current segment count/index.
- **Title-card narration stores descriptors only**: chapter-card narration omits `Level N`, holding only the descriptor (e.g. `The occasional.`). The TTS layer is the single place that adds `Level N`, with a defensive guard for older scripts that already include a level prefix.

## Video Rendering (Remotion)

Remotion 4 (React frame-by-frame) instead of FFmpeg filter graphs. Python writes scene data + FX config to JSON → invokes `npx remotion render` via subprocess → picks up the MP4. Renders the entire video as a single `FullVideo` composition (native transitions + global timeline). Output is 1920×1080 YouTube 16:9.

Export bundles must not generate or include standalone long-form audio MP3s; scene audio is internal pipeline media for timing/rendering only.

**FX**: AI-generated via Claude (not manually edited). Each scene has an optional `fx: SceneFX`. Active effect: `zoom_punch`. Timing adjustable via scene micro-timeline.

**Transitions**: each scene has `transition_in` (cut, fade_black, flash_white, wipe), assigned by Claude alongside FX. `SceneTransition` wraps visual+subtitle+Eli layers; audio plays through.

## Eli Character Overlay

Optional recurring animated host overlaid like a Twitch webcam box. Pre-generated frame library (~150 poses × 2 mouth states) via Gemini with reference-image chaining + rembg removal. Spec in `backend/prompts/character.py`. When Eli is disabled, the active style preset's scoped character takes the protagonist role (see Characters section).

Claude generates per-scene animation documents (keyframe timelines selecting pose/expression per frame range). Mouth state derives from `phrase_timestamps`, not animation documents. Eli Remotion render component is **not yet implemented**.

## Scene Micro-Timeline

Per-scene micro-timeline in the preview panel for frame-precise timing. `forwardRef` imperative API for keyboard shortcuts. Conditional lanes: InOutLane (always), ImageLane (multi-frame), FxLane (zoom_punch), EliLane (eli keyframes). Timing fields (`frame_timings`, `visual_in_seconds`, `visual_out_seconds`) stored in the script_json blob.
