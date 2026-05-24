# Character Asset Service Design

## Goal

Create one robust reusable path for generating a character image and producing a transparent cropped character cutout. The original reference image remains the canonical identity source, and the cutout becomes a derived asset that any workflow can reuse for compositing, popup experiments, Remotion animation, future character walk-ons, thumbnails, and other staged visuals.

The first consumers are preset-scoped main character generation and the Popup Crop Lab anchor-character workflow. Popup item sheets remain separate because they crop multiple items from one contact sheet.

## Current State

Preset-scoped characters are generated in `backend/pipeline/main_character.py`. The generated image is saved under:

```text
data/style/presets/{preset_id}/characters/{character_id}.png
```

Project sync copies the selected preset character into:

```text
data/projects/{script_id}/character/reference.png
```

These files are full 16:9 character reference images. They are good identity anchors for image model reference chaining and human review, but they are not ready for direct compositing because they still have a background.

Popup Crop Lab has a one-off anchor workflow in `backend/pipeline/test_lab_popup_crop.py`. It prompts for a character on a chroma background, samples the image corners, removes matching background pixels, auto-trims the result, and writes `crop_01_anchor_character.png`. This proves the approach, but the logic is local to Test Lab and cannot be reused by main-character pages or future Remotion treatments.

## Recommended Approach

Add a shared backend service, `backend/pipeline/character_assets.py`, that creates a character asset bundle from either a generated image or an existing source image.

The service owns:

- Character-specific generation prompt constraints for removable backgrounds.
- Background removal strategy selection.
- Alpha trimming and padding.
- Metadata and warning generation.
- Stable file naming for original references and transparent cutouts.

Callers should not implement their own character background removal. They call the service and receive explicit URLs/paths for both the original reference and the cutout.

## Asset Bundle

Each bundle contains:

```text
reference.png
cutout.png
metadata.json
```

When variants are already used, the variant source remains as the saved candidate and the active bundle points to the selected variant:

```text
references/{idx}.png
cutouts/{idx}.png
reference.png
cutout.png
metadata.json
```

`reference.png` is the canonical original image used for image-model reference chaining and UI review. `cutout.png` is the transparent auto-trimmed derivative used for compositing. `metadata.json` records enough detail to debug and reprocess without guessing.

Suggested metadata fields:

```json
{
  "version": 1,
  "source_path": "reference.png",
  "cutout_path": "cutout.png",
  "source_sha256": "...",
  "cutout_sha256": "...",
  "prompt_fingerprint": "...",
  "background_removal_method": "chroma_corner_sample",
  "trim_box": [120, 42, 830, 1010],
  "padding": 24,
  "warnings": []
}
```

## Data Model and API Shape

`StylePresetCharacter` keeps `reference_image_url` for compatibility and adds:

```text
cutout_image_url: str = ""
```

`StylePresetCharacterResponse` returns both URLs. Existing UI that only knows about `reference_image_url` continues to work; new compositing features use `cutout_image_url`.

Project config can continue to store `main_character_reference_url`. The project-local cutout can be resolved by convention:

```text
data/projects/{script_id}/character/cutout.png
/static/projects/{script_id}/character/cutout.png
```

If the frontend needs it immediately, project config responses can include a computed `main_character_cutout_url` without changing the core project config table.

## Character Generation Flow

Preset-scoped character creation becomes:

1. Validate the preset row and preset image file.
2. Build the style-matched character prompt.
3. Request a centered full-body character on a removable flat background.
4. Save the generated original as the active reference/variant.
5. Run the shared character asset processor to produce `cutout.png`.
6. Save the database row with both reference and cutout URLs.
7. Select the new character for that preset.

Project sync becomes:

1. Copy selected preset character `reference.png` into the project-local `reference.png`.
2. Copy selected preset character `cutout.png` into the project-local `cutout.png` when it exists.
3. If the selected preset character lacks a cutout, process the copied reference in place to create one.
4. Preserve the existing `ScriptContent.main_character` and `ProjectConfig.main_character_reference_url` contract.

Popup Crop Lab anchor generation becomes:

1. Generate the anchor source image with the shared character prompt constraints.
2. Run the shared character asset processor.
3. Return the original source URL, transparent cutout URL, trim box, and warnings.

Popup item-sheet generation stays in `test_lab_popup_crop.py`. Its slot-based multi-crop logic is different enough that forcing it through the character service would make both systems less clear.

## Background Removal Strategy

The first implementation uses deterministic chroma removal because the app can control the prompt:

1. Prompt for a flat chroma background color that does not appear in the character.
2. Sample corner pixels to infer the background color.
3. Confirm the corners are reasonably consistent.
4. Make pixels within tolerance transparent.
5. Auto-trim the alpha bounds with configurable padding.

The service should be strategy-based internally so future processors can be added without changing callers:

```text
chroma_corner_sample
external_removebg
rembg_model
manual_alpha_passthrough
```

The initial processor records warnings instead of failing for imperfect output. Hard failures are reserved for missing source files, unreadable images, and write errors.

## Quality Warnings

The processor should warn when output appears suspicious:

- Visible alpha bounds are extremely small.
- Visible alpha bounds cover nearly the whole image.
- The trim box touches an image edge, suggesting clipping.
- The alpha channel is almost entirely opaque after processing.
- Corner samples disagree too much to trust chroma removal.

Warnings are returned to API callers and written into metadata. UI can surface them in Test Lab and later in Settings if helpful.

## Dev Dashboard Logging

Character asset generation affects generated media and should log concise status messages:

- Reference generation started/completed.
- Cutout processing started/completed.
- Background removal warnings.
- Missing cutout repaired during project sync.

These logs make failures visible during Test Lab and project generation without requiring file-system inspection.

## Tests

Backend tests should cover:

- The processor preserves the original reference file.
- The processor writes a transparent `cutout.png`.
- The processor trims alpha bounds with padding.
- Metadata includes source hash, cutout hash, method, trim box, and warnings.
- Missing source images fail clearly.
- Suspicious outputs record warnings.
- Creating a style-preset character returns both reference and cutout URLs.
- Project sync carries both reference and cutout files into the project-local character directory.
- Project sync repairs a missing cutout from the selected reference.
- Popup Crop Lab anchor generation uses the shared character asset processor.
- Popup item-sheet crop behavior remains unchanged.

Frontend verification should cover:

- Settings style-preset character cards still show reference images.
- Any new cutout preview uses checkerboard styling.
- Popup Crop Lab still shows raw/source and transparent character outputs.
- `cd frontend && npm run build`

Backend verification:

```bash
npm run test:backend
```

## Non-Goals

- No migration of legacy global main-character settings.
- No new generic asset registry for all generated items.
- No replacement of item-sheet crop logic.
- No requirement to integrate rembg or a paid removebg service in the first implementation.
- No UI redesign beyond exposing cutout-derived outputs where an existing workflow already needs them.

## Open Implementation Notes

The implementation should avoid making database migrations a blocker if possible. The project already accepts lightweight schema evolution, but the first pass can use a new optional SQLModel field and tests should exercise fresh isolated engines.

The metadata processor version should increment whenever prompt or removal behavior changes enough that stale cutouts should be regenerated.
