# Smart Media Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the upfront game-name input with a post-script Claude-powered media analyzer that automatically identifies games, real-world subjects, and abstract concepts per scene and assigns optimal media sources.

**Architecture:** New `media_analyzer.py` pipeline module calls Claude to analyze a completed script and return per-scene media source assignments. A new API endpoint triggers this as a background job after script generation. The frontend shows a MediaReviewPanel for approval before image generation. The existing scriptwriter prompt injection and game-name input are removed.

**Tech Stack:** Python/FastAPI (backend pipeline + API), Claude API via `claude_client.py`, React/TypeScript (frontend review panel), existing `render_jobs.py` background job infrastructure, existing `usePollJob` hook.

**Spec:** `docs/superpowers/specs/2026-04-26-smart-media-routing-design.md`

---

### Task 1: Add `original_visual_prompt` to Scene model and frontend types

**Files:**
- Modify: `backend/models/script.py:114` (Scene class, add field after `upload_url`)
- Modify: `frontend/src/types/script.ts` (Scene interface, add field)

- [ ] **Step 1: Add `original_visual_prompt` to Scene model**

In `backend/models/script.py`, add after the `upload_url` field (line 114):

```python
    original_visual_prompt: str = ""    # preserved AI-art prompt when analyzer overwrites visual_prompt
```

- [ ] **Step 2: Add `original_visual_prompt` to frontend Scene interface**

In `frontend/src/types/script.ts`, add to the Scene interface after `upload_url`:

```typescript
    original_visual_prompt?: string;
```

- [ ] **Step 3: Commit**

```bash
git add backend/models/script.py frontend/src/types/script.ts
git commit -m "Add original_visual_prompt field to Scene model"
```

---

### Task 2: Register MEDIA_ANALYZER prompt in prompts.py

**Files:**
- Modify: `backend/prompts.py` (add new prompt definition at end of file, in a new MEDIA domain section)

- [ ] **Step 1: Add MEDIA_ANALYZER_SYSTEM prompt**

Add at the end of `backend/prompts.py`, before any final newline:

```python
# ===================================================================
# MEDIA — media source routing
# ===================================================================

MEDIA_ANALYZER_SYSTEM = register(PromptDef(
    name="MEDIA_ANALYZER_SYSTEM",
    domain="MEDIA",
    purpose="Analyze script content and assign optimal media sources per scene",
    template="""You are a media routing specialist for video production. You analyze video scripts and decide which visual source is best for each scene.

For each scene, assign one of these media sources:
{available_sources}

Guidelines:
- "gameplay_video": Use when a SPECIFIC, NAMED video game is being discussed, demonstrated, or referenced. Extract the most precise game title possible (e.g. "Grand Theft Auto III" not "GTA games", "Halo: Combat Evolved" not "Halo"). Only use this when you can name the exact game — general gaming discussions should use "ai".
- "stock_photo": Use when real-world objects, events, places, people, products, or historical moments are discussed. Generate an optimized Pexels search query: specific, descriptive, landscape-oriented (e.g. "PlayStation 2 console product photo black background" not "PS2").
- "ai": Default. Use for abstract concepts, metaphors, stylized illustrations, diagrams, or any scene that benefits from custom AI imagery. Also use for title card scenes (is_title_card=true) — these must ALWAYS be "ai".

Return a JSON array with one entry per scene:
[
  {
    "scene_id": "scene_1",
    "media_source": "ai" | "gameplay_video" | "stock_photo",
    "game_name": "Exact Game Title" or null,
    "search_query": "optimized pexels search query" or null,
    "reasoning": "Brief explanation of why this source was chosen"
  }
]

Rules:
- Every scene in the input must appear exactly once in the output
- Title card scenes (is_title_card=true) MUST always be "ai"
- Only assign sources from the available list above
- game_name must be null unless media_source is "gameplay_video"
- search_query must be null unless media_source is "stock_photo"
- Return ONLY the JSON array, no other text""",
    inputs=["script_content_json", "available_sources"],
    expected_output_format="JSON array of MediaAssignment objects",
    target_model="claude",
))
```

- [ ] **Step 2: Commit**

```bash
git add backend/prompts.py
git commit -m "Add MEDIA_ANALYZER_SYSTEM prompt for post-script media routing"
```

---

### Task 3: Create media analyzer pipeline module

**Files:**
- Create: `backend/pipeline/media_analyzer.py`

- [ ] **Step 1: Create `backend/pipeline/media_analyzer.py`**

```python
"""Post-script media analyzer — uses Claude to assign optimal media sources per scene."""

import json
import logging
from dataclasses import dataclass

from config import strip_markdown_fences
from integrations.claude_client import chat
from models.script import ScriptContent
from prompts import MEDIA_ANALYZER_SYSTEM

logger = logging.getLogger(__name__)


@dataclass
class MediaAssignment:
    scene_id: str
    media_source: str
    game_name: str | None
    search_query: str | None
    reasoning: str


def analyze_media_sources(
    script_content: ScriptContent,
    gameplay_enabled: bool = True,
    stock_photo_enabled: bool = True,
    script_id: str | None = None,
) -> list[MediaAssignment]:
    """Analyze a completed script and assign media sources per scene.

    Sends the full script to Claude, which returns per-scene assignments
    based on the narrative content.
    """
    sources = ['"ai"']
    if gameplay_enabled:
        sources.append('"gameplay_video"')
    if stock_photo_enabled:
        sources.append('"stock_photo"')
    available_sources = ", ".join(sources)

    system_prompt = MEDIA_ANALYZER_SYSTEM.template.replace("{available_sources}", available_sources)

    scenes_summary = []
    for seg in script_content.segments:
        for scene in seg.scenes:
            scenes_summary.append({
                "scene_id": scene.id,
                "segment": seg.name,
                "narration": scene.narration,
                "visual_prompt": scene.visual_prompt,
                "is_title_card": scene.is_title_card,
            })

    user_message = json.dumps(scenes_summary, indent=2)

    logger.info("[%s] Analyzing media sources for %d scenes (gameplay=%s, stock=%s)",
                script_id or "no-id", len(scenes_summary), gameplay_enabled, stock_photo_enabled)

    response = chat(
        system=system_prompt,
        user_message=user_message,
        max_tokens=4096,
        script_id=script_id,
    )

    cleaned = strip_markdown_fences(response)
    raw_assignments = json.loads(cleaned)

    if not isinstance(raw_assignments, list):
        raise ValueError("Expected JSON array from media analyzer")

    valid_sources = {"ai", "gameplay_video", "stock_photo"}
    assignments = []
    for entry in raw_assignments:
        source = entry.get("media_source", "ai")
        if source not in valid_sources:
            source = "ai"
        if not gameplay_enabled and source == "gameplay_video":
            source = "ai"
        if not stock_photo_enabled and source == "stock_photo":
            source = "ai"

        assignments.append(MediaAssignment(
            scene_id=entry["scene_id"],
            media_source=source,
            game_name=entry.get("game_name"),
            search_query=entry.get("search_query"),
            reasoning=entry.get("reasoning", ""),
        ))

    logger.info("[%s] Media analysis complete: %d ai, %d gameplay, %d stock",
                script_id or "no-id",
                sum(1 for a in assignments if a.media_source == "ai"),
                sum(1 for a in assignments if a.media_source == "gameplay_video"),
                sum(1 for a in assignments if a.media_source == "stock_photo"))

    return assignments


def apply_assignments(
    script_content: ScriptContent,
    assignments: list[MediaAssignment],
) -> None:
    """Patch scene fields in-place based on media assignments."""
    assignment_map = {a.scene_id: a for a in assignments}

    for seg in script_content.segments:
        for scene in seg.scenes:
            assignment = assignment_map.get(scene.id)
            if not assignment:
                continue

            scene.media_source = assignment.media_source

            if assignment.media_source == "gameplay_video" and assignment.game_name:
                scene.gameplay_game_override = assignment.game_name

            if assignment.media_source == "stock_photo" and assignment.search_query:
                scene.original_visual_prompt = scene.visual_prompt
                scene.visual_prompt = assignment.search_query
```

- [ ] **Step 2: Verify the module imports cleanly**

Run: `cd backend && uv run python -c "from pipeline.media_analyzer import analyze_media_sources, apply_assignments, MediaAssignment; print('OK')"`

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/pipeline/media_analyzer.py
git commit -m "Add Claude-powered media analyzer pipeline module"
```

---

### Task 4: Add media analysis API endpoints

**Files:**
- Modify: `backend/api/media.py` (add analyze, apply, and status endpoints)

- [ ] **Step 1: Add analysis endpoints to `backend/api/media.py`**

Add the following imports and endpoints after the existing `upload_scene_media` endpoint:

```python
import json
import time

from sqlmodel import Session

from database import get_session
from models.script import Script, ScriptContent
from pipeline.media_analyzer import analyze_media_sources, apply_assignments, MediaAssignment
from pipeline.render_jobs import create_job, get_job, run_in_background, update_job


class MediaAssignmentResponse(BaseModel):
    scene_id: str
    media_source: str
    game_name: str | None = None
    search_query: str | None = None
    reasoning: str = ""


class AnalyzeResponse(BaseModel):
    job_id: str


class AnalyzeResultResponse(BaseModel):
    assignments: list[MediaAssignmentResponse]
    summary: dict[str, int]


class ApplyRequest(BaseModel):
    assignments: list[MediaAssignmentResponse]


class ApplyResponse(BaseModel):
    ok: bool


@router.post("/analyze/{script_id}", response_model=AnalyzeResponse)
def analyze_media(script_id: str, session: Session = Depends(get_session)):
    """Trigger media source analysis for a script. Runs as a background job."""
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))

    gameplay_enabled = content.gameplay_enabled
    stock_photo_enabled = content.stock_photo_enabled

    if not gameplay_enabled and not stock_photo_enabled:
        raise HTTPException(status_code=400, detail="No media sources enabled")

    job = create_job()
    job_id = job.id

    def _run_analysis() -> list[str]:
        update_job(job_id, current_step="Analyzing script for media sources...")
        assignments = analyze_media_sources(
            content,
            gameplay_enabled=gameplay_enabled,
            stock_photo_enabled=stock_photo_enabled,
            script_id=script_id,
        )

        apply_assignments(content, assignments)

        from database import engine
        from sqlmodel import Session as SqlSession
        with SqlSession(engine) as bg_session:
            rec = bg_session.get(Script, script_id)
            if rec:
                rec.script_json = content.model_dump_json()
                bg_session.add(rec)
                bg_session.commit()

        result_data = json.dumps([{
            "scene_id": a.scene_id,
            "media_source": a.media_source,
            "game_name": a.game_name,
            "search_query": a.search_query,
            "reasoning": a.reasoning,
        } for a in assignments])

        update_job(job_id, output_data=result_data)
        return [script_id]

    run_in_background(job_id, _run_analysis)
    return AnalyzeResponse(job_id=job_id)


@router.get("/analyze/status/{job_id}")
def analyze_status(job_id: str):
    """Poll the status of a media analysis job."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    result = job.to_dict()
    if job.status == "completed" and job.output_data:
        raw = json.loads(job.output_data)
        summary: dict[str, int] = {}
        for a in raw:
            src = a["media_source"]
            summary[src] = summary.get(src, 0) + 1
        result["assignments"] = raw
        result["summary"] = summary
    return result


@router.post("/apply/{script_id}", response_model=ApplyResponse)
def apply_media(body: ApplyRequest, script_id: str, session: Session = Depends(get_session)):
    """Apply user-edited media assignments to the script."""
    record = session.get(Script, script_id)
    if not record:
        raise HTTPException(status_code=404, detail="Script not found")

    content = ScriptContent.model_validate(json.loads(record.script_json))

    assignments = [
        MediaAssignment(
            scene_id=a.scene_id,
            media_source=a.media_source,
            game_name=a.game_name,
            search_query=a.search_query,
            reasoning=a.reasoning,
        )
        for a in body.assignments
    ]

    apply_assignments(content, assignments)

    record.script_json = content.model_dump_json()
    session.add(record)
    session.commit()

    logger.info("Applied %d media assignments to script %s", len(assignments), script_id)
    return ApplyResponse(ok=True)
```

- [ ] **Step 2: Verify the endpoints load**

Run: `cd backend && uv run python -c "from api.media import router; print(f'{len(router.routes)} routes loaded')"`

Expected: `4 routes loaded` (upload + analyze + status + apply)

- [ ] **Step 3: Commit**

```bash
git add backend/api/media.py
git commit -m "Add media analysis API endpoints (analyze, status, apply)"
```

---

### Task 5: Remove scriptwriter prompt injection and game-name field

**Files:**
- Modify: `backend/pipeline/scriptwriter.py:93-106` (remove `gameplay_game_name` parameter), `148-179` (remove prompt injection block)
- Modify: `backend/models/script.py:178` (remove `gameplay_game_name` from `GenerateScriptRequest`)
- Modify: `backend/api/scripts.py:184,211` (remove `gameplay_game_name` references)

- [ ] **Step 1: Remove `gameplay_game_name` parameter from `generate_script()`**

In `backend/pipeline/scriptwriter.py`, change the function signature (lines 93-106) to remove `gameplay_game_name`:

Replace:
```python
def generate_script(
    topic: str,
    description: str = "",
    brand_context: str = "",
    animated_scene_count: int = 5,
    brand: dict | None = None,
    model: str | None = None,
    segmented: bool = False,
    cold_open_text: str | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
    gameplay_enabled: bool = False,
    stock_photo_enabled: bool = False,
    gameplay_game_name: str = "",
) -> ScriptContent:
```

With:
```python
def generate_script(
    topic: str,
    description: str = "",
    brand_context: str = "",
    animated_scene_count: int = 5,
    brand: dict | None = None,
    model: str | None = None,
    segmented: bool = False,
    cold_open_text: str | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
    gameplay_enabled: bool = False,
    stock_photo_enabled: bool = False,
) -> ScriptContent:
```

- [ ] **Step 2: Remove the media source prompt injection block**

In `backend/pipeline/scriptwriter.py`, delete lines 148-179 (the entire `if gameplay_enabled or stock_photo_enabled:` block that builds `media_parts` and appends to `user_parts`).

- [ ] **Step 3: Remove `gameplay_game_name` from `GenerateScriptRequest`**

In `backend/models/script.py`, remove the line (around line 178):
```python
    gameplay_game_name: str = PydanticField(default="", description="Default game name for gameplay clips")
```

- [ ] **Step 4: Remove `gameplay_game_name` from scripts API endpoint**

In `backend/api/scripts.py`, remove the line that captures `gameplay_game_name` (around line 184):
```python
    gameplay_game_name = body.gameplay_game_name
```

And remove `gameplay_game_name=gameplay_game_name` from the `generate_script()` call (around line 211).

- [ ] **Step 5: Verify backend starts without errors**

Run: `cd backend && uv run python -c "from api import app; print('OK')"`

Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add backend/pipeline/scriptwriter.py backend/models/script.py backend/api/scripts.py
git commit -m "Remove game-name input and scriptwriter media source prompt injection"
```

---

### Task 6: Auto-trigger media analyzer after script generation

**Files:**
- Modify: `backend/api/scripts.py` (add analyzer trigger inside `_run_generation`)

- [ ] **Step 1: Add media analyzer trigger after script generation**

In `backend/api/scripts.py`, inside the `_run_generation()` function (around line 250, after the hook scoring block), add:

```python
        # Auto-trigger media analyzer if media sources are enabled
        media_analysis_job_id = None
        if gameplay_enabled or stock_photo_enabled:
            try:
                update_job(job_id, current_step="Analyzing media sources...")
                from pipeline.media_analyzer import analyze_media_sources, apply_assignments
                assignments = analyze_media_sources(
                    script_content,
                    gameplay_enabled=gameplay_enabled,
                    stock_photo_enabled=stock_photo_enabled,
                    script_id=script_id,
                )
                apply_assignments(script_content, assignments)
                with SqlSession(engine) as bg_session3:
                    record3 = bg_session3.get(Script, script_id)
                    if record3:
                        record3.script_json = script_content.model_dump_json()
                        bg_session3.add(record3)
                    bg_session3.commit()
                logger.info("Media analysis complete for %s: %d assignments",
                            script_id, len(assignments))
            except Exception:
                logger.exception("Media analysis failed for %s — script saved without assignments", script_id)
```

This runs synchronously within the background script generation job (same pattern as hook scoring). No separate background job needed — it piggybacks on the existing script gen thread.

- [ ] **Step 2: Commit**

```bash
git add backend/api/scripts.py
git commit -m "Auto-trigger media analyzer after script generation"
```

---

### Task 7: Simplify script generation page — remove game name input

**Files:**
- Modify: `frontend/src/components/script/ScriptGenerationPage.tsx:218-229` (remove game name input)
- Modify: `frontend/src/components/script/useScriptGeneration.ts` (remove gameplayGameName state and API param)

- [ ] **Step 1: Remove `gameplayGameName` state from `useScriptGeneration.ts`**

In `frontend/src/components/script/useScriptGeneration.ts`:

Remove the state declaration (around line 109):
```typescript
  const [gameplayGameName, setGameplayGameName] = useState("");
```

Remove `gameplay_game_name` from the API call (around line 397):
```typescript
        gameplay_game_name: gameplayGameName || undefined,
```

Remove `gameplayGameName` and `setGameplayGameName` from the hook's return object.

- [ ] **Step 2: Remove game name input from `ScriptGenerationPage.tsx`**

In `frontend/src/components/script/ScriptGenerationPage.tsx`, remove the game name input block (lines 218-229):

```tsx
                    {gameplayEnabled && (
                      <div className="pl-7">
                        <label className="block text-xs text-neutral-500 mb-1">Game name</label>
                        <input
                          type="text"
                          value={gameplayGameName}
                          onChange={(e) => setGameplayGameName(e.target.value)}
                          placeholder="e.g. Minecraft, Fortnite"
                          className="w-64 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-sm text-neutral-200 placeholder-neutral-600 focus:outline-none focus:border-violet-500 transition-colors"
                        />
                      </div>
                    )}
```

Remove `gameplayGameName` and `setGameplayGameName` from the destructured hook return.

- [ ] **Step 3: Verify frontend compiles**

Run: `cd frontend && npx tsc --noEmit`

Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/script/ScriptGenerationPage.tsx frontend/src/components/script/useScriptGeneration.ts
git commit -m "Remove game name input from script generation page"
```

---

### Task 8: Add API client functions for media analysis

**Files:**
- Modify: `frontend/src/api.ts` (add analyzeMedia, getMediaAnalysisStatus, applyMediaAssignments functions)

- [ ] **Step 1: Add media analysis API functions**

Add at the end of `frontend/src/api.ts`, before the final export (or alongside other helper functions like `generateFX`):

```typescript
export interface MediaAssignment {
  scene_id: string;
  media_source: "ai" | "gameplay_video" | "stock_photo";
  game_name: string | null;
  search_query: string | null;
  reasoning: string;
}

export interface MediaAnalysisStatus {
  status: string;
  progress: number;
  error: string | null;
  assignments?: MediaAssignment[];
  summary?: Record<string, number>;
}

export async function analyzeMedia(scriptId: string) {
  return api.post<{ job_id: string }>(`/api/media/analyze/${scriptId}`);
}

export async function getMediaAnalysisStatus(jobId: string) {
  return api.get<MediaAnalysisStatus>(`/api/media/analyze/status/${jobId}`);
}

export async function applyMediaAssignments(
  scriptId: string,
  assignments: MediaAssignment[],
) {
  return api.post<{ ok: boolean }>(`/api/media/apply/${scriptId}`, { assignments });
}
```

- [ ] **Step 2: Verify frontend compiles**

Run: `cd frontend && npx tsc --noEmit`

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api.ts
git commit -m "Add media analysis API client functions"
```

---

### Task 9: Create MediaReviewPanel component

**Files:**
- Create: `frontend/src/components/timeline/MediaReviewPanel.tsx`

- [ ] **Step 1: Create `frontend/src/components/timeline/MediaReviewPanel.tsx`**

```tsx
import { useState } from "react";
import type { MediaAssignment } from "../../api";
import { applyMediaAssignments, analyzeMedia, getMediaAnalysisStatus } from "../../api";
import { usePollJob } from "../../hooks/usePollJob";
import type { MediaAnalysisStatus } from "../../api";

interface Props {
  scriptId: string;
  assignments: MediaAssignment[];
  onApproved: () => void;
  onReanalyze: () => void;
}

const SOURCE_LABELS: Record<string, { label: string; color: string }> = {
  ai: { label: "AI", color: "bg-violet-500/20 text-violet-300" },
  gameplay_video: { label: "Gameplay", color: "bg-emerald-500/20 text-emerald-300" },
  stock_photo: { label: "Stock Photo", color: "bg-sky-500/20 text-sky-300" },
};

export default function MediaReviewPanel({ scriptId, assignments: initial, onApproved, onReanalyze }: Props) {
  const [assignments, setAssignments] = useState<MediaAssignment[]>(initial);
  const [applying, setApplying] = useState(false);

  const summary = assignments.reduce<Record<string, number>>((acc, a) => {
    acc[a.media_source] = (acc[a.media_source] || 0) + 1;
    return acc;
  }, {});

  const totalScenes = assignments.length;

  const handleSourceChange = (sceneId: string, newSource: "ai" | "gameplay_video" | "stock_photo") => {
    setAssignments((prev) =>
      prev.map((a) =>
        a.scene_id === sceneId
          ? { ...a, media_source: newSource, game_name: newSource === "gameplay_video" ? a.game_name : null, search_query: newSource === "stock_photo" ? a.search_query : null }
          : a,
      ),
    );
  };

  const handleFieldChange = (sceneId: string, field: "game_name" | "search_query", value: string) => {
    setAssignments((prev) =>
      prev.map((a) => (a.scene_id === sceneId ? { ...a, [field]: value || null } : a)),
    );
  };

  const handleApprove = async () => {
    setApplying(true);
    const res = await applyMediaAssignments(scriptId, assignments);
    setApplying(false);
    if (res.ok) {
      onApproved();
    }
  };

  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-neutral-800 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-neutral-200">Media Source Review</h3>
          <p className="text-xs text-neutral-500 mt-0.5">
            {totalScenes} scenes: {Object.entries(summary).map(([src, count]) => `${count} ${SOURCE_LABELS[src]?.label ?? src}`).join(", ")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onReanalyze}
            className="px-3 py-1.5 text-xs bg-neutral-800 hover:bg-neutral-700 rounded-lg transition-colors text-neutral-300"
          >
            Re-analyze
          </button>
          <button
            onClick={handleApprove}
            disabled={applying}
            className="px-3 py-1.5 text-xs bg-violet-600 hover:bg-violet-500 disabled:opacity-50 rounded-lg transition-colors text-white font-medium"
          >
            {applying ? "Applying..." : "Approve & Generate Images"}
          </button>
        </div>
      </div>

      {/* Scene list */}
      <div className="divide-y divide-neutral-800 max-h-96 overflow-y-auto">
        {assignments.map((a, idx) => {
          const sourceInfo = SOURCE_LABELS[a.media_source] ?? { label: a.media_source, color: "bg-neutral-700 text-neutral-300" };
          return (
            <div key={a.scene_id} className="px-4 py-2.5 flex items-center gap-3 text-sm">
              <span className="text-neutral-500 w-6 text-right shrink-0">{idx + 1}</span>
              <select
                value={a.media_source}
                onChange={(e) => handleSourceChange(a.scene_id, e.target.value as "ai" | "gameplay_video" | "stock_photo")}
                className="bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200 shrink-0"
              >
                <option value="ai">AI</option>
                <option value="gameplay_video">Gameplay</option>
                <option value="stock_photo">Stock Photo</option>
              </select>
              <span className={`px-2 py-0.5 rounded text-xs font-medium shrink-0 ${sourceInfo.color}`}>
                {sourceInfo.label}
              </span>
              {a.media_source === "gameplay_video" && (
                <input
                  type="text"
                  value={a.game_name ?? ""}
                  onChange={(e) => handleFieldChange(a.scene_id, "game_name", e.target.value)}
                  placeholder="Game name"
                  className="bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200 placeholder-neutral-600 w-40"
                />
              )}
              {a.media_source === "stock_photo" && (
                <input
                  type="text"
                  value={a.search_query ?? ""}
                  onChange={(e) => handleFieldChange(a.scene_id, "search_query", e.target.value)}
                  placeholder="Search query"
                  className="bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200 placeholder-neutral-600 w-48"
                />
              )}
              <span className="text-neutral-500 text-xs truncate flex-1" title={a.reasoning}>
                {a.reasoning}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify frontend compiles**

Run: `cd frontend && npx tsc --noEmit`

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/timeline/MediaReviewPanel.tsx
git commit -m "Add MediaReviewPanel component for reviewing media source assignments"
```

---

### Task 10: Integrate MediaReviewPanel into TimelinePage

**Files:**
- Modify: `frontend/src/components/timeline/TimelinePage.tsx` (add state, polling, and conditional render in `TimelineEditor`)

- [ ] **Step 1: Add imports to TimelinePage.tsx**

At the top of `TimelinePage.tsx`, add:

```typescript
import MediaReviewPanel from "./MediaReviewPanel";
import { analyzeMedia, getMediaAnalysisStatus } from "../../api";
import type { MediaAssignment, MediaAnalysisStatus } from "../../api";
import { usePollJob } from "../../hooks/usePollJob";
```

- [ ] **Step 2: Add media review state to TimelineEditor**

Inside the `TimelineEditor` component (around line 190, after existing state declarations), add:

```typescript
  const [mediaAssignments, setMediaAssignments] = useState<MediaAssignment[] | null>(null);
  const [mediaReviewDismissed, setMediaReviewDismissed] = useState(false);
  const [mediaAnalyzing, setMediaAnalyzing] = useState(false);
```

- [ ] **Step 3: Add re-analyze handler**

After the state declarations, add:

```typescript
  const handleAnalyzeMedia = useCallback(async () => {
    setMediaAnalyzing(true);
    setMediaAssignments(null);
    setMediaReviewDismissed(false);
    const res = await analyzeMedia(scriptId);
    if (!res.ok) {
      setMediaAnalyzing(false);
      return;
    }
    const jobId = (res.data as { job_id: string }).job_id;
    const poll = setInterval(async () => {
      const statusRes = await getMediaAnalysisStatus(jobId);
      if (!statusRes.ok) return;
      const status = statusRes.data as MediaAnalysisStatus;
      if (status.status === "completed" && status.assignments) {
        clearInterval(poll);
        setMediaAssignments(status.assignments as MediaAssignment[]);
        setMediaAnalyzing(false);
      } else if (status.status === "failed") {
        clearInterval(poll);
        setMediaAnalyzing(false);
      }
    }, 1000);
  }, [scriptId]);
```

- [ ] **Step 4: Check for existing assignments on mount**

Add an effect to detect if media analysis has already been run (scenes have non-"ai" media_source):

```typescript
  useEffect(() => {
    const content = state.content;
    if (!content.gameplay_enabled && !content.stock_photo_enabled) return;

    const allScenes = content.segments.flatMap((s) => s.scenes);
    const hasNonAi = allScenes.some((s) => s.media_source && s.media_source !== "ai");

    if (hasNonAi && !mediaReviewDismissed) {
      const existing: MediaAssignment[] = allScenes.map((s) => ({
        scene_id: s.id,
        media_source: (s.media_source ?? "ai") as "ai" | "gameplay_video" | "stock_photo",
        game_name: s.gameplay_game_override || null,
        search_query: s.media_source === "stock_photo" ? s.visual_prompt : null,
        reasoning: "",
      }));
      setMediaAssignments(existing);
    }
  }, []);
```

- [ ] **Step 5: Render MediaReviewPanel conditionally**

In the TimelineEditor's JSX, add the MediaReviewPanel above the timeline lanes (before the `<TimelineLanes>` component). Find the appropriate location in the return JSX and add:

```tsx
        {/* Media Review Panel */}
        {mediaAnalyzing && (
          <div className="px-4 py-3 bg-violet-500/10 border-b border-neutral-800 flex items-center gap-3">
            <span className="w-4 h-4 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-sm text-neutral-300">Analyzing media sources...</span>
          </div>
        )}
        {mediaAssignments && !mediaReviewDismissed && !mediaAnalyzing && (
          <div className="p-4">
            <MediaReviewPanel
              scriptId={scriptId}
              assignments={mediaAssignments}
              onApproved={() => {
                setMediaReviewDismissed(true);
                state.handleGenerateAllImages();
              }}
              onReanalyze={handleAnalyzeMedia}
            />
          </div>
        )}
```

- [ ] **Step 6: Verify frontend compiles**

Run: `cd frontend && npx tsc --noEmit`

Expected: No errors

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/timeline/TimelinePage.tsx
git commit -m "Integrate MediaReviewPanel into timeline page"
```

---

### Task 11: Manual integration testing

**Files:** None (testing only)

- [ ] **Step 1: Start the dev server**

Run: `npm run dev`

- [ ] **Step 2: Test AI-only mode (no media sources)**

1. Navigate to an idea → Script Generation page
2. Verify the game name input is gone
3. Leave both toggles unchecked
4. Generate a script
5. Open the timeline → verify no MediaReviewPanel appears
6. Verify images can be generated normally

- [ ] **Step 3: Test with media sources enabled**

1. Ensure Twitch and/or Pexels API keys are configured in Settings
2. Navigate to an idea about a specific topic (e.g., gaming)
3. Check "Gameplay clips" and/or "Stock photos" checkboxes
4. Generate a script
5. Open the timeline → verify MediaReviewPanel appears with assignments
6. Verify each scene has a media source badge, reasoning, and editable fields
7. Change a scene's source from AI to Gameplay → enter a game name
8. Click "Approve & Generate Images" → verify image generation starts
9. Verify gameplay scenes attempt to fetch from Twitch, stock scenes from Pexels

- [ ] **Step 4: Test re-analyze**

1. In the MediaReviewPanel, click "Re-analyze"
2. Verify the loading spinner appears
3. Verify new assignments replace the old ones

- [ ] **Step 5: Test backward compatibility**

1. Open an existing script that was generated with the old game-name flow
2. Verify the timeline loads without errors
3. Verify existing media source assignments are preserved

- [ ] **Step 6: Commit any fixes**

If any fixes were needed during testing, commit them:

```bash
git add -A
git commit -m "Fix issues found during media routing integration testing"
```
