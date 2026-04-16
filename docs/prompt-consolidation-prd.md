# Prompt Consolidation: `backend/prompts.py`

## Context

Prompts are currently scattered across 14 pipeline files + 5 markdown files + 1 modifier. This makes it hard to audit for retention impact, detect contradictions, or iterate on prompt strategy. This refactor moves all prompt definitions into a single `backend/prompts.py` module while keeping orchestration logic (API calls, retries, JSON parsing) in the pipeline files where it belongs.

---

## Architecture

### Data Model

```python
@dataclass(frozen=True)
class RetentionMeta:
    goal: str = ""                    # "Keep viewers past 10s mark"
    failure_mode: str = ""            # "Generic intro causes early drop-off"
    metrics_to_watch: list[str] = field(default_factory=list)

@dataclass(frozen=True)
class PromptDef:
    name: str                         # "FX_SYSTEM"
    domain: str                       # "FX", "SCRIPT", "IMAGE", "SEO", etc.
    purpose: str                      # One-liner
    template: str                     # Raw text (or "" if dynamic)
    builder: Callable[..., str] | None = None   # For f-string prompts
    inputs: list[str] = field(default_factory=list)
    expected_output_format: str = ""
    target_model: str = "claude"      # "claude" | "gemini"
    retention: RetentionMeta = field(default_factory=RetentionMeta)

PROMPTS: dict[str, PromptDef] = {}   # Global registry
```

- **Static prompts**: `template` is set, `builder` is None. Pipeline does `chat(PROMPT.template, ...)`
- **Dynamic prompts**: `builder` takes kwargs, returns final string. Used for prompts with config interpolation (ideation's segment counts, title card f-string)
- Frozen dataclasses = immutable, introspectable, no framework baggage

### Domain Grouping (sections in prompts.py)

| Domain | Prompts | Source Files |
|--------|---------|-------------|
| **SCRIPT** | `SCRIPT_SYSTEM`, `SCRIPT_OUTLINE_INSTRUCTIONS`, `SCRIPT_SEGMENT_SCENES_INSTRUCTIONS`, `SCRIPT_RETRY_CRITIQUE`, `COLD_OPEN_ADDENDUM`, `TITLE_CARD_INSTRUCTIONS`, `SCRIPT_REVIEW_RUBRIC`, `REFINE_SYSTEM`, `TIGHTEN_SYSTEM` | `scriptwriter.py`, `cold_open.py`, `title_cards.py`, `script_reviewer.py`, `refine.py`, `duration_variance.py` |
| **FX** | `FX_SYSTEM` | `fx_generator.py` |
| **CHARACTER** | `ELI_ANIMATOR_SYSTEM`, `CHARACTER_SPEC`, `GREEN_BG_INSTRUCTION`, `REFERENCE_CONSISTENCY_INSTRUCTION`, `FRAME_DEFINITIONS`, `THUMBNAIL_FRAME_DEFINITIONS`, `VARIANT_PROMPTS` | `eli_animator.py`, `character_frames.py` |
| **IMAGE** | `IMAGE_VISUAL_STYLE`, `IMAGE_COMPOSITION_GUIDE`, `IMAGE_CHARACTER_IN_SCENE`, `IMAGE_CTR_EXPRESSION_GUIDANCE` | `image_gen.py`, `thumbnail.py` + inlined `.md` files |
| **IDEATION** | `IDEATION_SYSTEM`, `SMART_IDEATION_SYSTEM`, `FORMAT_FIT_SYSTEM` | `ideation.py`, `smart_ideation.py`, `trending_scorer.py` |
| **SEO** | `SEO_SYSTEM` | `seo.py` |
| **EVAL** | `PROFILE_SYSTEM` | `content_profile.py` |

### What Moves vs What Stays

**Moves to `prompts.py`:**
- All system prompt strings and constants
- Reusable prompt fragments (`CHARACTER_SPEC`, `GREEN_BG_INSTRUCTION`, etc.)
- `FRAME_DEFINITIONS` + `THUMBNAIL_FRAME_DEFINITIONS` data
- Prompt builder functions (`_build_prompt`, `_build_variant_prompt` from `character_frames.py`)
- Image prompt composition helper: `compose_image_prompt()`
- Script system prompt composition: `compose_script_system_prompt()`

**Stays in pipeline files:**
- User message construction (tightly coupled to function args + control flow)
- JSON serialization of scene data for user messages
- Retry/review logic, API call orchestration
- All non-prompt constants and utilities

### `.md` Files Decision

Inline all 5 markdown files as triple-quoted string constants in `prompts.py`. Delete the `backend/prompts/` directory after migration. Rationale: they're already loaded at import time as module-level strings; keeping them as files defeats single-file consolidation.

---

## Migration Steps

### Step 1: Create `backend/prompts.py` (additive only, nothing breaks)

Create the file with:
- `PromptDef`, `RetentionMeta` dataclasses + `PROMPTS` registry
- All prompts defined as registered `PromptDef` objects, organized by domain
- Inline the 5 `.md` files as string constants
- `compose_image_prompt()` and `compose_script_system_prompt()` helpers
- Character frame prompt builders from `character_frames.py`
- `FRAME_DEFINITIONS`, `THUMBNAIL_FRAME_DEFINITIONS`, `VARIANT_PROMPTS` data
- `audit_report()` utility function
- `detect_conflicts()` function with regex-based contradiction rules

**Verify:** `uv run python -c "import prompts; print(len(prompts.PROMPTS))"` succeeds

### Step 2: Migrate simple pipeline files (one at a time, low risk)

Replace inline prompts with imports. Each file follows the same pattern:

```python
# Before: SYSTEM_PROMPT = """..."""
# After:  from prompts import SEO_SYSTEM
#         ... chat(SEO_SYSTEM.template, user_msg, ...)
```

Order (simplest first):
1. `pipeline/seo.py` — replace `SYSTEM_PROMPT`
2. `pipeline/refine.py` — replace `SYSTEM_PROMPT`
3. `pipeline/content_profile.py` — replace `PROFILE_SYSTEM_PROMPT`
4. `pipeline/duration_variance.py` — replace `_TIGHTEN_SYSTEM_PROMPT`
5. `pipeline/smart_ideation.py` — replace `SMART_IDEATION_SYSTEM`
6. `pipeline/trending_scorer.py` — replace `FORMAT_FIT_SYSTEM`
7. `pipeline/fx_generator.py` — replace `FX_SYSTEM_PROMPT`
8. `pipeline/eli_animator.py` — replace `ELI_SYSTEM_PROMPT`
9. `pipeline/script_reviewer.py` — replace `REVIEW_RUBRIC`
10. `pipeline/ideation.py` — replace `SYSTEM_PROMPT` (uses builder for segment count interpolation)

### Step 3: Migrate complex files (higher risk, more moving parts)

11. `pipeline/cold_open.py` — replace `_COLD_OPEN_ADDENDUM`, use `compose_script_system_prompt(cold_open=True)`
12. `pipeline/modifiers/title_cards.py` — replace `TITLE_CARD_PROMPT_INSTRUCTIONS` (builder with config dependency)
13. `pipeline/scriptwriter.py` — replace `BASE_SYSTEM_PROMPT`, `_OUTLINE_INSTRUCTIONS`, `_SEGMENT_SCENES_INSTRUCTIONS`, retry critique template. Use `compose_script_system_prompt()` for the combined system prompt.
14. `pipeline/image_gen.py` — replace `_VISUAL_STYLE`, `_STYLE_GUIDE`, `_CHARACTER_PROMPT` and prompt assembly with `compose_image_prompt()` calls
15. `pipeline/character_frames.py` — replace `CHARACTER_SPEC`, `GREEN_BG_INSTRUCTION`, `REFERENCE_CONSISTENCY_INSTRUCTION`, `_VARIANT_PROMPTS`, `FRAME_DEFINITIONS`, `THUMBNAIL_FRAME_DEFINITIONS`, and builder functions
16. `pipeline/thumbnail.py` — replace `_CTR_EXPRESSION_GUIDANCE`

### Step 4: Clean up

- Delete `backend/prompts/script_prompt.md`, `image_gen_guide.md`, `visual_style.md`, `character_in_scene.md`, `character.md`
- Remove `backend/prompts/` directory
- Remove `_PROMPTS_DIR` / `read_prompt()` from any helpers if present

### Step 5: Fill in retention metadata

Add `RetentionMeta` to every `PromptDef` with:
- `goal` — what retention outcome this prompt targets
- `failure_mode` — how it can hurt retention
- `metrics_to_watch` — what to monitor

---

## Retention Audit System

### Per-Prompt Metadata

Every prompt carries a `RetentionMeta`. Example:

```python
COLD_OPEN_ADDENDUM = register(PromptDef(
    ...
    retention=RetentionMeta(
        goal="Generate hooks that maximize first-30s retention",
        failure_mode="Vague or slow openings cause immediate viewer drop-off",
        metrics_to_watch=["retention_0_30s", "avg_view_duration", "click_through_rate"],
    ),
))
```

### `audit_report()` Function

Returns all prompts as serializable dicts grouped by retention phase:
- **Hook (0-30s):** `COLD_OPEN_ADDENDUM`, `SCRIPT_SYSTEM` (intro_hook section)
- **Engagement (30s-2min):** `SCRIPT_SYSTEM` (mosaic structure, payoff promise), `FX_SYSTEM`
- **Sustained (2min+):** `SCRIPT_SYSTEM` (callbacks, steel-manning), `ELI_ANIMATOR_SYSTEM`
- **Re-engagement:** `FX_SYSTEM` (zoom punches), `TIGHTEN_SYSTEM` (overlong scenes)

Optional `/api/prompts/audit` endpoint can expose this.

---

## Conflict Detection

Regex-based contradiction rules in `detect_conflicts()`:

```python
_CONTRADICTION_RULES = [
    ("text_in_images", r"NEVER include any text", r"include.*text.*label", "..."),
    ("segment_count", r"exactly \d+ or \d+ segments", r"any number of segments", "..."),
    ("output_format", r"Return ONLY valid JSON", r"Return.*markdown", "..."),
]
```

Run at import time (logs warnings) or on demand. Easy to extend when new contradiction classes are discovered.

---

## Verification Plan

1. **Byte-level prompt verification:** After each migration step, hash the prompt string produced by the old code vs the new code. They must match exactly.
2. **Import test:** `uv run python -c "import prompts; print(len(prompts.PROMPTS))"` after Step 1
3. **Backend startup test:** `npm run dev:backend` after each migration step — app must start without errors
4. **End-to-end test:** After full migration, generate an idea, a script, images, and FX to verify the pipeline produces identical output
5. **Conflict detection:** Run `detect_conflicts()` after all prompts are registered — should return empty list (no known contradictions)

---

## Key Files

| File | Role |
|------|------|
| `backend/prompts.py` | **NEW** — Central prompt registry |
| `backend/pipeline/scriptwriter.py` | Most complex migration (base + outline + segment + retry) |
| `backend/pipeline/character_frames.py` | Largest data migration (`FRAME_DEFINITIONS`, builders) |
| `backend/pipeline/image_gen.py` | Prompt composition logic moves to `compose_image_prompt()` |
| `backend/pipeline/modifiers/title_cards.py` | Builder with config dependency |
| `backend/pipeline/seo.py` | Simplest migration (template pattern) |
| `backend/pipeline/fx_generator.py` | Template pattern |
| `backend/pipeline/eli_animator.py` | Template pattern |
| `backend/pipeline/cold_open.py` | Uses `compose_script_system_prompt()` |
| `backend/pipeline/refine.py` | Template pattern |
| `backend/pipeline/ideation.py` | Builder pattern (segment count interpolation) |
| `backend/pipeline/smart_ideation.py` | Template pattern |
| `backend/pipeline/trending_scorer.py` | Template pattern |
| `backend/pipeline/script_reviewer.py` | Template pattern (targets Gemini) |
| `backend/pipeline/content_profile.py` | Template pattern |
| `backend/pipeline/duration_variance.py` | Template pattern |
| `backend/pipeline/thumbnail.py` | Template pattern |
