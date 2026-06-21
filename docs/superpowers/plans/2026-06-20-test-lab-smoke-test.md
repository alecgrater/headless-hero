# Test Lab Smoke Test Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a one-click Test Lab smoke-test tab that runs targeted diagnostics for project-generation risk and reports pass/warn/fail results.

**Architecture:** Add a backend smoke-test service in `backend/pipeline/test_lab_smoke.py` and expose it through a thin `POST /api/test-lab/smoke-test` route. Add frontend types/API helper plus a focused `SmokeTestLab` component mounted from `TestLabPage`.

**Tech Stack:** FastAPI, Pydantic, SQLModel settings access, React 19, TypeScript, Vitest, pytest.

---

### Task 1: Backend Smoke-Test Report

**Files:**
- Create: `backend/pipeline/test_lab_smoke.py`
- Modify: `backend/api/test_lab.py`
- Test: `backend/tests/test_test_lab_smoke.py`

- [ ] **Step 1: Write failing backend tests**

Create tests for report shape, blink guardrail warnings, missing representative presets, and API route wiring.

- [ ] **Step 2: Verify backend tests fail**

Run: `uv run --project backend pytest backend/tests/test_test_lab_smoke.py -v`

Expected: failures because `pipeline.test_lab_smoke` and `/api/test-lab/smoke-test` do not exist yet.

- [ ] **Step 3: Implement backend service and route**

Add Pydantic models for request options and report rows, deterministic local checks, and a route that delegates to the service.

- [ ] **Step 4: Verify backend tests pass**

Run: `uv run --project backend pytest backend/tests/test_test_lab_smoke.py -v`

Expected: all tests pass.

### Task 2: Frontend Smoke-Test Tab

**Files:**
- Modify: `frontend/src/types/testLab.ts`
- Modify: `frontend/src/api.ts`
- Create: `frontend/src/components/test-lab/SmokeTestLab.tsx`
- Modify: `frontend/src/components/test-lab/TestLabPage.tsx`
- Test: `frontend/src/components/test-lab/TestLabPage.test.tsx`
- Test: `frontend/src/components/test-lab/SmokeTestLab.test.tsx`

- [ ] **Step 1: Write failing frontend tests**

Add tests that the tab appears, clicking `Run Smoke Test` posts default options, and result rows render status/details/next actions.

- [ ] **Step 2: Verify frontend tests fail**

Run: `npm run test:frontend -- SmokeTestLab TestLabPage`

Expected: failures because the component/helper do not exist and the tab is not mounted.

- [ ] **Step 3: Implement frontend types, API helper, tab component, and mount**

Add typed report interfaces, `runTestLabSmokeTest`, `SmokeTestLab`, and a `smoke-test` tab case in `TestLabPage`.

- [ ] **Step 4: Verify frontend tests pass**

Run: `npm run test:frontend -- SmokeTestLab TestLabPage`

Expected: all targeted frontend tests pass.

### Task 3: Verification and Completion

**Files:**
- Verify affected backend and frontend tests.
- Check `AGENTS.md` only if the implementation establishes a new project convention.

- [ ] **Step 1: Run backend targeted tests**

Run: `uv run --project backend pytest backend/tests/test_test_lab_smoke.py backend/tests/test_test_lab.py -v`

Expected: pass.

- [ ] **Step 2: Run frontend targeted tests**

Run: `npm run test:frontend -- SmokeTestLab TestLabPage`

Expected: pass.

- [ ] **Step 3: Run final status check**

Run: `git status --short`

Expected: only intentional files changed.
