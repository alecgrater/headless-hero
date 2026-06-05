# Caption Normal Duration Audit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make captions a normal-duration editorial punch mode and add deterministic pre-voiceover metadata audit for caption/stat candidates without rewriting narration.

**Architecture:** Update shared visual-mode policy and prompts so captions are normal-duration. Add a focused helper in `backend/pipeline/scriptwriter.py` that runs after generated scenes are assembled and before downstream post-processing. The helper promotes only eligible metadata, detects internal renderer language in narration, and is covered by backend tests. Update docs and AGENTS conventions.

**Tech Stack:** Python 3.12 backend, existing `Scene`/`ScriptContent` models, pytest via `uv run --project backend pytest`, React/Vitest docs tests.

---

## Task 1: Caption Duration Policy

**Files:**
- Modify: `backend/pipeline/visual_mode_policy.py`
- Modify: `backend/prompts/script.py`
- Test: `backend/tests/pipeline/test_visual_mode_policy.py`
- Test: `backend/tests/pipeline/test_scriptwriter_visual_beats.py`

- [ ] Step 1: Add failing tests that assert `captions` has normal duration/profile and prompt text describes captions as a short editorial punch mode.
- [ ] Step 2: Run `uv run --project backend pytest backend/tests/pipeline/test_visual_mode_policy.py backend/tests/pipeline/test_scriptwriter_visual_beats.py -q` and confirm failure.
- [ ] Step 3: Update duration target/profile and prompt text.
- [ ] Step 4: Rerun focused tests and confirm pass.

## Task 2: Pre-Voiceover Metadata Audit

**Files:**
- Modify: `backend/pipeline/scriptwriter.py`
- Test: `backend/tests/pipeline/test_scriptwriter_visual_beats.py`

- [ ] Step 1: Add failing tests for deterministic audit behavior:
  - long scripts get several caption promotions from exact narration phrases,
  - stat-card promotions use money/time/year figures,
  - existing specialized modes are preserved,
  - narration text is unchanged.
- [ ] Step 2: Run focused backend tests and confirm failure.
- [ ] Step 3: Implement helper functions and call them before final script post-processing.
- [ ] Step 4: Rerun focused backend tests and confirm pass.

## Task 3: Internal Visual-Mode Leakage Guard

**Files:**
- Modify: `backend/pipeline/scriptwriter.py`
- Test: `backend/tests/pipeline/test_scriptwriter_visual_beats.py`

- [ ] Step 1: Add failing test that narration containing internal terms like "captions rendering" or "popup sequence" raises a clear `RuntimeError`.
- [ ] Step 2: Run focused backend tests and confirm failure.
- [ ] Step 3: Implement guard without rewriting narration.
- [ ] Step 4: Rerun focused backend tests and confirm pass.

## Task 4: Docs and Conventions

**Files:**
- Modify: `AGENTS.md`
- Modify: `frontend/src/components/docs/WorkflowDocSection.tsx`
- Modify: `frontend/src/components/settings/visual-modes/VisualModesSection.tsx`
- Test: `frontend/src/components/docs/DocsPage.test.tsx`
- Test: `frontend/src/components/settings/visual-modes/VisualModesSection.test.tsx`

- [ ] Step 1: Add/update tests for normal-duration captions and metadata-only audit language.
- [ ] Step 2: Run focused frontend tests and confirm failure.
- [ ] Step 3: Update docs and project conventions.
- [ ] Step 4: Rerun focused frontend tests and confirm pass.

## Task 5: Verification, Commit, Push, Review

- [ ] Step 1: Run focused backend tests.
- [ ] Step 2: Run focused frontend docs tests.
- [ ] Step 3: Run `npm run test:backend`.
- [ ] Step 4: Stage relevant files, commit, push to `main`.
- [ ] Step 5: Dispatch delegated code review per `AGENTS.md`; fix required findings and repeat until LGTM.
