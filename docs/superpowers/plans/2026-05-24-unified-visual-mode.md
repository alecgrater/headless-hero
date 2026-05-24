# Unified Visual Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `visual_mode` the canonical scene routing setting for video, full-frame, popup sequence, and flip-flop scenes.

**Architecture:** Add `Scene.visual_mode` with compatibility synchronization to existing `media_source` and `visual_treatment` fields. Update routing, generation, rendering, and UI to read/write the canonical field while preserving old JSON compatibility.

**Tech Stack:** Python 3.12, Pydantic/SQLModel, FastAPI pipeline modules, React 19, TypeScript, Tailwind 4, Remotion 4.

---

### Task 1: Scene Model And Compatibility

**Files:**
- Modify: `backend/models/script.py`
- Modify: `frontend/src/types/script.ts`
- Modify: `remotion/src/types.ts`
- Test: `backend/tests/test_visual_mode.py`

- [ ] Write failing tests for default mode, legacy `ai_video` derivation, legacy popup derivation, and invalid combinations normalizing to deterministic values.
- [ ] Add `VISUAL_MODES`, `VisualMode`, `Scene.visual_mode`, and model validation that synchronizes `visual_mode`, `media_source`, and `visual_treatment`.
- [ ] Add matching TypeScript union types.
- [ ] Run `uv run --project backend pytest backend/tests/test_visual_mode.py -q`.

### Task 2: Backend Routing

**Files:**
- Modify: `backend/pipeline/media_analyzer.py`
- Modify: `backend/pipeline/visual_treatments.py`
- Modify: `backend/api/visual_treatments.py`
- Test: `backend/tests/test_media_analysis_flags.py`
- Test: `backend/tests/test_visual_treatments.py`

- [ ] Write failing tests showing media assignments apply `visual_mode="video"` and treatment assignments preserve video scenes.
- [ ] Extend assignment models with `visual_mode`.
- [ ] Ensure apply functions call the shared scene synchronization path.
- [ ] Run targeted backend tests for media analysis and visual treatments.

### Task 3: Asset Generation And Render Input

**Files:**
- Modify: `backend/pipeline/image_gen.py`
- Modify: `backend/pipeline/test_lab.py`
- Modify: `backend/pipeline/remotion_render.py`
- Test: `backend/tests/test_media_source_dispatch.py`
- Test: `backend/tests/test_test_lab.py`
- Test: `backend/tests/pipeline/test_remotion_render.py`

- [ ] Write failing tests for generation dispatch by `visual_mode`.
- [ ] Update video/full-frame/layered branches to key off `visual_mode`.
- [ ] Include `visual_mode` in Remotion scene props.
- [ ] Run targeted backend tests.

### Task 4: Unified UI Controls

**Files:**
- Modify: `frontend/src/components/timeline/PropertiesPanel.tsx`
- Modify: `frontend/src/components/test-lab/TestLabControls.tsx`
- Modify: `frontend/src/types/testLab.ts`
- Search and update related timeline panels that display separate media/treatment labels.

- [ ] Replace separate scene media source and animation type controls with one visual mode selector.
- [ ] Keep helper text and disabled states tied to mode-specific stages.
- [ ] Run `npm run test:frontend -- --run` or the closest project-supported frontend test command.

### Task 5: Documentation, Verification, Commit, Review Loop

**Files:**
- Modify: `AGENTS.md`
- Modify: design and plan docs from this change.

- [ ] Update project conventions to make `visual_mode` canonical.
- [ ] Run backend and frontend targeted tests.
- [ ] Stage, commit, and push to `main`.
- [ ] Dispatch delegated review of the most recent commit.
- [ ] Apply all required review findings, commit fixes, push, and repeat review until LGTM.
