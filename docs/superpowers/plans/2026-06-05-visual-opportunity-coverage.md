# Visual Opportunity Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make outline-time visual opportunity planning more permissive for extended and medium visual modes without adding hard final quotas.

**Architecture:** Extend the existing shared visual-mode policy with soft opportunity discovery guidance and a coverage schema. Thread the field through standard and life-as-a outline prompts, keep per-segment scene prompts contextual, and update in-app docs for invisible workflow behavior.

**Tech Stack:** Python 3.12 backend prompt helpers, React/TypeScript docs surfaces, pytest via `uv run --project backend pytest`, Vitest via `cd frontend && npm run test -- ...`.

---

## File Structure

- Modify: `backend/pipeline/visual_mode_policy.py`
  - Add soft opportunity discovery expectations and coverage schema guidance.
- Modify: `backend/prompts/script.py`
  - Add `visual_opportunity_coverage` to standard and life-as-a outline schemas.
  - Strengthen wording so long scripts normally surface multiple candidates before accepting low/zero counts.
- Modify: `backend/tests/pipeline/test_visual_mode_policy.py`
  - Lock long-script soft coverage language and schema requirements.
- Modify: `backend/tests/pipeline/test_scriptwriter_visual_beats.py`
  - Lock outline prompt coverage field and contextual segment prompt behavior.
- Modify: `frontend/src/components/docs/WorkflowDocSection.tsx`
  - Explain the invisible outline-time candidate discovery behavior.
- Modify: `frontend/src/components/settings/visual-modes/VisualModesSection.tsx`
  - Explain that extended modes have soft candidate discovery expectations, not hard quotas.
- Modify: relevant frontend tests for those doc surfaces.
- Modify: `AGENTS.md`
  - Record the convention that long-script opportunity planning uses soft candidate coverage before accepting zeros.

## Task 1: Backend Policy and Prompt Contract

**Files:**
- Modify: `backend/pipeline/visual_mode_policy.py`
- Modify: `backend/prompts/script.py`
- Test: `backend/tests/pipeline/test_visual_mode_policy.py`
- Test: `backend/tests/pipeline/test_scriptwriter_visual_beats.py`

- [ ] Step 1: Write failing backend tests.
  - Add assertions that long-script guidance mentions soft candidate expectations, at least two candidates for `captions`, `popup_sequence`, and `comparison_board`, one or two `stat_card` candidates, `visual_opportunity_coverage`, and no hard final quotas.
  - Add assertions that both outline prompts include `visual_opportunity_coverage`.
- [ ] Step 2: Run focused backend tests and confirm they fail for missing coverage expectations.
  - Command: `uv run --project backend pytest backend/tests/pipeline/test_visual_mode_policy.py backend/tests/pipeline/test_scriptwriter_visual_beats.py -q`
- [ ] Step 3: Implement minimal backend prompt-policy changes.
  - Add coverage expectation lines to `prompt_visual_opportunity_guidance`.
  - Add `visual_opportunity_coverage` to `prompt_visual_opportunity_schema_guidance`.
  - Add `visual_opportunity_coverage` to standard and life-as-a outline prompt schemas and critical instructions.
- [ ] Step 4: Run the same focused backend tests and confirm they pass.

## Task 2: Docs and Project Convention

**Files:**
- Modify: `AGENTS.md`
- Modify: `frontend/src/components/docs/WorkflowDocSection.tsx`
- Modify: `frontend/src/components/settings/visual-modes/VisualModesSection.tsx`
- Test: `frontend/src/components/docs/DocsPage.test.tsx`
- Test: `frontend/src/components/settings/visual-modes/VisualModesSection.test.tsx`

- [ ] Step 1: Write failing frontend docs tests.
  - Assert docs mention soft candidate discovery, extended modes, and contextual final mode usage.
- [ ] Step 2: Run focused frontend tests and confirm they fail.
  - Command: `cd frontend && npm run test -- src/components/docs/DocsPage.test.tsx src/components/settings/visual-modes/VisualModesSection.test.tsx`
- [ ] Step 3: Update docs surfaces and `AGENTS.md`.
  - Add concise explanation of invisible outline-time soft candidate expectations.
- [ ] Step 4: Run focused frontend tests and confirm they pass.

## Task 3: Full Verification, Commit, Push, Review

**Files:**
- All modified files above.

- [ ] Step 1: Run focused backend and frontend tests.
- [ ] Step 2: Run broader backend tests if focused backend passes.
  - Command: `npm run test:backend`
- [ ] Step 3: Stage, commit, and push to `main`.
- [ ] Step 4: Dispatch delegated code review per `AGENTS.md`.
- [ ] Step 5: Apply any required findings, commit as `fix: address review findings`, push, and repeat review until LGTM.
