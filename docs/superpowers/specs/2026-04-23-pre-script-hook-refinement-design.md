# Pre-Script Hook Refinement

**Date:** 2026-04-23
**Status:** Design

## Problem

The hook retention score (Promise/Tension/Payoff Hint analysis with actionable suggestions) currently runs *after* the full script is generated. By then, the suggestions are hard to act on — the script is already built around the original hook. Users need this feedback loop to happen *before* script generation so improvements are incorporated seamlessly.

## Solution

Insert a **score → auto-rewrite** step between cold open selection and script generation. After the user picks a cold open variant, Claude deep-scores the hook, then automatically rewrites the intro_hook + opening_narration to address weaknesses. The refined version feeds into script generation as `cold_open_text`.

## Pipeline Flow

```
User picks cold open variant
  ↓
[NEW] Deep Hook Score — score_hook() on intro_hook + opening_narration
  ↓
[NEW] Hook Refine — refine_hook() rewrites hook using score + suggestions
  ↓
[EXISTING] Script Generation — uses refined cold_open_text
  ↓
[EXISTING] Post-script Hook Score — scores final version with full scene context
```

Single pass: score once, rewrite once, move on. No iteration loop.

The post-script hook score remains unchanged — it serves as the "final grade" in full scene context. The pre-script score is a draft-quality check.

## Backend

### New: `backend/pipeline/hook_refiner.py`

```python
class RefinedHook(BaseModel):
    intro_hook: str
    opening_narration: str

def refine_hook(
    intro_hook: str,
    opening_narration: str,
    hook_score: HookScore,
    video_title: str,
) -> RefinedHook:
```

Claude receives:
- Original intro_hook and opening_narration
- Full HookScore breakdown (scores, reasoning, suggestions)
- Video title for context

Prompt instructs Claude to rewrite the intro_hook and opening_narration to address weak dimensions while preserving what scored well. Returns the rewritten versions.

### Adapting `score_hook()` for Pre-Script Use

Add an optional `narration_text: str | None` parameter to `score_hook()`. When provided, it's used directly as the opening content instead of extracting narration from `hook_scenes: list[Scene]`. This avoids synthesizing pseudo-scenes from raw narration text.

Signature becomes:

```python
def score_hook(
    intro_hook: str,
    hook_scenes: list[Scene],
    video_title: str,
    script_id: str | None = None,
    narration_text: str | None = None,  # NEW — used in pre-script context
) -> HookScore:
```

When `narration_text` is provided, `hook_scenes` can be empty. The scorer prompt receives the narration text directly instead of formatted scene data.

### New API Endpoint

`POST /api/scripts/refine-hook`

Request body:
```json
{
  "topic": "string",
  "description": "string",
  "cold_open_index": 0,
  "cold_open_job_id": "string"
}
```

The endpoint looks up the cold open result from the job, extracts the selected variant by index. The `topic` field doubles as `video_title` for the scorer (matching current cold open generation behavior). It orchestrates:
1. `score_hook()` with `narration_text` — deep retention analysis
2. `refine_hook()` — rewrite using score + suggestions
3. Return both `HookScore` and `RefinedHook`

Runs as a background job. Poll via `GET /api/scripts/refine-hook-status/{job_id}`.

Response on completion:
```json
{
  "hook_score": { "promise": {...}, "tension": {...}, "payoff_hint": {...}, "overall": 82, "suggestions": [...] },
  "refined_hook": { "intro_hook": "...", "opening_narration": "..." },
  "original_hook": { "intro_hook": "...", "opening_narration": "..." }
}
```

## Frontend

### New Phase: `"refining"`

Phase sequence becomes: `cold_opens` → `selecting` → **`refining`** → `script` → `idle`

### `useScriptGeneration.ts` Changes

- Add `"refining"` to the phase union type
- `handleColdOpenSelect()` triggers `POST /api/scripts/refine-hook` instead of immediately starting script generation
- Poll `GET /api/scripts/refine-hook-status/{job_id}` during `refining` phase
- On completion, store `HookScore` + `RefinedHook` + original in state
- Auto-trigger script generation with refined `cold_open_text` (intro_hook + opening_narration concatenated)

### `ScriptGenerationPage.tsx` Changes

New render block for `phase === "refining"`:

1. **Loading sub-phase** — "Scoring your hook..." spinner (~3s), then "Refining your hook..." spinner (~3s)
2. **Result sub-phase** — Shows:
   - `HookScoreCard` with the deep score (passed as prop, not auto-fetched)
   - Before/after comparison: original intro_hook + narration (dimmed) vs. refined version (highlighted)
3. Auto-proceeds to `script` phase after ~2s, or user clicks "Continue" immediately

### `HookScoreCard.tsx` Changes

Add an optional `score: HookScore` prop. When provided, the component displays it directly instead of using `useHookScore` to auto-fetch. This allows reuse in both the refining phase (prop-driven) and the post-script phase (auto-fetched).

### New Component: `HookRefinementResult.tsx`

Lightweight before/after text comparison. Shows:
- Original intro_hook + opening_narration (dimmed, smaller text)
- Refined intro_hook + opening_narration (normal weight, highlighted)
- No editing, no approval — informational only

### No Changes To

- `ColdOpenSelector.tsx`
- Post-script `useHookScore.ts` (still auto-scores on script load)
- Timeline, properties panel, or downstream components
