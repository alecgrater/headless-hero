# Eli Disable Per Project + Main Character Replacement

**Date:** 2026-05-22
**Status:** Design approved, ready for implementation plan

## Summary

Make Eli (the recurring animated host overlay) optionally disable-able. When a project has Eli disabled, the pipeline picks a topic-specific main character, generates a single canonical reference image for that character, and chains that reference into scene image generation so the character appears consistently in scenes that warrant it.

The Eli on/off decision is a **project-level toggle**, set at idea-pick time, locked once the script is generated. A global default lives in Settings and seeds new projects — flipping it never affects existing projects in either direction.

## Goals

- A single toggle controls Eli for the whole lifetime of a project.
- Existing projects continue to behave exactly as they do today.
- When Eli is disabled, scene images get visual identity from a project-specific main character — no overlay, no host webcam, just visual storytelling.
- UI clearly communicates which mode a project is in.

## Non-goals

- No mid-project switching between Eli/no-Eli modes.
- No main-character integration into thumbnails or title cards (scenes only).
- No multiple characters per project.
- No replacing the existing Eli system — both pipelines coexist, gated by the per-project flag.

## Data Model

### New table: `ProjectConfig`

```python
# backend/models/project_config.py
class ProjectConfig(SQLModel, table=True):
    script_id: str = Field(primary_key=True, foreign_key="script.id")
    eli_enabled: bool = True
    main_character_reference_url: str | None = None
    created_at: datetime
    updated_at: datetime
```

One row per script. Created at script-generation time. Missing rows (legacy projects) treated as `eli_enabled=True` via a `get_project_config(script_id) -> ProjectConfig` helper that returns a synthetic default.

**Source of truth for character data:**
- `ProjectConfig` stores only the queryable mode flag (`eli_enabled`) and the file-system pointer (`main_character_reference_url`).
- The structured character description lives in the `ScriptContent.main_character` JSON blob (see below). When image gen needs the description text, it reads `ScriptContent.main_character` and serializes it into the prompt.
- This avoids duplicating the description in two places.

### New global setting

`eli_enabled_default: bool = True` added to `ALLOWED_KEYS` and `_DEFAULTS` in `backend/api/settings.py`. Read once at idea-picker mount to seed the per-project toggle. Not loaded into env — read directly from DB as needed.

### Script content additions (in script_json blob, no migration)

- `ScriptContent.main_character: MainCharacter | None` — `{ name: str, appearance: str, vibe: str }`. Only populated when `eli_enabled=False`.
- `Scene.include_main_character: bool = False` — Claude sets per scene during scriptwriter. Only meaningful when `eli_enabled=False`.

No changes to existing `Script`, `Scene`, or `EliOverlay` columns/fields.

## Settings & Global Default

**Backend:** Add `eli_enabled_default` to `ALLOWED_KEYS` in `backend/api/settings.py`, default `True`.

**Frontend:** Add a toggle to the top of `frontend/src/components/settings/CharacterSection.tsx`:

- Label: "Enable Eli host overlay by default"
- Help: "When off, new projects start with Eli disabled and use a project-specific main character integrated into scene images instead. Existing projects are unaffected."
- Reads/writes via the existing `PUT /api/settings/keys` flow.

The Character section already manages Eli's frame library; co-locating the default toggle keeps Eli-related controls together.

## Ideation Flow & Toggle UI

### Where the toggle lives

`frontend/src/components/ideation/IdeationPage.tsx` gets a page-level toggle at the top, above the idea grid. Not per-card.

```
┌─────────────────────────────────────────────────────┐
│  [Idea topic input]                       [Generate]│
│  ◉ Eli enabled    ◯ Eli disabled  (i)               │
│                                                     │
│  ── Idea cards grid ──                              │
└─────────────────────────────────────────────────────┘
```

- Initial value seeded from `eli_enabled_default` on page mount.
- Component-state for the session — flowed into the script-gen request when the user picks a card.
- Tooltip explains what Eli is and what disabling means.

### Idea → Script handoff

- `GenerateScriptRequest` (`backend/models/script.py:183`) gains `eli_enabled: bool = True`.
- `POST /api/scripts/generate` reads it, creates `ProjectConfig` alongside the `Script` row in `_run_generation` (`backend/api/scripts.py`).
- Once `ProjectConfig.eli_enabled` is written, no UI edits it — the project is locked into its mode.

## Main Character Generation Pipeline

This pipeline runs **only when `eli_enabled=False`**. When `eli_enabled=True`, nothing in this section executes; the existing Eli pipeline runs unchanged.

### 4a. Character description (during scriptwriter)

`backend/pipeline/scriptwriter.py` — when `eli_enabled=False`, the system prompt is augmented to instruct Claude to:

1. Pick one main character that fits the topic. Output a `main_character` block: `name`, `appearance` (detailed visual description: face, hair, clothing, build), `vibe`.
2. For each scene, set `include_main_character: true` if a person/character would naturally appear in this scene's visual; `false` for landscapes, abstracts, object close-ups.

After script gen completes:
- `main_character` (full structured block) is written into the `script_json` blob — this is the canonical source of truth for character data.
- `Scene.include_main_character` is written into each scene in the JSON blob.
- `ProjectConfig.eli_enabled=False` is set; `main_character_reference_url` is left null until step 4b runs.

### 4b. Reference image generation

New module `backend/pipeline/main_character.py`:

- `generate_character_reference(script_id) -> str`
- Reads `ScriptContent.main_character` for the structured character block.
- Composes a Gemini prompt from `name + appearance + vibe` plus style hints (cinematic lighting, neutral background, chest-up framing).
- Calls `google_image_client.generate_image()`.
- Saves to `data/projects/{script_id}/character/reference.png`.
- Stores path on `ProjectConfig.main_character_reference_url`.
- Cached via mtime + `.prompt` marker file (same pattern as scene images).

Triggered automatically inside the script-generation background job, after script saves and before the user is shown the timeline. User-visible progress step: "Generating script and main character…".

### 4c. User override UI — Main Character drawer

A new top-level drawer/modal launched from a header button (next to the "Eli: off" / "Main character: {name}" badge). Visible only when `eli_enabled=False`.

Contents:
- Reference image preview.
- Character name.
- Editable appearance description (textarea).
- "Regenerate reference image" button.

Editing the description and saving:
- Updates `ScriptContent.main_character` in the `script_json` blob (canonical source).
- Invalidates cached scene images that had `include_main_character=true` (deletes their `.prompt` markers so they re-render on next batch).

Regenerating the reference image:
- Calls `generate_character_reference` again.
- Same cache invalidation as description edits.

### 4d. Eli endpoints defend

`POST /api/eli/generate` and the per-scene regenerate endpoints check `ProjectConfig.eli_enabled` for the script. If `False`, return `400 {"detail": "Eli is disabled for this project"}`. Frontend won't call them (UI is gated), but the backend guards against stale state.

## Image Gen Reference Chaining

`google_image_client.generate_image()` already accepts `reference_image_path` and feeds it to Gemini as a multi-modal Part. This section is mostly wiring.

### `backend/pipeline/image_gen.py` changes

```python
def generate_scene_image(scene, script_id, ...):
    config = get_project_config(script_id)
    script_content = load_script_content(script_id)
    reference_path = None
    character = None

    if not config.eli_enabled and scene.include_main_character:
        reference_path = config.main_character_reference_url
        character = script_content.main_character

    prompt = compose_prompt(scene)
    if character and reference_path:
        prompt = f"{serialize_character(character)}\n\n{prompt}"

    return google_image_client.generate_image(
        prompt=prompt,
        reference_image_path=reference_path,
        ...
    )
```

### Cache invalidation

The existing `.prompt` marker pattern handles description changes for free — the prompt now includes the character description, so a different description produces a different marker. To also invalidate when only the reference image is regenerated (description unchanged), include the reference image's mtime (or a hash of it) in the marker.

### Per-scene flag

Scenes with `include_main_character=False` generate without a reference (pure landscape/object/abstract). This preserves visual variety — forcing the character into every scene would flatten the storytelling.

### `POST /api/visuals/generate-batch`

No batch-level changes — the per-scene logic handles each scene's flag independently.

### Order of operations on a fresh `eli_enabled=False` project

1. Script generates (Claude outputs `main_character` + per-scene flags) → writes Script + ProjectConfig.
2. Character reference generates (1 Gemini call) → writes `main_character_reference_url`.
3. User lands on timeline; scenes can now image-generate with reference chaining.

Steps 1 + 2 happen back-to-back inside the same script-gen background job.

## UI Indicators When Eli Is Disabled

All UI gating reads `ProjectConfig.eli_enabled` via a `getProjectConfig(scriptId)` API call, fetched alongside the script in `TimelinePage`.

### Project header

- Pill badge next to the project title:
  - `"Eli: off"` (neutral gray) until a character has a name.
  - `"Main character: {name}"` once the character is generated.
- Clicking the badge opens the **Main Character drawer**.
- No badge when `eli_enabled=true` (today's behavior preserved).

### "Add Eli" button + Eli scene controls

When `eli_enabled=false`:
- "Add Eli" button rendered but disabled (grayed, `cursor-not-allowed`, no hover).
- Tooltip: "Eli is disabled for this project. The main character is integrated into scene images instead."
- Same treatment for any "Generate Eli" / "Regenerate Eli frame" affordances in scene editors.
- `EliLane` in the per-scene micro-timeline is **hidden** (project header badge already communicates the state; an empty lane is visual noise).

### Settings → Character section

- Frame-library generation UI is unaffected (Eli's frame library is a global asset, not project-scoped).
- The new `eli_enabled_default` toggle sits at the top of the section.

### Pipeline / progress steps

- When `eli_enabled=false`, the "Generate Eli animations" step is removed from the export/progress panel.
- A "Generate main character" step replaces it, showing reference-image-gen progress.
- Export panel's render summary skips Eli-related rollup items.

## File Topology (Implementation Targets)

### New files

- `backend/models/project_config.py` — `ProjectConfig` SQLModel + Pydantic schemas.
- `backend/pipeline/main_character.py` — character reference generation + cache helpers.
- `backend/api/project_config.py` — endpoints: `GET /api/projects/{script_id}/config` (returns `ProjectConfig` + `main_character` from script_json), `PUT /api/projects/{script_id}/config/character` (updates `ScriptContent.main_character` in script_json), `POST /api/projects/{script_id}/config/character/regenerate` (regenerates reference image).
- `frontend/src/components/timeline/MainCharacterDrawer.tsx` — drawer/modal for character override.
- `frontend/src/components/ideation/EliToggle.tsx` (or inline in `IdeationPage.tsx`) — toggle UI.

### Modified files

**Backend:**
- `backend/models/script.py` — add `main_character` to `ScriptContent`, `include_main_character` to `Scene`, `eli_enabled` to `GenerateScriptRequest`.
- `backend/api/scripts.py` — write `ProjectConfig` in `_run_generation`; trigger `generate_character_reference` when `eli_enabled=False`.
- `backend/pipeline/scriptwriter.py` — augment system prompt + parse new fields when `eli_enabled=False`.
- `backend/pipeline/image_gen.py` — read `ProjectConfig`, pass reference path conditionally, prepend description to prompt.
- `backend/api/eli.py` — guard endpoints with `eli_enabled` check.
- `backend/api/settings.py` — add `eli_enabled_default` to `ALLOWED_KEYS` + `_DEFAULTS`.
- `backend/database.py` — register new model so `init_db` creates the table.

**Frontend:**
- `frontend/src/api.ts` — add `getProjectConfig`, `updateMainCharacter`, `regenerateMainCharacter`; extend `generateScript` to send `eli_enabled`.
- `frontend/src/components/ideation/IdeationPage.tsx` — toggle UI + state.
- `frontend/src/components/timeline/TimelinePage.tsx` — fetch `ProjectConfig`, pass to children.
- `frontend/src/components/timeline/PropertiesPanel.tsx` (or wherever "Add Eli" lives — to be confirmed in planning) — disabled state + tooltip.
- `frontend/src/components/timeline/SceneMicroTimeline.tsx` + `micro-timeline/EliLane.tsx` — hide `EliLane` when `eli_enabled=false`.
- `frontend/src/components/settings/CharacterSection.tsx` — toggle for `eli_enabled_default`.
- `frontend/src/components/timeline/ExportPanel.tsx` — swap Eli step for main-character step in progress UI.

## Edge Cases & Defenses

- **Legacy projects (no `ProjectConfig` row):** `get_project_config()` returns synthetic default with `eli_enabled=True`. They behave identically to today.
- **Stale frontend calling `/api/eli/*` on an `eli_enabled=false` project:** backend returns 400. Frontend defends by gating UI.
- **User edits character description while scene images are mid-generation:** description change invalidates `.prompt` markers; in-flight generations finish with the old prompt, next batch picks up new prompt. Acceptable — same behavior as editing a scene's `image_prompt` today.
- **`main_character_reference_url` missing when `include_main_character=true`:** image gen falls back to no-reference generation and logs a warning. Should not happen if script-gen completed successfully, but defends against partial-failure states.
- **Settings default flipped mid-session:** the value is read on `IdeationPage` mount; user has to leave and return for the new default to take effect. Acceptable — settings changes are not expected to be reactive across pages.

## Out of Scope (for follow-ups, not this spec)

- Multiple characters per project.
- Character library reuse across projects.
- Main character in thumbnails or title cards.
- Per-scene character override UI (the page-level character is the only knob; per-scene `include_main_character` is set by Claude and not user-editable in v1).
- Migrating projects between Eli-enabled and Eli-disabled modes.
