# Script Rating Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the unused pass/fail script reviewer with a persisted GPT-5-mini script rating that appears on the dashboard and timeline.

**Architecture:** Add a focused backend rating module that calls the routed LLM once, validates JSON, recomputes scores locally, and stores the result in `ScriptContent.script_rating`. Generation saves the rating after script creation, summaries expose the overall value, and frontend components render compact and detailed score views.

**Tech Stack:** Python 3.12, FastAPI, SQLModel, Pydantic, React 19, TypeScript, Tailwind 4, Vitest, pytest via `uv`.

---

## File Structure

- Remove: `backend/pipeline/script_reviewer.py` because it is unused legacy code.
- Modify: `backend/prompts/script.py` to remove `SCRIPT_REVIEW_RUBRIC`.
- Modify: `backend/integrations/llm_client.py` to add the `script_rating` LLM task.
- Modify: `backend/models/script.py` to add rating models, `ScriptContent.script_rating`, and `ScriptSummary.script_rating_overall`.
- Create: `backend/pipeline/script_rating.py` for prompt construction, LLM call, parsing, and score recomputation.
- Modify: `backend/api/scripts.py` to run rating after generation and include summary overall score.
- Create: `backend/tests/test_script_rating.py` for rating model/parser behavior.
- Modify: `backend/tests/test_script_summaries.py` for summary exposure.
- Modify: `backend/tests/test_script_generation_eli_flag.py` or create a focused generation test for persistence.
- Modify: `frontend/src/types/script.ts` to add `ScriptRating` types and summary overall field.
- Create: `frontend/src/components/script/ScriptRatingCard.tsx` for detailed timeline rendering.
- Modify: `frontend/src/components/script/ScriptGenerationPage.tsx` or the timeline-side script panel to show the rating card where script-level cards live.
- Modify: `frontend/src/components/dashboard/ProjectDashboard.tsx` to show the compact badge.

## Tasks

### Task 1: Backend Data Model And Legacy Removal

**Files:**
- Modify: `backend/models/script.py`
- Modify: `backend/prompts/script.py`
- Modify: `backend/integrations/llm_client.py`
- Delete: `backend/pipeline/script_reviewer.py`
- Test: `backend/tests/test_script_rating.py`

- [ ] Write failing tests for `ScriptRating` serialization and `script_rating` LLM routing.
- [ ] Run `uv run --project backend pytest backend/tests/test_script_rating.py backend/tests/test_llm_routing.py -q` and confirm the new tests fail because the model/task does not exist.
- [ ] Add rating Pydantic models and `ScriptContent.script_rating`.
- [ ] Add `script_rating` to `LLM_TASKS`.
- [ ] Remove the unused reviewer module and prompt rubric.
- [ ] Run the focused tests and confirm they pass.

### Task 2: Rating Pipeline

**Files:**
- Create: `backend/pipeline/script_rating.py`
- Test: `backend/tests/test_script_rating.py`

- [ ] Write failing tests for parsing a complete LLM response and recomputing all category averages plus weighted overall.
- [ ] Write failing tests for rejecting missing criteria and out-of-range scores.
- [ ] Run `uv run --project backend pytest backend/tests/test_script_rating.py -q` and confirm the tests fail for missing implementation.
- [ ] Implement prompt constants, script payload extraction, `parse_script_rating_response`, and `rate_script`.
- [ ] Run the focused test and confirm it passes.

### Task 3: Generation Persistence And Summaries

**Files:**
- Modify: `backend/api/scripts.py`
- Modify: `backend/tests/test_script_summaries.py`
- Create or modify: focused generation API test

- [ ] Write a failing summary test asserting `script_rating_overall` is populated from saved `ScriptContent.script_rating`.
- [ ] Write a failing generation test that monkeypatches `api.scripts.rate_script`, completes generation, and verifies the saved script has `script_rating`.
- [ ] Run focused backend tests and confirm failure.
- [ ] Wire `rate_script` into `_run_generation` after the initial script save and before final job completion.
- [ ] Add `script_rating_overall` to `_build_summary`.
- [ ] Run focused backend tests and confirm they pass.

### Task 4: Frontend Types And UI

**Files:**
- Modify: `frontend/src/types/script.ts`
- Create: `frontend/src/components/script/ScriptRatingCard.tsx`
- Modify: `frontend/src/components/timeline/TimelinePage.tsx`
- Modify: `frontend/src/components/dashboard/ProjectDashboard.tsx`

- [ ] Add TypeScript rating interfaces.
- [ ] Add a detailed `ScriptRatingCard` with overall, category rows, criterion chips, and explanation text.
- [ ] Render the card on the timeline when `content.script_rating` exists.
- [ ] Add a dashboard `Script {score}` badge beside the hook badge when `script_rating_overall` exists.
- [ ] Run `npm run test:frontend -- --run` and `cd frontend && npm run build`.

### Task 5: Verification, AGENTS Update, Commit, Push, Review Loop

**Files:**
- Modify: `AGENTS.md`

- [ ] Update `AGENTS.md` with the new convention: full-script quality ratings use `ScriptContent.script_rating`; the old `script_reviewer.py` path is removed and must not be reintroduced.
- [ ] Run backend focused tests.
- [ ] Run frontend tests/build.
- [ ] Stage only feature files, commit, and push to `main`.
- [ ] Dispatch delegated review for the most recent commit.
- [ ] If review returns findings, implement every fix, commit as `fix: address review findings`, push, and repeat review until LGTM.
