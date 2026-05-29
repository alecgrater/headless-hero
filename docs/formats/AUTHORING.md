# Format Authoring Guide

A practical reference for adding a new video format to Headless Hero. Read end-to-end before touching code; sections are ordered to match the rough chronology of an implementation.

Cross-references:
- Design rationale: [`docs/superpowers/specs/2026-05-19-script-formats-design.md`](../superpowers/specs/2026-05-19-script-formats-design.md)
- Implementation plan (file map): [`docs/superpowers/plans/2026-05-19-script-formats.md`](../superpowers/plans/2026-05-19-script-formats.md)

## 1. What is a format?

A "format" is a declarative `VideoFormat` object that fully describes how Headless Hero generates one shape of video — the prompt set, the level/segment structure, what supplementary phases (cold open, hook scoring) apply, the title-card / thumbnail strategy, the visual-beat distribution rules, and a post-processing function. The orchestration code (`scriptwriter.py`, `ideation.py`, `remotion_render.py`, the API) is format-agnostic and dispatches through the registry. Adding a new format means creating a new `VideoFormat` instance and the prompt + strategy assets it points to — not editing pipelines.

The two reference formats are:
- **`youtube-listicle`** — fixed 8 segments, composite-grid thumbnail, viral-tuned, supports cold opens + hook scoring. ([`backend/pipeline/formats/youtube_listicle.py`](../../backend/pipeline/formats/youtube_listicle.py))
- **`life-as-a`** — 4–7 levels, cinematic chapter cards, literary second-person, no cold open / hook scoring. ([`backend/pipeline/formats/life_as_a.py`](../../backend/pipeline/formats/life_as_a.py))

## 2. Adding a format: checklist

Suppose you are adding a format named `origin-story`. Touch these files in roughly this order:

| Step | File | What you do |
|---|---|---|
| 1 | `backend/prompts.py` | Add `ORIGIN_STORY_IDEATION_SYSTEM`, `ORIGIN_STORY_SCRIPT_SYSTEM`, and (if segmented) `ORIGIN_STORY_OUTLINE_INSTRUCTIONS` + `ORIGIN_STORY_LEVEL_SCENES_INSTRUCTIONS` `PromptDef`s. Wrap each in `register(...)`. |
| 2 | `backend/pipeline/formats/origin_story.py` | Define `VisualBeatRules`, post-processor function, and `VideoFormat` instance. End the file with `_register(...)` so the import side-effect registers it. |
| 3 | `backend/pipeline/formats/__init__.py` | Add `from . import origin_story  # noqa: F401` to `_bootstrap()`. |
| 4 (optional) | `backend/pipeline/formats/title_cards/<your_strategy>.py` | Only if neither `composite-grid` nor `cinematic-chapters` fits. Implement the `TitleCardStrategy` protocol. |
| 5 | `backend/tests/pipeline/test_formats_registry.py` | Add a one-test stanza asserting your format's flags + strategy kind (mirror `test_life_as_a_flags`). |
| 6 | `backend/tests/pipeline/test_origin_story_post_processing.py` | Add post-processor tests (mirror `test_life_as_a_post_processing.py`). |
| 7 (frontend, only if a new strategy kind is added) | `frontend/src/types/format.ts` | Widen `title_card_strategy_kind` union. |
| 8 (frontend, optional UX) | `frontend/src/components/script/<your-preview>.tsx` | If your strategy needs a preview UI (e.g. the `CinematicChaptersPreview` for `life-as-a`). |

Do **not** touch `scriptwriter.py`, `ideation.py`, `remotion_render.py`, `api/scripts.py`, `api/ideas.py`, `api/cold_opens.py`, `api/visuals.py`, `api/thumbnail.py`, `api/formats.py`, `IdeationPage.tsx`, or `ScriptGenerationPage.tsx`. They already dispatch through the registry; if you find yourself wanting to edit them, your `VideoFormat` is missing a flag or your strategy is the wrong shape.

The `GET /api/formats` endpoint at [`backend/api/formats.py`](../../backend/api/formats.py) auto-discovers your new format via `list_formats()` — no endpoint changes required.

## 3. Anatomy of `VideoFormat`

Every field in [`backend/pipeline/formats/base.py:55`](../../backend/pipeline/formats/base.py) (`VideoFormat`):

```python
@dataclass(frozen=True)
class VideoFormat:
    id: str
    display_name: str
    short_description: str

    level_count: int | tuple[int, int]
    level_label: str

    ideation_prompt: PromptDef
    script_system_prompt: PromptDef
    outline_prompt: PromptDef | None
    segment_scenes_prompt: PromptDef | None

    supports_cold_open: bool
    supports_hook_scoring: bool
    supports_segmented_generation: bool

    title_card_strategy: TitleCardStrategy
    visual_beat_rules: VisualBeatRules

    enforce_post_processing: Callable[[ScriptContent], ScriptContent]
```

| Field | Controls | Consequences if changed |
|---|---|---|
| `id` | Stable string key in registry, persisted in `Script.format_id` and `ScriptContent.format_id`. | Renaming breaks all existing scripts in the DB. Pick one and don't change it. |
| `display_name` | Human label in the frontend `FormatSelector`. | Cosmetic — safe to change anytime. |
| `short_description` | One-line tagline shown under the radio button. | Cosmetic. |
| `level_count` | Either an `int` (fixed count, e.g. `8`) or `(min, max)` tuple. Drives the user-message line `"Use exactly N {level_label}s"` or `"Use between LO and HI {level_label}s"` injected by `generate_script` ([`scriptwriter.py:145-151`](../../backend/pipeline/scriptwriter.py)) and the API's `level_count_min` / `level_count_max` fields. | Tighter ranges = more rigid scripts. The frontend reads min/max from `/api/formats` and displays them in the selector. |
| `level_label` | Word used in user message + in surfaced UI: `"segment"` for listicle, `"level"` for life-as-a. | Surfaces in narration system prompts as the canonical noun for "section". |
| `ideation_prompt` | `PromptDef` used by `generate_ideas` ([`pipeline/ideation.py:46`](../../backend/pipeline/ideation.py)). | Must produce JSON `{ideas: [...]}` shape compatible with `VideoIdea.model_validate`. |
| `script_system_prompt` | The Claude system prompt passed to `chat()` in `generate_script`. | The single largest determinant of script style. Most format DNA lives here. |
| `outline_prompt` | Used in segmented-generation Phase 1 (outline only, no scenes). Required iff `supports_segmented_generation=True`. | Output shape must include `segments[]` (or `levels[]` in `life-as-a`) so Phase 2 can iterate. |
| `segment_scenes_prompt` | Used in Phase 2: scenes for one segment/level at a time. Required iff `supports_segmented_generation=True`. | Output must be `{"scenes": [...]}` — a flat list of `Scene` objects. The orchestrator unpacks this into `Segment.scenes`. |
| `supports_cold_open` | If `False`, [`api/cold_opens.py:64`](../../backend/api/cold_opens.py) returns 400, and `scriptwriter.py:162` ignores any `cold_open_text`. | Whole cold-open phase + hook refinement disappear for this format. |
| `supports_hook_scoring` | Gates the hook-scoring branch in [`api/scripts.py:573`](../../backend/api/scripts.py). | `hook_score` will be `None` on generated `ScriptContent` if disabled. |
| `supports_segmented_generation` | If `False`, the user-facing `segmented` toggle is honored only when the format opts in. Falls back to single-pass generation otherwise ([`scriptwriter.py:180`](../../backend/pipeline/scriptwriter.py)). | If `False`, `outline_prompt` and `segment_scenes_prompt` may be `None`. |
| `title_card_strategy` | Pluggable object satisfying `TitleCardStrategy` protocol. Routes thumbnail + per-scene title-card preparation. | See section 5. |
| `visual_beat_rules` | `VisualBeatRules` dataclass parameterizing `_fix_visual_monotony` ([`scriptwriter.py:54`](../../backend/pipeline/scriptwriter.py)). | See section 6. |
| `enforce_post_processing` | Callable run after Claude generation, before monotony fixing ([`scriptwriter.py:232`](../../backend/pipeline/scriptwriter.py)). Signature: `(ScriptContent) -> ScriptContent`. May mutate-and-return, must be idempotent. | Place format-specific cleanups here (coercing illegal beats, inserting required title cards, synthesizing missing fields). |

The dataclass is `frozen=True` — once registered, treat the format as immutable.

## 4. Prompt slots

A format has up to four prompt slots. All four are `PromptDef` objects defined in [`backend/prompts.py`](../../backend/prompts.py) and registered via `register(PromptDef(...))` so they appear in the global `PROMPTS` dict.

### `ideation_prompt`

- **Consumer:** `pipeline/ideation.py:48` calls `fmt.ideation_prompt.template` (or `.build(...)` if a builder is set).
- **Output contract:** `{"ideas": [{"title": str, "segments_est": int, "description": str, "keywords": [str], ...}]}`.
- **Format-specific extras** are allowed (e.g. `closing_image` in `LIFE_AS_A_IDEATION_SYSTEM` — see [`prompts.py:1708`](../../backend/prompts.py)) — they ride along on `VideoIdea` if the model schema accepts them.

### `script_system_prompt`

- **Consumer:** [`scriptwriter.py:173`](../../backend/pipeline/scriptwriter.py) sets it as the Claude system prompt. For `composite-grid` formats, `TITLE_CARD_PROMPT_INSTRUCTIONS` is appended (`scriptwriter.py:176-177`); for other strategies you must bake title-card instructions into the system prompt directly.
- **Output contract:** Valid JSON parsable into `ScriptContent` ([`models/script.py:134`](../../backend/models/script.py)). The most important fields are `title`, `segments[].name`, `segments[].scenes[]`, `intro_hook`, `outro_cta`. Format-specific fields (`cinematic_thumbnail_prompt`, `levels[]`) are optional on the model, so you can require them in the prompt without touching the schema.
- **Single-pass vs segmented:** If `supports_segmented_generation=False`, this prompt drives the entire script in one Claude call. If `True` and `segmented=True` is requested, this prompt is the system prompt for *both* phases.

### `outline_prompt`

- **Consumer:** [`scriptwriter.py:200`](../../backend/pipeline/scriptwriter.py) (`_generate_outline`).
- **Output contract:** JSON outline with `segments[]` (or in `life-as-a`'s case, parallel `segments[]` and `levels[]`). Must NOT include scene narration — only metadata. Phase 2 walks `segments` and emits scenes per segment.
- **Reference:** `SCRIPT_OUTLINE_INSTRUCTIONS` ([`prompts.py:329`](../../backend/prompts.py)) for listicle; `LIFE_AS_A_OUTLINE_INSTRUCTIONS` ([`prompts.py:584`](../../backend/prompts.py)) for life-as-a.

### `segment_scenes_prompt`

- **Consumer:** Phase-2 inner loop in `_generate_segmented`. Called once per segment.
- **Output contract:** `{"scenes": [Scene, ...]}` — a flat array. The orchestrator assigns this list to `segment.scenes` and renumbers `Scene.id` globally afterward.
- **Important:** Per scene, narration length and beat distribution are governed by the prompt. A `life-as-a` segment yields ~3–5 scenes with 3–8 sentences each; a listicle segment yields ~5–10 scenes with 1–2 sentences each. There is no orchestrator-side enforcement — your prompt is the contract.

### Authoring tips

- Inherit shared scaffolding (visual beat system, shot-type vocabulary, frame_directives JSON shape) by copy-paste, not by import. The prompts are independent reference texts and divergence is expected.
- Use the `expected_output_format` field on `PromptDef` as documentation; it isn't parsed.
- Use the `RetentionMeta` field to record intent — it's surfaced in the dev dashboard.

## 5. Title-card strategy contract

The `TitleCardStrategy` protocol ([`base.py:21`](../../backend/pipeline/formats/base.py)):

```python
class TitleCardStrategy(Protocol):
    kind: str  # "composite-grid" | "cinematic-chapters" | <yours>

    def prepare_thumbnail(
        self,
        script_id: str,
        content: ScriptContent,
        accent_color: str,
        force: bool = False,
        job_id: str | None = None,
    ) -> None: ...

    def prepare_title_card_scene(
        self,
        scene: Scene,
        script_id: str,
        content: ScriptContent,
        brand: dict,
    ) -> Scene: ...
```

### When each method is called

- `prepare_thumbnail` is invoked from [`api/visuals.py:298`](../../backend/api/visuals.py) (background thread, idempotent, gated by `force`). It is responsible for generating any image files the format needs at thumbnail-generation time: the YouTube thumbnail itself, plus any per-segment / per-level title-card or chapter-card images. The thumbnail endpoint at [`api/thumbnail.py:65`](../../backend/api/thumbnail.py) also resolves the strategy.
- `prepare_title_card_scene` is invoked from [`pipeline/remotion_render.py:482`](../../backend/pipeline/remotion_render.py) once per scene at render-time. It mutates the `scene` object — typically setting `scene.image_url` and packing overlay metadata into `scene.visual_source_metadata`. Returning the scene is required even if unchanged.

### Files a strategy "owns"

- The strategy decides where images live under `data/projects/{script_id}/images/`. Names must be stable so the cache (mtime check vs source) works.
- The strategy decides what to stuff into `Scene.visual_source_metadata` (a `dict | None` already serialized by Remotion). It's the carrier for any non-image render-time data — e.g. `cinematic-chapters` packs `chapter_overlay = {level_number, descriptor}` here ([`cinematic_chapters.py:122-127`](../../backend/pipeline/formats/title_cards/cinematic_chapters.py)).

### Worked example: `composite-grid`

[`backend/pipeline/formats/title_cards/composite_grid.py`](../../backend/pipeline/formats/title_cards/composite_grid.py) is a thin wrapper over the pre-existing N-circle composite pipeline. It delegates entirely:

```python
def prepare_thumbnail(self, script_id, content, accent_color, force=False, job_id=None) -> None:
    ensure_title_card_images(script_id=script_id, content=content,
                             accent_color=accent_color, force=force, job_id=job_id)

def prepare_title_card_scene(self, scene, script_id, content, brand) -> Scene:
    return _legacy_prepare(scene, script_id, brand)
```

The legacy logic (`pipeline/title_card.py`, `pipeline/modifiers/title_cards.py`) generates one circle image per segment, composites them into a single grid image, and at render time replaces the title-card scene's image with the composite + a zoom target. No overlay metadata is set; Remotion just zooms into the right circle.

### Worked example: `cinematic-chapters`

[`backend/pipeline/formats/title_cards/cinematic_chapters.py`](../../backend/pipeline/formats/title_cards/cinematic_chapters.py) takes a different approach — there is no composite grid. Instead:

1. **`prepare_thumbnail`** generates `cinematic_thumbnail_clean.png` via Gemini (using `content.cinematic_thumbnail_prompt`), copies it to `chapter_1.png` (level 1 reuses this image — no separate generation), then generates `chapter_N.png` for levels 2..N from `levels[i].image_prompt`. Two time-period labels are picked and persisted to `cinematic_thumbnail.levels.json` for re-render stability: left uses `3 months in` through `8 months in`, and right uses `8 years in` through `15 years in`. Finally, `enhance_split_progression()` calls Gemini once with `SPLIT_PROGRESSION_PROMPT` to transform the clean image into `cinematic_thumbnail.png` — a split-progression composite with a diagonal divider, the two time-period labels, and no video title text. Total Gemini calls: N + 1 (1 cinematic + N-1 chapter images + 1 enhancement). All images live at predictable paths: `data/projects/{script_id}/images/cinematic_thumbnail{,_clean}.png` and `chapter_{N}.png`.
2. **`prepare_title_card_scene`** maps the title-card scene back to a level number (by counting prior title cards in `content.all_scenes()`), points `scene.image_url` at the chapter image, and packs `chapter_overlay = {level_number, descriptor}` into `scene.visual_source_metadata`. Remotion's `TitleCardScene.tsx` ([`remotion/src/scenes/TitleCardScene.tsx:19`](../../remotion/src/scenes/TitleCardScene.tsx)) reads `scene.chapter_overlay` and renders the two-line text overlay.

### Adding a new strategy

Implement the protocol, drop it under `backend/pipeline/formats/title_cards/`, expose a singleton (e.g. `MY_STRATEGY = MyStrategy()`), import it in your format module. The frontend type union at [`frontend/src/types/format.ts:11`](../../frontend/src/types/format.ts) is `"composite-grid" | "cinematic-chapters"` — widen it if you add a new kind, or the TypeScript build will fail.

## 6. Visual beat rules

`VisualBeatRules` ([`base.py:14`](../../backend/pipeline/formats/base.py)):

```python
@dataclass(frozen=True)
class VisualBeatRules:
    allowed_beats: frozenset[str]
    target_distribution: dict[str, tuple[float, float]] = field(default_factory=dict)
    max_consecutive_same_beat: int = 3
    monotony_threshold: int = 3
```

`_fix_visual_monotony` ([`scriptwriter.py:54`](../../backend/pipeline/scriptwriter.py)) walks the flattened scene list, finds runs of identical `visual_beat` longer than `monotony_threshold`, and rewrites every third scene in the run to a different (allowed) beat.

| Field | Effect |
|---|---|
| `allowed_beats` | The pool from which alternatives are drawn when breaking a run. Beats outside this set are *not* candidates for substitution but are still observed when detecting runs. |
| `target_distribution` | Currently advisory — emitted in logs, not enforced by `_fix_visual_monotony`. Reserved for a future target-driven rebalancer. |
| `max_consecutive_same_beat` | Soft contract — your post-processor or prompt enforces it. The monotony fixer doesn't read this directly. |
| `monotony_threshold` | The minimum run length before the fixer intervenes. Set to a value larger than your max scene count (e.g. `99`) to **fully disable** run-breaking — see `LIFE_AS_A_BEAT_RULES` ([`life_as_a.py:31`](../../backend/pipeline/formats/life_as_a.py)) where long static runs are intentional. |

Disabling the fixer is appropriate when:
- The format's narrative voice depends on long uninterrupted runs (literary, contemplative pacing).
- The post-processor (`enforce_post_processing`) already coerces beats into a constrained set.

For listicle, runs are catastrophic for retention so `monotony_threshold=3`. For life-as-a, runs are *the point* so it's set to `99`.

## 7. Generation flag interactions

Each `supports_*` flag gates one specific behavior. Trace each in the codebase before flipping it.

### `supports_cold_open`

When `False`:
1. `POST /api/scripts/cold-opens` returns `400 Bad Request` ([`api/cold_opens.py:64-68`](../../backend/api/cold_opens.py)).
2. `scriptwriter.generate_script` ignores `cold_open_text` even if passed ([`scriptwriter.py:162`](../../backend/pipeline/scriptwriter.py): `if cold_open_text and fmt.supports_cold_open`).
3. The frontend `ScriptGenerationPage` hides the cold-open A/B selection step ([`ScriptGenerationPage.tsx:42`](../../frontend/src/components/script/ScriptGenerationPage.tsx): `const supportsColdOpen = format?.supports_cold_open ?? true;`).

### `supports_hook_scoring`

When `False`:
1. `api/scripts.py:573-587` skips the hook-scoring branch in the background generation thread. The `hook_score` field on `ScriptContent` stays `None`.
2. The hook-refinement endpoints (`/api/scripts/refine-hook`) remain available — they're not gated. (You generally don't surface them in the UI for formats without hook scoring.)
3. The frontend reads `format.supports_hook_scoring` to hide hook-related UI affordances on the script generation page.

### `supports_segmented_generation`

When `False`:
1. Even if the user toggles `segmented=true` in the request, `scriptwriter.py:180` (`use_segmented = segmented and fmt.supports_segmented_generation`) forces single-pass.
2. `outline_prompt` and `segment_scenes_prompt` may be `None`. If `True` and either is `None`, `generate_script` raises `RuntimeError` ([`scriptwriter.py:182-186`](../../backend/pipeline/scriptwriter.py)).

When `True`, single-pass is still allowed — the user opts in via the request body's `segmented` flag.

### Frontend consumption

`GET /api/formats` ([`backend/api/formats.py`](../../backend/api/formats.py)) summarizes all three flags onto the response object. The frontend `VideoFormat` type ([`frontend/src/types/format.ts`](../../frontend/src/types/format.ts)) mirrors them. `IdeationPage.tsx` and `ScriptGenerationPage.tsx` read the flags to drive conditional UI.

## 8. Backwards-compatibility model

Existing scripts in the database predate the format system. They must continue to render and re-export without migrations. Three guards work together:

1. **Column default.** `Script.format_id` ([`models/script.py:174`](../../backend/models/script.py)) is declared `Field(default="youtube-listicle", index=True)`. SQLite back-fills new rows; old rows already have `youtube-listicle` baked into their JSON (or pick up the default at read time).
2. **JSON default.** `ScriptContent.format_id` ([`models/script.py:157`](../../backend/models/script.py)) defaults to `"youtube-listicle"`. Pydantic populates it on `model_validate` if missing.
3. **Defensive read helper.** [`pipeline.formats.resolve_format()`](../../backend/pipeline/formats/__init__.py) returns `youtube-listicle` for `None` or unknown IDs and logs a warning. Use this everywhere you read a `format_id` from persisted state. `get_format()` raises — only call it from generation paths where the ID was just selected by the user.

Convention: **`get_format` for write paths (generation), `resolve_format` for read paths (rendering, post-generation API endpoints).** Search for `get_format(` vs `resolve_format(` in the codebase to confirm.

Format-specific optional fields on `ScriptContent` (`cinematic_thumbnail_prompt`, `levels`) are typed as `... | None`. Older scripts deserialize cleanly with these fields absent.

## 9. Testing a new format

Two test files cover a new format:

### `backend/tests/pipeline/test_<format>_post_processing.py`

Modeled on [`test_life_as_a_post_processing.py`](../../backend/tests/pipeline/test_life_as_a_post_processing.py). Test cases:

- **Disallowed beats are coerced.** Build a `ScriptContent` containing illegal beats, run your post-processor, assert they were rewritten.
- **Required scaffolding is inserted when missing.** E.g. life-as-a inserts a chapter card at the head of every segment if Claude omitted one.
- **Synthesized fields populate when missing.** E.g. life-as-a synthesizes `levels[]` from segments if absent.
- **Existing fields are preserved.** Idempotency: running the post-processor on already-correct content must not damage it.

Each test constructs a minimal `ScriptContent` (use the `_scene` helper from `test_life_as_a_post_processing.py:12-19` as a template) and calls the post-processor directly — no mocks needed.

### `backend/tests/pipeline/test_formats_registry.py`

Add a one-test stanza like [`test_life_as_a_flags`](../../backend/tests/pipeline/test_formats_registry.py:51) (4–5 assertions on the format's flags + strategy kind + label). Add the format ID to the assertion in `test_list_formats_returns_registered_formats` (line 39).

Run tests with:

```bash
uv run pytest backend/tests/pipeline/test_formats_registry.py \
              backend/tests/pipeline/test_<format>_post_processing.py -v
```

End-to-end: `pipeline/scriptwriter.py:generate_script` is exercised by the smoke test `test_generate_script_dispatches_to_format` ([`test_formats_registry.py:60`](../../backend/tests/pipeline/test_formats_registry.py)). For a new format, copy that test, mock `chat`, and assert the right system prompt was passed.

## 10. Worked example: `life-as-a`

A retracing of how `life-as-a` was added, in commit order, as a reference walkthrough.

### Step 1 — Add prompts

Four `PromptDef`s went into [`backend/prompts.py`](../../backend/prompts.py):

- `LIFE_AS_A_IDEATION_SYSTEM` (line 1702) — generates "Your Life As A {role}" titles, returns ideas with extra `closing_image` field.
- `LIFE_AS_A_SCRIPT_SYSTEM` (line 418) — the long-form literary system prompt. Bakes title-card instructions in (no `TITLE_CARD_PROMPT_INSTRUCTIONS` append happens for non-`composite-grid` strategies).
- `LIFE_AS_A_OUTLINE_INSTRUCTIONS` (line 584) — Phase 1 outline. Output shape: `{title, levels[], cinematic_thumbnail_prompt, intro_hook, outro_cta, segments[]}` with `levels` and `segments` parallel.
- `LIFE_AS_A_LEVEL_SCENES_INSTRUCTIONS` (line 660) — Phase 2 per-level scenes. Output: `{"scenes": [...]}`.

Each is `register(...)`-wrapped so it appears in the global `PROMPTS` dict.

### Step 2 — Define the title-card strategy

[`backend/pipeline/formats/title_cards/cinematic_chapters.py`](../../backend/pipeline/formats/title_cards/cinematic_chapters.py) implements `TitleCardStrategy`. Key choices:

- One cinematic thumbnail (clean + with title) generated from `content.cinematic_thumbnail_prompt`.
- One chapter-card image per `LevelMeta` in `content.levels`, named `chapter_{N}.png`.
- Per-scene preparation maps title-card scenes to chapter images via positional order in `content.all_scenes()` and packs `chapter_overlay` overlay metadata into `scene.visual_source_metadata`.

### Step 3 — Define the post-processor

`enforce_life_as_a_constraints` ([`life_as_a.py:34`](../../backend/pipeline/formats/life_as_a.py)) does three things:

1. Coerces disallowed text-only beats (`aha_subtitle`) to `"static"` and normalizes legacy multi-frame aliases (`quick_cuts`, `montage`) to canonical `"multi_frame"`.
2. Inserts a chapter-card scene at the head of every segment that's missing one.
3. Synthesizes `content.levels[]` from `segments` if Claude omitted them.

Idempotent: running it twice produces the same result.

### Step 4 — Define the visual beat rules

`LIFE_AS_A_BEAT_RULES` ([`life_as_a.py`](../../backend/pipeline/formats/life_as_a.py)) constrains beats to `{static, continuous, multi_frame}`, keeps `quick_cuts` only as a legacy compatibility alias, and uses `monotony_threshold=3`.

### Step 5 — Compose the `VideoFormat` and register

[`life_as_a.py:85-101`](../../backend/pipeline/formats/life_as_a.py):

```python
LIFE_AS_A = _register(VideoFormat(
    id="life-as-a",
    display_name="Your Life As A...",
    short_description='A walk through the stages of being something — literary, 4–7 levels, second-person.',
    level_count=(4, 7),
    level_label="level",
    ideation_prompt=LIFE_AS_A_IDEATION_SYSTEM,
    script_system_prompt=LIFE_AS_A_SCRIPT_SYSTEM,
    outline_prompt=LIFE_AS_A_OUTLINE_INSTRUCTIONS,
    segment_scenes_prompt=LIFE_AS_A_LEVEL_SCENES_INSTRUCTIONS,
    supports_cold_open=False,
    supports_hook_scoring=False,
    supports_segmented_generation=True,
    title_card_strategy=CINEMATIC_CHAPTERS,
    visual_beat_rules=LIFE_AS_A_BEAT_RULES,
    enforce_post_processing=enforce_life_as_a_constraints,
))
```

### Step 6 — Wire bootstrap

A single line was added to `_bootstrap()` in [`backend/pipeline/formats/__init__.py:55`](../../backend/pipeline/formats/__init__.py): `from . import life_as_a  # noqa: F401`. Import side-effect registers the format.

### Step 7 — Tests

- Registry-level assertions added to [`test_formats_registry.py:51-57`](../../backend/tests/pipeline/test_formats_registry.py).
- Post-processor tests in [`test_life_as_a_post_processing.py`](../../backend/tests/pipeline/test_life_as_a_post_processing.py) covering the four cases listed in section 9.

### Step 8 — Frontend (only the bare minimum)

- `frontend/src/types/format.ts` widened `title_card_strategy_kind` to include `"cinematic-chapters"`.
- A new `CinematicChaptersPreview` component was added under `frontend/src/components/script/` for the strategy-specific preview UX.
- `IdeationPage.tsx` and `ScriptGenerationPage.tsx` read the format object and conditionally hide cold-open + hook-scoring UI when those flags are `false`.

No backend pipeline files (`scriptwriter.py`, `ideation.py`, `remotion_render.py`) were touched. The single registration line + the prompts + the strategy + the post-processor are the entire surface area.

For the design rationale (why `life-as-a` exists, what the format taxonomy is for), see the spec at [`docs/superpowers/specs/2026-05-19-script-formats-design.md`](../superpowers/specs/2026-05-19-script-formats-design.md). For the file-by-file plan that built it, see [`docs/superpowers/plans/2026-05-19-script-formats.md`](../superpowers/plans/2026-05-19-script-formats.md).
