# Global Style Preset — Design

**Date:** 2026-05-22
**Status:** Approved (ready for implementation plan)

## Goal

Enforce a consistent visual art style across all videos by attaching a single "style reference" image to every Gemini image-generation call. The reference is a multi-subject sheet (people, objects, environments) generated from a user-supplied free-form prompt. Switching between saved presets in Settings rotates the active style globally.

## Non-Goals

- No per-project preset selection (one global active preset at a time).
- No fine-tuning / LoRA training.
- No automatic regeneration of already-generated images when the active preset changes (lazy invalidation only — old caches stay until intentionally regenerated).
- Does not affect Eli's frame library, Eli-driven projects, or main-character generation.

## Behavior Summary

A *style preset* is a single 16:9 reference image generated from a free-form Gemini prompt. Multiple presets live in a library; **one** is "active" globally (`AppSettings["active_style_preset_id"]`). Each project carries an independent `style_preset_enabled` toggle that decides whether *that* video uses the active preset. The toggle is force-disabled and ignored when `eli_enabled` is true for that project.

When a project's `eli_enabled` is `false` AND `style_preset_enabled` is `true` AND there is an active preset, the active preset image is attached as an extra multi-modal `Part` to every Gemini image-generation call for that video, alongside any existing character reference (Eli ref or `main_character` ref). When `eli_enabled` is `true`, the style preset is ignored entirely.

**Scope of application** (Option 3 — full coverage):
- Scene images (`pipeline/image_gen.py` → `generate_scene_image`)
- Animation frames (`pipeline/image_gen.py` → `generate_scene_frames` / `_v2`)
- YouTube thumbnails (`pipeline/thumbnail.py`)
- Cinematic chapter cards (life-as-a format, `cinematic_chapters.py`)
- Cinematic clean thumbnail and split-progression enhancement pass (`cinematic_chapters.py`)

Title-card composites (`pipeline/title_card.py`) are unaffected because they are FFmpeg/PIL composites of existing scene images, not Gemini calls.

## Architecture

### Storage

- New SQLModel table `style_presets`: `id (UUID str, PK)`, `name (str)`, `prompt (str)`, `created_at (datetime)`.
- Image file on disk: `data/style/presets/<id>.png`.
- Static mount: `/static/style` → `data/style/`.
- Active preset id: stored in existing `AppSettings` under key `active_style_preset_id` (nullable). No new table needed for "active."
- Global default toggle for new projects: stored in existing `AppSettings` under key `style_preset_enabled_default` (defaults to `"true"`). Mirrors how `eli_enabled_default` is already handled.
- Per-project toggle: new bool field `style_preset_enabled` on `ProjectConfig`. When a new `ProjectConfig` row is created, the field is initialized from `AppSettings["style_preset_enabled_default"]` (just like `eli_enabled` is initialized from `eli_enabled_default`).

### Resolution Rule

In `pipeline/image_gen.py`:

```python
def _active_style_preset_path() -> str | None:
    """Reads AppSettings, returns absolute file path if the active preset exists, else None."""

def _resolve_style_preset(eli_enabled: bool, project_style_enabled: bool) -> str | None:
    if eli_enabled or not project_style_enabled:
        return None
    return _active_style_preset_path()
```

### Image-Gen Integration

1. `integrations/google_image_client.generate_image()` — add optional parameter `style_reference_path: str | None = None`. When set, the function loads the file as a `types.Part.from_bytes` and appends it to the `contents` list **after** any character reference Part and **before** the prompt text. Same retry/fallback paths apply unchanged.

2. `pipeline/image_gen.py` — wire the new helpers into:
   - `generate_scene_image`
   - `generate_scene_frames`
   - `generate_scene_frames_v2`
   The `eli_enabled` value is already loaded by `_load_project_character_context`, so no extra DB fetch. The new style ref path is forwarded to `generate_image` via the new parameter.

3. `pipeline/thumbnail.py` — load the project's `style_preset_enabled` flag, resolve the style ref via the same helpers, and forward to `generate_image`.

4. `pipeline/formats/title_cards/cinematic_chapters.py` — already calls `generate_scene_image`, so it picks up the style ref automatically. The split-progression enhancement pass (which calls `transform_with_references` with the clean image) needs a small edit to also include the style preset path in its image list when the style preset is active.

### Cache Invalidation

The existing `[char_ref:{path}:{mtime}]` marker pattern in cached prompt strings gets a sibling marker:

```
[style_ref:{path}:{mtime}]
```

appended when a style preset is active. Switching active preset → path changes → cache miss on next regen. Regenerating a preset image → mtime changes → cache miss. Lazy invalidation only.

## API

### New Router — `backend/api/style.py`

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/style/presets` | List all presets (id, name, prompt, image_url, created_at) |
| POST | `/api/style/presets` | Create new — body `{prompt, name?}` → returns `{job_id}`, runs Gemini in background |
| GET | `/api/style/presets/jobs/{job_id}` | Poll generation status |
| DELETE | `/api/style/presets/{id}` | Delete (file + DB row + clears active if it was the active one) |
| GET | `/api/style/active` | Returns the active preset or `null` |
| PUT | `/api/style/active` | Body `{preset_id: str \| null}` |

### Updated Endpoints

- `POST /api/scripts/generate` — request body gains `style_preset_enabled: bool` (defaults to the global setting if omitted).
- `GET /api/project-config/{script_id}` — response gains `style_preset_enabled`.
- `PUT /api/project-config/{script_id}` — accepts `style_preset_enabled`.

## Pipeline

### `backend/pipeline/style_presets.py` (new)

- `generate_preset(prompt: str, name: str) -> str` — calls Gemini at 16:9 with the user's free-form prompt as-is, saves the resulting PNG to `data/style/presets/<id>.png`, inserts the DB row, returns the new preset id.
- Background job tracking that reuses the in-memory dict + threading pattern from `render_jobs.py` and `pipeline/character_frames.py`.
- The user's prompt is sent **as-is**. No programmatic wrapping or scaffolding. The UI textarea provides an example placeholder that guides users toward writing multi-subject prompts.

## Frontend

### Shared component — `frontend/src/components/shared/StylePresetToggle.tsx`

Used in every per-project surface and in Settings → Misc.

Props:
```ts
{
  eliEnabled: boolean
  enabled: boolean
  onChange: (enabled: boolean) => void
  activePresetName: string | null
}
```

Behavior:

- **Active state** — toggle is on, Eli is off, an active preset exists. Shows: `Active: "<preset name>"`. Inline descriptor: "Applies the preset across all scenes, frames, thumbnails, and chapter cards."
- **Off state** — toggle is off, Eli is off. Inline descriptor: "No style preset will be used."
- **Greyed state** — Eli is on. Toggle is forced off and disabled. Inline descriptor: "Style presets only apply when Eli is disabled for this video."
- **Warning state** — toggle is on but no preset is active. Inline warning: "No active preset. Pick one in Settings → Style Presets."

Descriptions render *inline* under the toggle (not just on hover), so the user can never flip the switch without seeing the resulting behavior.

### Active preset context — `frontend/src/contexts/StylePresetContext.tsx` (new)

A small provider mounted at App level that fetches `/api/style/active` once and exposes `{ activePreset, refresh }`. Refreshed when Settings changes the active preset. Avoids stale state when the user switches active preset and navigates back to a per-project page.

### Settings → Style Presets section — `frontend/src/components/settings/StylePresetsSection.tsx` (new)

- Header: "Style Presets" + descriptor: "A reference image attached to AI image generation. Used to enforce a consistent visual art style across all videos. Only applies when Eli is disabled for a video."
- **Active preset selector** at the top: labelled dropdown showing "None" plus all presets, with the current active preset marked. Caption: "All non-Eli projects with the style toggle on will use this preset."
- **Preset library** below: 3-column grid of cards. Each card shows the preset image (thumbnail), name, prompt (truncated, expand on hover), an "Active" badge if active, and a delete button. A trailing `+` card opens the create modal.
- **Create modal**:
  - Name field
  - Free-form prompt textarea with placeholder example: "A 16:9 reference sheet showing 6 diverse people in different poses, 4 everyday objects, and 2 environments — all in 90s Nickelodeon style with thick outlines and muted earth tones."
  - Explainer block above the prompt: "This prompt is sent to Gemini as-is. Tip: include multiple subjects (people, objects, environments) so the reference can guide many kinds of scene generations."
  - Generate button → calls `POST /api/style/presets`, polls the job, shows preview + Save / Discard / Regenerate buttons.

### Settings → Misc section — `frontend/src/components/settings/MiscSection.tsx` (extended)

Reframed as "Default for new projects" if not already so. Add the StylePresetToggle next to the existing Eli toggle, with a header line: "These defaults apply when you create a new project. They can still be overridden per project." The Style Preset toggle here uses the same shared component, with `eliEnabled` bound to the global default — same greying behavior.

### Per-project surfaces (extended)

Three pages already render an Eli toggle:

- `IdeationPage.tsx`
- `ScriptGenerationPage.tsx`

Each adds a `StylePresetToggle` next to its existing Eli toggle. The submit payload in `useScriptGeneration.ts` (lines 317 and 449, currently `eli_enabled: eliEnabled`) gains `style_preset_enabled: stylePresetEnabled` alongside.

### TimelinePage — read-only badge

A small badge near the header: `[ Eli: off · Style: Saturday Cartoon ]`. Clicking the badge deep-links to Settings → Style Presets. The badge is informational — per-project toggles cannot be edited from the timeline (matches existing read-only behavior for Eli at this stage).

### API client — `frontend/src/api.ts` additions

```ts
listStylePresets(): Promise<StylePreset[]>
createStylePreset(prompt: string, name: string): Promise<{ job_id: string }>
pollStylePresetJob(jobId: string, onUpdate?: (status) => void): Promise<StylePreset>
deleteStylePreset(id: string): Promise<void>
getActiveStylePreset(): Promise<StylePreset | null>
setActiveStylePreset(id: string | null): Promise<void>
```

## Testing

Additive — no rewriting existing tests:

- `backend/tests/test_style_preset_resolve.py` — covers all branches of `_resolve_style_preset` (eli on → None; project disabled → None; active=None → None; else → path).
- `backend/tests/test_image_gen_with_style_preset.py` — mocks Gemini, asserts the style ref Part is forwarded for non-Eli + project-enabled, suppressed otherwise. Covers single-image and multi-frame paths.
- `backend/tests/test_style_preset_api.py` — CRUD + active endpoint behavior + delete-active edge case (clears active id from `AppSettings`).
- `backend/tests/test_thumbnail_with_style_preset.py` — confirms thumbnail and cinematic-chapters paths thread the preset through correctly, and that the split-progression enhancement pass includes the style ref.

## Edge Cases

- **Active preset deleted while assigned.** `DELETE /api/style/presets/{id}` checks if the deleted id matches `AppSettings["active_style_preset_id"]` and clears it (sets to null) in the same transaction.
- **Active preset id present but file missing on disk.** `_active_style_preset_path` returns `None` if the file does not exist; image-gen proceeds without a style ref. Logged as a warning.
- **Project created before the field existed.** `ProjectConfig.style_preset_enabled` defaults to the value in `AppSettings["style_preset_enabled_default"]` (which itself defaults to `"true"`); existing rows that lack the field read the default. `_resolve_style_preset` then checks `_active_style_preset_path`, which returns `None` if no preset is active. Net effect: no behavior change for existing projects until a user activates a preset.
- **User toggles active preset mid-render.** Render jobs in flight already hold their resolved Gemini call inputs in memory; switching the active preset has no effect on a running job. Subsequent regenerations of the same scene observe the new preset.
- **Two references collide.** When both `main_character` ref and style preset are sent (Eli off, person scene, style on), Gemini sees character first (about *who*) then style (about *how*) then prompt. Acceptable; if quality degrades we can revisit ordering.

## Open Questions

None blocking. Future considerations:

- Whether to expose per-project preset *selection* (not just on/off) if the global-only model proves too rigid.
- Whether to add a toggle to disable the preset specifically for thumbnails if the channel-row consistency vs click-through-design tradeoff turns out poorly.
