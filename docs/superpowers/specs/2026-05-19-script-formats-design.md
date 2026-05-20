# Script Formats — Design

**Date:** 2026-05-19
**Status:** Spec — pending implementation plan

## Problem

Headless Hero today produces exactly one shape of video: an 8-segment, staccato-educational listicle ("8 X That Y"). The pipeline has this shape baked in at every layer — `SEGMENT_COUNT = 8` is hardcoded, the script system prompt prescribes a punchy mosaic style, ideation generates listicle-shaped titles, the title-card system composites a fixed N-circle grid, and hook-scoring rates the opening for staccato-style retention.

We want to add a second video format: **"Your Life As A..."** — a literary, second-person, level-by-level walk through a life path (sample reference: a 13-minute "Your Life At Every Level Of A Casino Addiction" video). The user wants this selectable at video creation time, and the system should be designed so additional formats can be added in the future with minimal rework.

## Goals

- Introduce a `format_id` concept that flows from ideation through script generation through rendering
- Implement two formats: `youtube-listicle` (current behavior) and `life-as-a` (new)
- Make adding a third format mostly additive — a new module + a registry entry, not edits scattered across the codebase
- Preserve all existing functionality with no behavior change for existing scripts
- Produce a Format Authoring Guide so future format additions don't require re-reading the codebase

## Non-goals

- No conversion path between formats. Format is chosen at ideation and locked through generation.
- No format-aware FX, Eli, or rendering changes. Those layers stay uniform across formats.
- No removal of `SEGMENT_COUNT` from `config.py` (it remains the default for `youtube-listicle`); review of stale imports is a follow-up cleanup.

## Architecture

### Format registry

```
backend/pipeline/formats/
  __init__.py                # registry: get_format(id), list_formats(), resolve_format(record)
  base.py                    # VideoFormat dataclass + TitleCardStrategy protocol + VisualBeatRules
  youtube_listicle.py        # wraps existing 8-segment educational behavior
  life_as_a.py               # new format
  title_cards/
    composite_grid.py        # current N-circle composite (used by youtube-listicle)
    cinematic_chapters.py    # new (used by life-as-a)
```

**`VideoFormat`** is a frozen dataclass that declares everything orchestration needs:

```python
@dataclass(frozen=True)
class VideoFormat:
    id: str                              # "youtube-listicle" | "life-as-a"
    display_name: str                    # for UI selector
    short_description: str               # for UI selector

    level_count: int | tuple[int, int]   # 8 (fixed) | (4, 7) (range)
    level_label: str                     # "segment" | "level"

    ideation_prompt: PromptDef
    script_system_prompt: PromptDef
    outline_prompt: PromptDef | None         # segmented gen, optional
    segment_scenes_prompt: PromptDef | None  # segmented gen, optional

    supports_cold_open: bool
    supports_hook_scoring: bool
    supports_segmented_generation: bool

    title_card_strategy: TitleCardStrategy
    visual_beat_rules: VisualBeatRules

    enforce_post_processing: Callable[[ScriptContent], ScriptContent]
```

**`TitleCardStrategy`** is a protocol with two implementations (composite-grid, cinematic-chapters), described in the title-cards section below.

**`VisualBeatRules`** captures the per-format distribution rules currently hardcoded in `_fix_visual_monotony`:

```python
@dataclass(frozen=True)
class VisualBeatRules:
    allowed_beats: set[str]              # e.g. {"static", "continuous"} for life-as-a
    target_distribution: dict[str, tuple[float, float]]  # beat -> (min%, max%)
    max_consecutive_same_beat: int       # 3 for listicle, higher for life-as-a
```

**Registry usage:**

```python
from pipeline.formats import get_format, list_formats, resolve_format

format = get_format("life-as-a")              # raises KeyError if unknown
all_formats = list_formats()                  # for the frontend selector
format = resolve_format(script_record)        # safe: defaults to youtube-listicle if missing
```

`resolve_format` is the read-side helper — falls back to `youtube-listicle` if `format_id` is missing or unknown, logs a warning, never crashes.

### Database

- `Script` model gains `format_id: str` with a column-level default of `"youtube-listicle"`. SQLite handles backfill of existing rows on column add.
- `ScriptContent` (the JSON blob) gains two optional fields, populated only by `life-as-a`:
  - `cinematic_thumbnail_prompt: str | None`
  - `levels: list[LevelMeta] | None` — parallel to `segments`, carries chapter-card metadata (`number`, `descriptor`, `image_prompt`)
- Existing `Segment` model is reused for the actual level content; `LevelMeta` is purely for the chapter card.

No migration required beyond the column add. Old script JSON deserializes cleanly with the new optional fields defaulting to `None`.

### API

- `GET /api/formats` — returns the list of formats: `id`, `display_name`, `short_description`, `level_count`, `supports_cold_open`, `supports_hook_scoring`, `supports_segmented_generation`, `title_card_strategy.kind`. Drives the frontend selector.
- `GenerateIdeasRequest` adds `format_id: str` (required).
- `GenerateScriptRequest` adds `format_id: str` (required).
- `VideoIdea` response carries `format_id` so it threads through to script generation.

### Pipeline orchestration

`generate_script()` becomes a thin dispatcher:

1. Look up the format via `get_format(format_id)`
2. Build prompts from `format.script_system_prompt`, `format.outline_prompt`, etc.
3. Run the LLM call with format-supplied templates
4. Apply `format.enforce_post_processing(content)`
5. Run `_fix_visual_monotony(content, rules=format.visual_beat_rules)`
6. Conditionally run cold-open variant generation (`if format.supports_cold_open`)
7. Conditionally run hook scoring (`if format.supports_hook_scoring`)
8. Conditionally use segmented generation (`if format.supports_segmented_generation`)

Same pattern at the title-card pipeline:

- `prepare_title_card_scene(scene, ...)` → delegates to `format.title_card_strategy.prepare_title_card_scene(...)`
- Thumbnail generation → delegates to `format.title_card_strategy.prepare_thumbnail(...)`

## The "Your Life As A..." format spec

This becomes the body of `LIFE_AS_A_SCRIPT_SYSTEM` in `prompts.py`.

### Voice & POV

- **Second person, present tense.** "You walk into a casino. You are 26."
- **Observational, literary, contemplative.** The narrator is a step ahead — naming patterns the protagonist is still living through.
- **No greeting, no listicle hook, no rule-of-three escalation, no mic drops.** The staccato-educational scaffolding is explicitly disabled.

### Structural arc

A "Your Life As A..." video is a single continuous progression broken into 4–7 levels. Claude picks the right number per topic. Suggested beats (descriptive guidance, not prescriptive — Claude varies per topic):

1. **Entry** — first encounter, naive, no understanding of the system
2. **Familiarization** — early competence, identity formation
3. **Drift** — gradual recalibration the protagonist doesn't notice
4. **Architecture** — the thing has reorganized their life around itself
5. **Floor / Reckoning** — collapse, consequence, a moment of clarity
6. **(Optional) Aftermath** — what's left, what was learned

Level titles follow `Level {N}, the {descriptor}` — e.g. *"Level one, the occasional"*, *"Level four, the architecture"*. Stripped, declarative, no colon.

### Scene granularity

Critically different from the listicle format:

| | listicle | life-as-a |
|---|---|---|
| Narration per scene | 1–2 sentences | 3–8 sentences, paragraph-shaped |
| Duration per scene | ~5–10s | ~10–25s |
| Visual beats | varied (static/quick_cuts/montage/aha) | mostly `static`, occasional `continuous` |
| Transitions | varied with intentional energy | mostly `cut`, occasional `crossfade` for time-passage |

### Required craft elements

The system prompt enforces these:

- **Time progression markers.** Explicit time anchors throughout ("you are 26", "by year three", "the morning you leave"). The viewer must always know roughly where they are in the journey.
- **Recurring named characters.** At least one secondary character appears across multiple levels with specific concrete moments. No faceless plurals like "your friends".
- **Concrete sensory anchors.** Every level needs at least one viscerally specific detail (the cocktail waitress, the fold-out couch, a specific dollar amount). No abstractions floating untethered.
- **Internal callbacks.** Plant a phrase, object, or moment in early levels and bring it back later with shifted meaning.
- **The level shift is gradual, not announced.** Levels overlap at the edges — the protagonist is already deep into level N before they realize level N-1 ended.
- **Closing register is topic-determined.** Cautionary topics (addiction, burnout, breakdown) close on the cost — a specific image of what was paid. Textured-but-not-tragic topics (a software engineer's career, a parent of twins) close on something honestly reflective without forcing tragedy. The closing image must be specific and earned either way; only the register changes. Claude classifies the topic upfront and chooses accordingly.

### Visual beat rules

Format-supplied via `VisualBeatRules`:

- **`static`: 80–90%** of non-chapter-card scenes
- **`continuous`: ~10–15%** for time-passage moments
- **`quick_cuts`: 0–5%** — only for compressed time ("you go four times in the second year, then six")
- **`aha_subtitle`: disabled** — breaks the literary register
- **`montage`: disabled** — real-photo intercutting breaks immersion

Shot-type palette (`[ESTABLISHING] [CLOSE-UP] [REACTION] [METAPHOR]`) still applies; `[DIAGRAM]` and `[SCALE]` de-prioritized since the format isn't explanatory.

### Ideation pattern

`LIFE_AS_A_IDEATION_SYSTEM` produces titles in the shape:

- `Your Life As A {role/identity}` — software engineer, casino addict, ER nurse, hedge fund trader
- `Your Life At Every Level Of {experience}` — a casino addiction, parenting twins, a Mormon missionary trip

Each idea includes a description of what the journey looks like and what the closing image will be. The closing image is load-bearing for the format and ideation should already know it.

## Title cards & thumbnail strategy

Two strategies behind `TitleCardStrategy`:

```python
class TitleCardStrategy(Protocol):
    kind: str  # "composite-grid" | "cinematic-chapters"

    def prepare_thumbnail(script_id, content) -> Path:
        """Generate the YouTube thumbnail. Called once per script."""

    def prepare_title_card_scene(scene, script_id, content) -> Scene:
        """Resolve image_url for a title-card scene at render time."""

    def get_chapter_card_scenes(content) -> list[Scene]:
        """Return the title/chapter scenes that should be inserted between segments."""
```

### Strategy A: `composite-grid` (existing)

Wraps current behavior. No behavior change.

- **Thumbnail**: composite N-circle grid with title overlay → `composite_title_card.png` and `composite_title_card_notitle.png`
- **Title-card scenes**: one at the start of each segment, all using the no-title composite as their image
- **Frontend preview**: side-by-side view of both composite variants (existing UI)

### Strategy B: `cinematic-chapters` (new)

- **Thumbnail**: a single AI-generated image (1280×720) for the topic, with title-overlay treatment ("YOUR LIFE AS A CASINO ADDICT") composited on top. Image prompt comes from `ScriptContent.cinematic_thumbnail_prompt`, populated by Claude during script generation.
- **Per-level chapter cards**: one full-frame chapter scene at the start of each level. Each carries:
  - An AI-generated image driven by `LevelMeta.image_prompt` for that level
  - A two-line text overlay: `LEVEL {N}` (small, top) + `THE {DESCRIPTOR}` (large, centered)
  - Short narration line ("Level one, the occasional") in the audio
- **Frontend preview**: a horizontal storyboard strip — thumbnail + each chapter card

### Storage paths

- `composite-grid` keeps current paths
- `cinematic-chapters` writes:
  - `data/projects/{id}/images/cinematic_thumbnail.png` (with title overlay)
  - `data/projects/{id}/images/cinematic_thumbnail_clean.png` (no overlay)
  - `data/projects/{id}/images/chapter_{N}.png` (one per level)

### Remotion

The Remotion side gains awareness via the existing `Scene.is_title_card` flag. The existing TitleCard scene component already accepts an arbitrary background image and a text overlay — no new components needed.

## Frontend changes

### Format selector on `IdeationPage`

A horizontal format-card row above the niche input. Cards are visual (not a dropdown) because the formats are stylistically very different and the choice is consequential.

```
┌──────────────────────────────────────────┬──────────────────────────────────────────┐
│ Educational Listicle              [✓]    │ Your Life As A...                        │
│ "8 things you didn't know about X"       │ "A walk through the stages of being X"   │
│ 8 segments · staccato · viral-tuned      │ 4–7 levels · literary · second-person    │
└──────────────────────────────────────────┴──────────────────────────────────────────┘
```

Selection persists to `localStorage` (`hh-selected-format`); default on first load is `youtube-listicle`. The selected format is sent in `POST /api/ideas/generate` so ideas come back in the right pattern. Each `VideoIdea` response carries `format_id`, threaded through `onUseIdea` into `ScriptGenerationPage`.

### `ScriptGenerationPage` conditional UI

Driven by the format's `supports_*` flags from `/api/formats`:

- **Cold-open variant picker**: hidden when `supports_cold_open === false`
- **Hook score badge**: hidden when `supports_hook_scoring === false`
- **Title-card section**: renders different UI per `title_card_strategy.kind`:
  - `composite-grid` → existing two-image preview
  - `cinematic-chapters` → horizontal storyboard strip (thumbnail + chapter cards)
- **Segment progress list during generation**: labels swap between "Segment N" and "Level N" based on `format.level_label`
- A small badge shows which format the script is being generated as (no second selector — locked once chosen at ideation)

### What does not change

- Timeline editor, scene editing, properties panel, micro-timeline, FX assignment, Eli, render/export — all format-agnostic. They operate on `ScriptContent` which is format-neutral.

## Backwards compatibility

- New `format_id` column defaults to `youtube-listicle` for all existing rows
- New `ScriptContent` fields (`cinematic_thumbnail_prompt`, `levels`) default to `None` and are ignored by `youtube-listicle`
- `resolve_format()` falls back to `youtube-listicle` if `format_id` is missing or unknown — never crashes on corrupt/old data
- All existing scripts continue to render exactly as they do today, with no observable difference

## Deliverables

1. **`backend/pipeline/formats/`** — registry, base, two formats, two title-card strategies
2. **`prompts.py` additions** — `LIFE_AS_A_SCRIPT_SYSTEM`, `LIFE_AS_A_IDEATION_SYSTEM`, plus segmented-gen variants if applicable for the new format
3. **`Script.format_id` column** + `resolve_format` defensive read helper
4. **`ScriptContent` schema additions** (`cinematic_thumbnail_prompt`, `levels: list[LevelMeta] | None`)
5. **`GET /api/formats`** endpoint
6. **`format_id` in `GenerateIdeasRequest` and `GenerateScriptRequest`**
7. **Frontend format selector** on `IdeationPage` + `localStorage` persistence
8. **Conditional UI** on `ScriptGenerationPage` (cold-open / hook-score gating, level-vs-segment label, chapter-card storyboard preview)
9. **Cinematic-chapters thumbnail + chapter-card image generation** in the title-card pipeline
10. **`docs/formats/AUTHORING.md`** — Format Authoring Guide. Exhaustive checklist for adding a new format: every prompt to write, every strategy method to implement, every flag to set, every UI affordance to wire up, every test to add. Includes a worked example walking through how `life-as-a` was implemented as a reference.
11. **Tests**: format registry resolution, format-specific post-processing, defensive fallback for unknown `format_id`, smoke test that renders a tiny `life-as-a` script end-to-end with a fixture.

## Out of scope

- Format conversion (no "regenerate this script as a different format" feature)
- Format-specific FX rules
- Format-specific Eli animation rules
- Removing `SEGMENT_COUNT` from `config.py` (stays as the listicle default; stale-import audit is a follow-up)

## Open questions for the implementation plan

- Does `life-as-a` use segmented generation, single-pass, or both? The casino sample is ~13 minutes — likely too long for single-pass with most models. Default likely `supports_segmented_generation = True` with an outline phase that produces level titles + image prompts.
- Where exactly does the chapter-card text overlay get rendered — Remotion or a pre-rendered PNG composite? Existing TitleCard component handles arbitrary text overlays; Remotion is preferred to keep the chapter card editable post-generation.
- Should the format selector show a brief sample/preview (a paragraph of representative narration) when hovered? Helps users understand the difference. Defer to UX iteration after MVP.
