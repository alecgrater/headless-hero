# Preset-Scoped Characters Design

## Goal

Style presets and main characters become one combined workflow. A character is generated from a specific style preset, belongs only to that preset, and can only be selected when that preset is active or being viewed. The Settings UI has one Style Presets screen: choose the active preset at the top, review preset images, then manage the characters available for the selected preset.

## Current State

The app currently stores style presets in the `style_presets` table and generated preset images at `data/style/presets/{id}.png`. The active preset is stored in `AppSetting` under `ACTIVE_STYLE_PRESET_ID`.

Main character settings are separate global app settings (`GLOBAL_MAIN_CHARACTER_*`) with a global reference image at `data/character/main/reference.png`. Project generation syncs that global character into `ScriptContent.main_character` and copies the active reference to `data/projects/{script_id}/character/reference.png`.

This works for a single house character, but it cannot express "this character belongs to this visual style."

## Recommended Approach

Add a preset-scoped character library backed by the database. Each character row has exactly one `style_preset_id`, and selection is also scoped per preset.

This is preferable to filesystem-only metadata because the UI needs reliable list, select, delete, and validation behavior. It is also preferable to stamping a style id onto the old global character because the product model becomes many characters grouped under many presets, not one global character that happens to remember a style.

## Data Model

Create a new SQLModel table:

```text
style_preset_characters
  id: str primary key
  style_preset_id: str
  name: str
  appearance: str
  vibe: str
  reference_image_url: str
  created_at: datetime
```

Store generated character reference images under:

```text
data/style/presets/{preset_id}/characters/{character_id}.png
```

Track the active character per preset in `AppSetting` with keys like:

```text
ACTIVE_STYLE_PRESET_CHARACTER_ID_{preset_id}
```

Read APIs must hide characters whose referenced image file is missing, matching the existing style-preset behavior for stale fileless rows. Selecting a character must verify that both the character and preset image exist and that the character belongs to the requested preset.

## API

Add preset-scoped character endpoints under the existing style router:

```text
GET  /api/style/presets/{preset_id}/characters
POST /api/style/presets/{preset_id}/characters
GET  /api/style/presets/{preset_id}/active-character
POST /api/style/presets/{preset_id}/characters/{character_id}/select
```

`POST /characters` accepts name, appearance, and vibe, generates a reference using the preset image as the style reference, saves the row and image, and selects the new character for that preset.

The old `/api/style/main-character` endpoints remain temporarily for compatibility during the transition, but new Settings UI and project sync use the preset-scoped endpoints.

## Character Generation

Character generation must require an existing style preset and image file. The prompt keeps the existing no-text, flat-illustration, and non-photorealistic constraints, but stops describing a single global house style as the only source of truth. Instead, it says the character must match the selected style preset image.

Generation passes the selected preset image as `style_reference_path` through the existing Gemini image client. The character reference is still a clean 16:9 reference image with the character centered on a plain background.

## Project Sync

When Eli is disabled, project image generation syncs from:

1. The active style preset.
2. The active character for that style preset.
3. The character reference image scoped to that preset.

The project-local render contract stays the same: copy the selected character image to `data/projects/{script_id}/character/reference.png`, set `ProjectConfig.main_character_reference_url`, and write the selected character details into `ScriptContent.main_character`.

If no active preset exists, or the active preset has no active character, image generation blocks with a clear message that directs the user to Settings -> Style Presets.

## Settings UI

Replace the two-tab `StylePresetsSection` UI with one continuous screen:

1. Active style preset selector at the top.
2. Style preset carousel/preview with set-active, delete, and new-preset actions.
3. Character gallery for the selected preset.
4. Character editor/generator for creating a new character under the selected preset.

The character gallery shows only characters for the selected preset. Cards show the reference image, name, and active marker. Clicking a non-active character selects it for that preset. If no preset is selected, the character area shows an empty disabled state.

The UI does not show a separate "Main Character" tab. Characters appear as part of the selected preset, not a separate global subsystem.

## Deletion Behavior

Deleting a style preset clears that preset's active character key, deletes its character rows, and removes its character image directory after the database delete succeeds.

Deleting individual characters is not required for the first implementation unless it falls out naturally from existing UI patterns. If omitted, character rows remain append-only under each preset.

## Compatibility

Fresh installs start with no preset-scoped characters. Existing global main character settings are treated as legacy data and are not migrated automatically. Existing projects with copied project-local references can continue to render from their stored project config until they need to sync fresh settings.

AGENTS.md is updated to describe preset-scoped characters as the source of truth and to stop requiring a global main character reference.

## Tests

Backend tests cover:

- Characters are listed only for their own preset.
- Creating a character fails when the preset row or image is missing.
- Creating a character uses the preset image as a style reference.
- Selecting a character under the wrong preset fails.
- Active character lookup is scoped by preset.
- Eli-disabled project sync blocks when no active preset or no active character exists.
- Eli-disabled project sync copies the active preset character into the existing project-local path.

Frontend verification includes:

- `cd frontend && npm run build`
- UI state where no preset exists.
- UI state where a preset exists but has no characters.
- UI state where multiple presets have different character galleries.
