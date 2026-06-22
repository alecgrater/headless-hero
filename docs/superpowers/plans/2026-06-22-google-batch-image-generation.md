# Google Batch Image Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an opt-in Google Batch API path for timeline Generate All Images while keeping `gemini-2.5-flash-image` as the default model and preserving standard generation as the default behavior.

**Architecture:** Add a persisted `GOOGLE_IMAGE_BATCH_ENABLED` setting, a backend visual-generation background job, and a Google Batch helper that handles safe independent Gemini image requests. The timeline will send full-project image payloads to the job endpoint and poll status; single-scene regeneration remains immediate.

**Tech Stack:** FastAPI, SQLModel settings, Google GenAI Python SDK, React 19/Vite/TypeScript, Vitest, pytest via `uv run --project backend pytest`.

---

### Task 1: Settings Toggle

**Files:**
- Modify: `backend/api/settings.py`
- Modify: `frontend/src/components/settings/GeneralSection.tsx`
- Test: `frontend/src/components/settings/GeneralSection.test.tsx`

- [ ] **Step 1: Write failing tests**

Add a frontend test that mocks `/api/settings/keys` with `GOOGLE_IMAGE_BATCH_ENABLED: { masked: "true" }`, renders `GeneralSection` with `panel="visuals"`, and asserts the toggle appears checked with the label "Google Batch for Generate All".

- [ ] **Step 2: Verify the test fails**

Run: `npm run test:frontend -- GeneralSection.test.tsx`

Expected: FAIL because the toggle is not rendered.

- [ ] **Step 3: Implement setting support**

Add `GOOGLE_IMAGE_BATCH_ENABLED` to `ALLOWED_KEYS`, `_PLAINTEXT_KEYS`, and `_DEFAULTS` with default `"false"`. In `GeneralSection`, add state/original state, load it from settings, include it in autosave payloads, and render a switch in Visuals.

- [ ] **Step 4: Verify tests pass**

Run: `npm run test:frontend -- GeneralSection.test.tsx`

Expected: PASS.

### Task 2: Backend Batch Helper

**Files:**
- Modify: `backend/integrations/google_image_client.py`
- Modify: `backend/pipeline/image_gen.py`
- Test: `backend/tests/test_google_image_batch.py`

- [ ] **Step 1: Write failing backend tests**

Create tests for a fake Google batch client that returns inline image bytes. Assert the helper creates one batch job, polls until success, returns temp PNG paths, and raises on terminal failure.

- [ ] **Step 2: Verify tests fail**

Run: `uv run --project backend pytest backend/tests/test_google_image_batch.py -q`

Expected: FAIL because the helper does not exist.

- [ ] **Step 3: Implement Google Batch helper**

Add functions that build inline generateContent requests with `response_modalities=["IMAGE"]` and `image_config.aspect_ratio`, submit via `client.batches.create`, poll via `client.batches.get`, extract inline image parts, write temp PNGs, and record usage as `image_gen_batch`.

- [ ] **Step 4: Verify tests pass**

Run: `uv run --project backend pytest backend/tests/test_google_image_batch.py -q`

Expected: PASS.

### Task 3: Visual Batch Job API

**Files:**
- Modify: `backend/api/visuals.py`
- Modify: `backend/pipeline/image_gen.py`
- Test: `backend/tests/test_visual_batch_job.py`

- [ ] **Step 1: Write failing backend tests**

Test that `POST /api/visuals/generate-batch-job` returns a job id. With `GOOGLE_IMAGE_BATCH_ENABLED=false`, assert standard `generate_batch` is called. With it enabled and a full-frame scene, assert the new batch pipeline is called. With a batch exception, assert the job status becomes failed and does not call the standard path as a fallback.

- [ ] **Step 2: Verify tests fail**

Run: `uv run --project backend pytest backend/tests/test_visual_batch_job.py -q`

Expected: FAIL because the endpoint does not exist.

- [ ] **Step 3: Implement backend job**

Add request/response models, start a `render_jobs` background job, update progress, route by `GOOGLE_IMAGE_BATCH_ENABLED`, persist returned scene assets into script JSON, and expose a status endpoint.

- [ ] **Step 4: Verify tests pass**

Run: `uv run --project backend pytest backend/tests/test_visual_batch_job.py -q`

Expected: PASS.

### Task 4: Timeline Integration

**Files:**
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/components/timeline/useTimelineState.ts`
- Test: existing frontend timeline tests if present; otherwise typecheck/build.

- [ ] **Step 1: Write failing frontend coverage**

Add or update API-level tests if available to assert `generateVisualBatchJob` posts to `/api/visuals/generate-batch-job` and `getVisualBatchJobStatus` reads `/api/visuals/generate-batch-status/{job_id}`.

- [ ] **Step 2: Verify test fails**

Run: `npm run test:frontend -- api`

Expected: FAIL if API tests exist, otherwise document no matching test file and proceed with TypeScript build as verification.

- [ ] **Step 3: Implement frontend job polling**

Add API helpers and update `generateAllImages` to submit all scene payloads to the backend job, poll status, refresh the script on completion, and keep progress visible. Preserve single-scene generation.

- [ ] **Step 4: Verify frontend**

Run: `npm run test:frontend -- GeneralSection.test.tsx`

Run: `cd frontend && npm run build`

Expected: both commands exit 0.

### Task 5: Full Verification and Project Docs

**Files:**
- Modify: `AGENTS.md`

- [ ] **Step 1: Update project convention**

Add a convention that true Google Batch image generation is optional, applies only to Generate All Images, and must not silently fallback to standard paid calls after a batch failure.

- [ ] **Step 2: Run targeted backend tests**

Run: `uv run --project backend pytest backend/tests/test_google_image_batch.py backend/tests/test_visual_batch_job.py -q`

Expected: PASS.

- [ ] **Step 3: Run broader verification**

Run: `npm run test:frontend -- GeneralSection.test.tsx`

Run: `cd frontend && npm run build`

Expected: PASS.

- [ ] **Step 4: Commit, push, and delegated review**

Stage relevant files, commit with an imperative message, push to `main`, dispatch delegated review of the most recent commit, apply all required findings, and repeat until LGTM.

