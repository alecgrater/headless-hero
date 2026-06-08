# Preset-Scoped Characters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the separate global main-character flow with preset-scoped characters shown beneath the selected style preset.

**Architecture:** Add a `StylePresetCharacter` SQLModel and character helpers beside the existing style preset pipeline. Keep project-local render paths unchanged by syncing the active character for the active style preset into existing `ProjectConfig` and `ScriptContent` fields. Merge the Settings UI into one carousel-style preset box plus a similar character box below it.

**Tech Stack:** FastAPI, SQLModel, SQLite, React 19, TypeScript, Tailwind 4, pytest, Vite build.

---

### Task 1: Backend Preset-Scoped Character API

**Files:**
- Create: `backend/models/style_preset_character.py`
- Create: `backend/tests/test_style_preset_characters.py`
- Modify: `backend/api/style.py`
- Modify: `backend/pipeline/main_character.py`
- Modify: `backend/database.py`

- [ ] **Step 1: Write failing API tests**

Add tests that create two style presets, create a character for one preset, verify it is hidden from the other preset, verify cross-preset selection fails, and verify generation receives the preset image as `style_reference_path`.

- [ ] **Step 2: Run red tests**

Run: `uv run --project backend pytest backend/tests/test_style_preset_characters.py -q`
Expected: failures because endpoints and model do not exist.

- [ ] **Step 3: Implement model, helpers, endpoints, and migration**

Create `StylePresetCharacter`, add preset character endpoints under `/api/style/presets/{preset_id}/characters`, pass style preset images into generation, and add a startup migration/create step for the new table.

- [ ] **Step 4: Run green tests**

Run: `uv run --project backend pytest backend/tests/test_style_preset_characters.py backend/tests/test_style_preset_api.py -q`
Expected: all selected backend tests pass.

### Task 2: Project Sync Uses Active Preset Character

**Files:**
- Modify: `backend/pipeline/main_character.py`
- Modify: `backend/tests/test_image_gen_main_character.py`
- Modify: `backend/tests/test_test_lab.py`

- [ ] **Step 1: Write failing sync tests**

Add coverage that Eli-disabled generation blocks without an active style preset character, then copies the active preset character into `data/projects/{script_id}/character/reference.png`.

- [ ] **Step 2: Run red tests**

Run: `uv run --project backend pytest backend/tests/test_image_gen_main_character.py -q`
Expected: failures showing old global-character sync behavior.

- [ ] **Step 3: Implement sync changes**

Read the active style preset id, read the active character for that preset, copy its image into the existing project-local reference path, and write the character details into `ScriptContent.main_character`.

- [ ] **Step 4: Run green tests**

Run: `uv run --project backend pytest backend/tests/test_image_gen_main_character.py backend/tests/test_character_reference_generation_gates.py -q`
Expected: all selected backend tests pass.

### Task 3: Unified Settings UI

**Files:**
- Modify: `frontend/src/api.ts`
- Modify: `frontend/src/components/settings/StylePresetsSection.tsx`
- Optionally leave unused: `frontend/src/components/settings/MainCharacterSection.tsx`

- [ ] **Step 1: Add frontend API types**

Add `StylePresetCharacter`, `listStylePresetCharacters`, `createStylePresetCharacter`, `getActiveStylePresetCharacter`, and `selectStylePresetCharacter`.

- [ ] **Step 2: Replace tabs and active-preset box**

Remove the two-tab segmented control and the standalone "Active preset" select. The style preset carousel remains the active selector: the visible `Set as active` button is the way to activate a preset.

- [ ] **Step 3: Add matching character box below**

Render a second carousel-style box under the style preset box. It lists only characters for the selected preset, supports select-as-active, and has a dashed "New character" action with inline name/appearance/vibe inputs for generating a new character.

- [ ] **Step 4: Verify frontend build**

Run: `cd frontend && npm run build`
Expected: production build succeeds.

### Task 4: End-To-End Verification And Auto-Commit

**Files:**
- Modify if needed: `AGENTS.md`

- [ ] **Step 1: Run focused backend tests**

Run: `uv run --project backend pytest backend/tests/test_style_preset_characters.py backend/tests/test_style_preset_api.py backend/tests/test_image_gen_main_character.py -q`

- [ ] **Step 2: Run frontend build**

Run: `cd frontend && npm run build`

- [ ] **Step 3: Stage, commit, push, and review loop**

Stage relevant files, commit with a descriptive imperative message, push to `main`, dispatch delegated review for the most recent commit, apply required findings, and repeat until LGTM.

