# Pre-Script Hook Refinement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Score and auto-refine the hook between cold open selection and script generation so suggestions are incorporated before the full script is written.

**Architecture:** New `refining` phase inserted between cold open selection and script generation. Backend: adapt `score_hook()` to accept raw narration text, add `refine_hook()` pipeline function, add API endpoint that orchestrates score → refine as a background job. Frontend: new phase in generation state machine, reuse HookScoreCard with prop-driven score, add before/after display, auto-proceed to script gen.

**Tech Stack:** Python/FastAPI (backend pipeline + API), React/TypeScript (frontend state + UI), Claude API (scoring + rewriting)

**Spec:** `docs/superpowers/specs/2026-04-23-pre-script-hook-refinement-design.md`

---

## File Structure

**New files:**
- `backend/pipeline/hook_refiner.py` — `RefinedHook` model + `refine_hook()` function (Claude-powered rewriter)
- `frontend/src/components/script/HookRefinementResult.tsx` — Before/after text comparison component

**Modified files:**
- `backend/pipeline/hook_scorer.py` — Add `narration_text` parameter to `score_hook()`
- `backend/api/cold_opens.py` — Add `POST /refine-hook` and `GET /refine-hook-status/{job_id}` endpoints
- `frontend/src/types/script.ts` — Add `RefinedHookResult` type
- `frontend/src/api.ts` — Add `refineHook()` API function
- `frontend/src/components/script/useScriptGeneration.ts` — Add `"refining"` phase, refine polling, auto-proceed to script gen
- `frontend/src/components/script/ScriptGenerationPage.tsx` — Render refining phase UI
- `frontend/src/components/script/HookScoreCard.tsx` — Accept optional `score` prop to bypass auto-fetch

---

### Task 1: Adapt `score_hook()` to Accept Raw Narration Text

**Files:**
- Modify: `backend/pipeline/hook_scorer.py`

- [ ] **Step 1: Add `narration_text` parameter to `score_hook()`**

In `backend/pipeline/hook_scorer.py`, change the function signature and add a branch for narration text:

```python
def score_hook(
    intro_hook: str,
    hook_scenes: list[Scene],
    video_title: str,
    script_id: str | None = None,
    narration_text: str | None = None,
) -> HookScore:
    """Score the first ~30 seconds of a script for viewer retention."""
    if narration_text is not None:
        opening_content = f"Opening narration:\n{narration_text}"
    else:
        scene_texts = []
        for i, scene in enumerate(hook_scenes, 1):
            scene_texts.append(
                f"Scene {i} ({scene.duration_estimate_seconds:.0f}s):\n"
                f"  Narration: {scene.narration}\n"
                f"  Visual: {scene.visual_prompt}"
            )
        opening_content = (
            "Opening scenes (first ~30 seconds):\n\n"
            + "\n\n".join(scene_texts)
        )

    user_msg = (
        f"Video title: {video_title}\n\n"
        f"Intro hook text: \"{intro_hook}\"\n\n"
        + opening_content
    )

    logger.info("[%s] Scoring hook for %r (%d scenes, narration_text=%s)",
                script_id or "no-id", video_title, len(hook_scenes),
                "yes" if narration_text else "no")
    raw = chat(SYSTEM_PROMPT, user_msg, max_tokens=2048, script_id=script_id)
    text = strip_markdown_fences(raw)

    try:
        data = json.loads(text)
        result = HookScore.model_validate(data)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("[%s] Failed to parse hook score response: %s\nRaw: %s",
                     script_id or "no-id", exc, text[:500])
        raise RuntimeError(f"Hook scoring returned invalid JSON: {exc}") from exc

    logger.info("[%s] Hook score: overall=%d, promise=%d, tension=%d, payoff=%d",
                script_id or "no-id", result.overall, result.promise.score,
                result.tension.score, result.payoff_hint.score)
    return result
```

- [ ] **Step 2: Verify existing post-script scoring still works**

Run the backend to confirm the existing `POST /api/scripts/{script_id}/hook-score` endpoint still functions — it passes `hook_scenes` and no `narration_text`, so the else branch should be hit.

Run: `cd backend && uv run python -c "from pipeline.hook_scorer import score_hook; print('import OK')"`
Expected: `import OK`

- [ ] **Step 3: Commit**

```bash
git add backend/pipeline/hook_scorer.py
git commit -m "Add narration_text parameter to score_hook for pre-script scoring"
```

---

### Task 2: Create `refine_hook()` Pipeline Function

**Files:**
- Create: `backend/pipeline/hook_refiner.py`

- [ ] **Step 1: Create `backend/pipeline/hook_refiner.py`**

```python
"""Hook refiner — Claude rewrites intro_hook + opening_narration using retention score feedback."""

import json
import logging

from pydantic import BaseModel

from config import strip_markdown_fences
from integrations.claude_client import chat
from models.script import HookScore

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a YouTube hook specialist. You receive an intro hook and opening \
narration that have been scored on Promise, Tension, and Payoff Hint. Your \
job is to rewrite them to address the weaknesses identified in the score \
while preserving what already works well.

## Rules

- Keep the same core topic and angle — don't change what the video is about.
- Preserve elements that scored 80+ unless they conflict with improving weaker areas.
- Focus your changes on the lowest-scoring dimensions.
- The intro_hook should be 1-2 punchy sentences — the first words the viewer hears.
- The opening_narration should be 3-4 sentences for the first 2-3 content scenes.
- Write in the same tone and style as the original.
- Be concrete and specific, not vague or generic.

## Output format

Return ONLY valid JSON — no markdown fences, no commentary:

{
  "intro_hook": "<rewritten 1-2 sentence hook>",
  "opening_narration": "<rewritten 3-4 sentence opening narration>"
}
"""


class RefinedHook(BaseModel):
    intro_hook: str
    opening_narration: str


def refine_hook(
    intro_hook: str,
    opening_narration: str,
    hook_score: HookScore,
    video_title: str,
) -> RefinedHook:
    """Rewrite intro_hook + opening_narration to address retention score weaknesses."""
    suggestions_text = "\n".join(f"- {s}" for s in hook_score.suggestions)

    user_msg = (
        f"Video title: {video_title}\n\n"
        f"## Original Hook\n\n"
        f"Intro hook: \"{intro_hook}\"\n\n"
        f"Opening narration: \"{opening_narration}\"\n\n"
        f"## Retention Score\n\n"
        f"Promise: {hook_score.promise.score}/100 — {hook_score.promise.reasoning}\n"
        f"Tension: {hook_score.tension.score}/100 — {hook_score.tension.reasoning}\n"
        f"Payoff Hint: {hook_score.payoff_hint.score}/100 — {hook_score.payoff_hint.reasoning}\n"
        f"Overall: {hook_score.overall}/100\n\n"
        f"## Suggestions to Address\n\n"
        f"{suggestions_text}\n\n"
        f"Rewrite the intro_hook and opening_narration to address these weaknesses."
    )

    logger.info("Refining hook for %r (overall score: %d)", video_title, hook_score.overall)
    raw = chat(SYSTEM_PROMPT, user_msg, max_tokens=1024)
    text = strip_markdown_fences(raw)

    try:
        data = json.loads(text)
        result = RefinedHook.model_validate(data)
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("Failed to parse hook refine response: %s\nRaw: %s", exc, text[:500])
        raise RuntimeError(f"Hook refinement returned invalid JSON: {exc}") from exc

    logger.info("Hook refined for %r", video_title)
    return result
```

- [ ] **Step 2: Verify import**

Run: `cd backend && uv run python -c "from pipeline.hook_refiner import refine_hook, RefinedHook; print('import OK')"`
Expected: `import OK`

- [ ] **Step 3: Commit**

```bash
git add backend/pipeline/hook_refiner.py
git commit -m "Add hook refiner pipeline function for pre-script hook rewriting"
```

---

### Task 3: Add Refine-Hook API Endpoints

**Files:**
- Modify: `backend/api/cold_opens.py`

- [ ] **Step 1: Add request/response models and endpoints**

Add these imports at the top of `backend/api/cold_opens.py`:

```python
from pipeline.hook_refiner import refine_hook, RefinedHook
from pipeline.hook_scorer import score_hook
from models.script import HookScore
```

Add these models after the existing `ColdOpenJobResponse`:

```python
class RefineHookRequest(BaseModel):
    topic: str = Field(..., min_length=1)
    description: str = ""
    cold_open_index: int = Field(..., ge=0, le=2)
    cold_open_job_id: str = Field(..., min_length=1)


class RefineHookResultData(BaseModel):
    hook_score: dict
    refined_hook: dict
    original_hook: dict
```

Add endpoints after the existing `cold_opens_status` endpoint:

```python
@router.post("/refine-hook")
def refine_hook_endpoint(body: RefineHookRequest):
    cold_open_job = get_job(body.cold_open_job_id)
    if not cold_open_job or cold_open_job.status != "completed" or not cold_open_job.output_data:
        raise HTTPException(status_code=404, detail="Cold open job not found or not completed")

    cold_open_result = json.loads(cold_open_job.output_data)
    variants = cold_open_result.get("variants", [])
    if body.cold_open_index >= len(variants):
        raise HTTPException(status_code=422, detail="Invalid cold open index")

    variant = variants[body.cold_open_index]
    intro_hook = variant["intro_hook"]
    opening_narration = variant["opening_narration"]
    video_title = body.topic

    job = create_job()
    job_id = job.id

    def _run() -> list[str]:
        update_job(job_id, current_step="Scoring hook...")
        hook_score = score_hook(
            intro_hook=intro_hook,
            hook_scenes=[],
            video_title=video_title,
            narration_text=opening_narration,
        )

        update_job(job_id, current_step="Refining hook...", progress=0.5)
        refined = refine_hook(
            intro_hook=intro_hook,
            opening_narration=opening_narration,
            hook_score=hook_score,
            video_title=video_title,
        )

        result = RefineHookResultData(
            hook_score=hook_score.model_dump(),
            refined_hook=refined.model_dump(),
            original_hook={"intro_hook": intro_hook, "opening_narration": opening_narration},
        )
        update_job(job_id, output_data=result.model_dump_json())
        return []

    run_in_background(job_id, _run)
    return {"job_id": job_id}


@router.get("/refine-hook-status/{job_id}")
def refine_hook_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    result = job.to_dict()
    if job.status == "completed" and job.output_data:
        result["refine_result"] = json.loads(job.output_data)
    return result
```

- [ ] **Step 2: Verify endpoint registration**

Run: `cd backend && uv run python -c "from api.cold_opens import router; print([r.path for r in router.routes])"`
Expected: List includes `/refine-hook` and `/refine-hook-status/{job_id}`

- [ ] **Step 3: Commit**

```bash
git add backend/api/cold_opens.py
git commit -m "Add refine-hook API endpoints for pre-script hook scoring and rewriting"
```

---

### Task 4: Add Frontend Types and API Function

**Files:**
- Modify: `frontend/src/types/script.ts`
- Modify: `frontend/src/api.ts`

- [ ] **Step 1: Add `RefinedHookResult` type**

In `frontend/src/types/script.ts`, add after the existing `HookScore` interface:

```typescript
export interface RefinedHookResult {
  hook_score: HookScore;
  refined_hook: { intro_hook: string; opening_narration: string };
  original_hook: { intro_hook: string; opening_narration: string };
}
```

- [ ] **Step 2: Add `refineHook` API function**

In `frontend/src/api.ts`, add a new exported function (near the existing `scoreHook` function):

```typescript
export async function refineHook(body: {
  topic: string;
  description: string;
  cold_open_index: number;
  cold_open_job_id: string;
}): Promise<{ job_id: string }> {
  const res = await api.post("/api/scripts/refine-hook", body);
  if (!res.ok)
    throw new Error(
      (res.data as { detail?: string }).detail || "Hook refinement failed",
    );
  return res.data as { job_id: string };
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/types/script.ts frontend/src/api.ts
git commit -m "Add RefinedHookResult type and refineHook API function"
```

---

### Task 5: Add `"refining"` Phase to `useScriptGeneration`

**Files:**
- Modify: `frontend/src/components/script/useScriptGeneration.ts`

- [ ] **Step 1: Update type and add state variables**

Change the `GenerationPhase` type:

```typescript
export type GenerationPhase = "idle" | "cold_opens" | "selecting" | "refining" | "script";
```

Add to the `ScriptGenerationState` interface:

```typescript
  refineResult: RefinedHookResult | null;
```

Add import at the top:

```typescript
import { refineHook } from "../../api";
import type { ColdOpenResult, ColdOpenVariant, RefinedHookResult, ScriptContent } from "../../types/script";
```

Add state variable alongside the existing ones:

```typescript
const [refineResult, setRefineResult] = useState<RefinedHookResult | null>(null);
```

- [ ] **Step 2: Add refine-hook polling**

Add a third `usePollJob` instance after the existing cold open polling setup. Follow the same pattern as the cold open poller:

```typescript
interface RefineJobStatus {
  status: string;
  current_step: string;
  error: string | null;
  refine_result?: RefinedHookResult;
  elapsed_seconds?: number;
}

const { startPolling: startRefinePolling, stopPolling: stopRefinePolling } =
  usePollJob<RefineJobStatus>({
    pollFn: async (jobId) => {
      const res = await api.get(`/api/scripts/refine-hook-status/${jobId}`);
      return res.ok ? (res.data as RefineJobStatus) : null;
    },
    isComplete: (s) => s.status === "completed",
    isFailed: (s) => s.status === "failed",
    onStatus: (s) => {
      setElapsedSeconds(s.elapsed_seconds ?? null);
      if (s.status === "completed" && s.refine_result) {
        setRefineResult(s.refine_result);
        setLoading(false);
      } else if (s.status === "failed") {
        setError(s.error || "Hook refinement failed");
        setLoading(false);
        setPhase("idle");
      }
    },
    onConnectionLost: () => {
      setError("Lost connection to backend during hook refinement.");
      setLoading(false);
      setPhase("idle");
    },
    intervalMs: 1500,
  });
```

- [ ] **Step 3: Modify `handleColdOpenSelect` to trigger refinement instead of script gen**

Replace the body of `handleColdOpenSelect` so it triggers refinement first. The function needs to know the cold open job ID and the variant index. Add a `coldOpenJobId` ref to track it:

```typescript
const coldOpenJobIdRef = useRef<string | null>(null);
```

In `handleGenerate`, after `const { job_id } = res.data as { job_id: string };`, store it:

```typescript
coldOpenJobIdRef.current = job_id;
```

Then replace `handleColdOpenSelect`:

```typescript
const handleColdOpenSelect = async (variant: ColdOpenVariant) => {
  cancelledRef.current = false;
  setSelectedColdOpen(variant);
  setLoading(true);
  setError(null);
  setRefineResult(null);
  setElapsedSeconds(null);
  setPhase("refining");

  const variantIndex = coldOpenResult
    ? coldOpenResult.variants.findIndex((v) => v.id === variant.id)
    : 0;

  try {
    const { job_id } = await refineHook({
      topic: idea.title,
      description: idea.description,
      cold_open_index: variantIndex,
      cold_open_job_id: coldOpenJobIdRef.current!,
    });
    if (cancelledRef.current) return;
    startRefinePolling(job_id);
  } catch (err) {
    if (!cancelledRef.current) {
      console.error("[ScriptGeneration] Refine request failed:", err);
      setError("Could not reach the backend. Is it running?");
      setLoading(false);
      setPhase("idle");
    }
  }
};
```

- [ ] **Step 4: Add auto-proceed from refining to script generation**

Add a `useEffect` that watches for `refineResult` to be set and auto-triggers script generation after a 2-second delay:

```typescript
useEffect(() => {
  if (phase !== "refining" || !refineResult || !selectedColdOpen) return;

  const timer = setTimeout(() => {
    const refined = refineResult.refined_hook;
    const coldOpenText = `${refined.intro_hook}\n\n${refined.opening_narration}`;

    setPhase("script");
    setLoading(true);
    setElapsedSeconds(null);
    setGenSegments(null);
    setGenCompletedSegments([]);

    fetchGenerationEstimate("script_generation_youtube")
      .then((est) => setEstimatedSeconds(est.average_seconds))
      .catch(() => setEstimatedSeconds(null));

    api
      .post("/api/scripts/generate", {
        topic: idea.title,
        description: idea.description,
        brand_id: brandId,
        segment_count:
          idea.segments_est > 0 ? snapSegmentCount(idea.segments_est) : undefined,
        animated_scene_count: 5,
        model: selectedModel !== DEFAULT_MODEL ? selectedModel : undefined,
        segmented,
        cold_open_text: coldOpenText,
      })
      .then((res) => {
        if (cancelledRef.current) return;
        if (!res.ok) {
          const detail =
            res.data && typeof res.data === "object" && "detail" in res.data
              ? (res.data as { detail: string }).detail
              : "Failed to start script generation";
          setError(detail);
          setLoading(false);
          setPhase("idle");
          return;
        }
        const { job_id } = res.data as { job_id: string };
        startScriptPolling(job_id);
      })
      .catch((err) => {
        if (!cancelledRef.current) {
          console.error("[ScriptGeneration] Script request failed:", err);
          setError("Could not reach the backend. Is it running?");
          setLoading(false);
          setPhase("idle");
        }
      });
  }, 2000);

  return () => clearTimeout(timer);
}, [phase, refineResult, selectedColdOpen]);
```

- [ ] **Step 5: Add `refineResult` to the return object and `handleCancelGeneration`**

Add `refineResult` to the returned state object. Also update `handleCancelGeneration` to stop refine polling and reset refine state:

In `handleCancelGeneration`, add:

```typescript
stopRefinePolling();
setRefineResult(null);
```

In the return object, add:

```typescript
refineResult,
```

Update the `ScriptGenerationState` interface to include `refineResult: RefinedHookResult | null`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/script/useScriptGeneration.ts
git commit -m "Add refining phase to script generation state machine"
```

---

### Task 6: Update `HookScoreCard` to Accept Optional Score Prop

**Files:**
- Modify: `frontend/src/components/script/HookScoreCard.tsx`

- [ ] **Step 1: Add optional `score` prop**

Update the `Props` interface:

```typescript
interface Props {
  hookScore: HookScore | null;
  loading: boolean;
  error: string | null;
  onRescore: () => void;
  score?: HookScore | null;
}
```

At the top of the component function, resolve which score to display:

```typescript
export default function HookScoreCard({ hookScore, loading, error, onRescore, score }: Props) {
  const displayScore = score ?? hookScore;
```

Then replace all references to `hookScore` in the rendering logic with `displayScore`. The `loading`, `error`, and `onRescore` props should only apply when not using the `score` prop override.

When `score` is provided, skip the loading/error states — render the score directly:

```typescript
  if (score) {
    // Direct score display — skip loading/error states
    return (
      // ... same scored rendering as the existing scored state block,
      // but using `score` instead of `hookScore`, and hiding the Re-score button
    );
  }

  // ... existing loading/error/hookScore rendering unchanged
```

Hide the "Re-score" button when rendering via the `score` prop (the refining phase has no re-score action).

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/script/HookScoreCard.tsx
git commit -m "Add optional score prop to HookScoreCard for pre-script display"
```

---

### Task 7: Create `HookRefinementResult` Component

**Files:**
- Create: `frontend/src/components/script/HookRefinementResult.tsx`

- [ ] **Step 1: Create the component**

```typescript
import type { RefinedHookResult } from "../../types/script";

interface Props {
  result: RefinedHookResult;
}

export default function HookRefinementResult({ result }: Props) {
  return (
    <div className="space-y-4">
      <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4 space-y-3">
        <h4 className="text-xs font-medium uppercase tracking-wider text-neutral-500">
          Original
        </h4>
        <p className="text-sm text-neutral-500 italic leading-relaxed">
          &ldquo;{result.original_hook.intro_hook}&rdquo;
        </p>
        <p className="text-xs text-neutral-600 leading-relaxed">
          {result.original_hook.opening_narration}
        </p>
      </div>

      <div className="rounded-lg border border-violet-500/30 bg-violet-500/5 p-4 space-y-3">
        <h4 className="text-xs font-medium uppercase tracking-wider text-violet-400">
          Refined
        </h4>
        <p className="text-sm text-neutral-100 italic leading-relaxed">
          &ldquo;{result.refined_hook.intro_hook}&rdquo;
        </p>
        <p className="text-xs text-neutral-400 leading-relaxed">
          {result.refined_hook.opening_narration}
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/script/HookRefinementResult.tsx
git commit -m "Add HookRefinementResult before/after comparison component"
```

---

### Task 8: Render Refining Phase in `ScriptGenerationPage`

**Files:**
- Modify: `frontend/src/components/script/ScriptGenerationPage.tsx`

- [ ] **Step 1: Import new components and add `refineResult` to destructured state**

Add imports:

```typescript
import HookRefinementResult from "./HookRefinementResult";
```

Add `refineResult` to the destructured state from `useScriptGeneration`:

```typescript
const {
  // ... existing destructured props
  refineResult,
} = useScriptGeneration({ brandId, idea });
```

- [ ] **Step 2: Add refining phase render block**

In the rendering section, after the cold open selection block (`phase === "selecting"`) and before the script loading block, add a new conditional block:

```typescript
{/* Refining phase — scoring + rewriting hook */}
{phase === "refining" && (
  <div className="space-y-6">
    {loading && !refineResult && (
      <div className="flex flex-col items-center gap-4 py-12">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-violet-500 border-t-transparent" />
        <p className="text-sm text-neutral-400">Scoring and refining your hook...</p>
        {elapsedSeconds != null && (
          <p className="text-xs text-neutral-600">{Math.round(elapsedSeconds)}s elapsed</p>
        )}
      </div>
    )}

    {refineResult && (
      <div className="space-y-6 animate-in fade-in duration-500">
        <HookScoreCard
          hookScore={null}
          loading={false}
          error={null}
          onRescore={() => {}}
          score={refineResult.hook_score}
        />
        <HookRefinementResult result={refineResult} />
        <p className="text-center text-xs text-neutral-600">
          Continuing to script generation...
        </p>
      </div>
    )}
  </div>
)}
```

This renders:
1. A spinner while the refine job is running
2. Once complete: the score card + before/after comparison + "Continuing..." message
3. The `useEffect` in `useScriptGeneration` auto-proceeds to script gen after 2s

- [ ] **Step 3: Verify the loading block handles the refining phase**

The existing `{loading && ...}` block that shows "Generating cold open variants..." or "Generating script..." should NOT render during the refining phase (since the refining phase has its own loading UI above). Check that the existing loading block is gated to only show when `phase === "cold_opens" || phase === "script"`, not during `"refining"`. If it currently renders for all loading states, add a phase check:

The existing loading block condition should be updated from:

```typescript
{loading && ...}
```

To:

```typescript
{loading && (phase === "cold_opens" || phase === "script") && ...}
```

This ensures the refining phase's own UI handles its loading state.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/script/ScriptGenerationPage.tsx
git commit -m "Render refining phase UI in script generation page"
```

---

### Task 9: End-to-End Manual Test

**Files:** None (testing only)

- [ ] **Step 1: Start the dev server**

Run: `npm run dev`

- [ ] **Step 2: Test the full flow**

1. Create or select a video idea
2. Click "Generate Script" — cold opens should generate (3 variants)
3. Select a cold open variant
4. **NEW:** Should see "Scoring and refining your hook..." spinner
5. **NEW:** Should see HookScoreCard with scores + before/after comparison
6. **NEW:** After ~2s, should auto-proceed to "Generating script with Claude..."
7. Script should generate using the refined hook text
8. Post-script hook score should still auto-trigger on script load

- [ ] **Step 3: Test cancel during refining**

1. Start a new generation
2. Select a cold open
3. While "Scoring and refining your hook..." is showing, click Cancel
4. Should return to idle state cleanly

- [ ] **Step 4: Test error handling**

1. Stop the backend while refining is in progress
2. Should show "Lost connection to backend" error after ~7.5s (5 poll failures × 1.5s)
3. Should return to idle state

- [ ] **Step 5: Commit any fixes found during testing**

If any issues are found, fix and commit with descriptive message.
