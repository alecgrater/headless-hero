# Unified Visual Mode Design

## Goal

Replace the scene-level split between `media_source` and `visual_treatment` with one canonical scene setting: `visual_mode`.

Supported visual modes:

- `video`
- `full_frame`
- `popup_sequence`
- `flipflop`

## Architecture

`Scene.visual_mode` becomes the source of truth for routing, asset ownership, UI labels, and analyzer output. Existing `media_source` and `visual_treatment` remain as compatibility fields while old scripts, Remotion props, and transitional code still need them.

The compatibility mapping is deterministic:

| visual_mode | media_source | visual_treatment |
| --- | --- | --- |
| `video` | `ai_video` | `full_frame` |
| `full_frame` | `ai` | `full_frame` |
| `popup_sequence` | `ai` | `popup_sequence` |
| `flipflop` | `ai` | `flipflop` |

When old data lacks `visual_mode`, the model derives it from the legacy pair. Invalid combinations normalize to the nearest valid mode, with `ai_video` winning as `video`.

## Backend Behavior

The media analyzer should become a visual mode router. It may still preserve the file/function names during migration, but its assignment object should carry `visual_mode`; applying assignments updates all three fields so downstream code remains compatible.

The animation type analyzer should no longer assign popup/flipflop independently of video routing. It should emit `visual_mode` assignments for `full_frame`, `popup_sequence`, and `flipflop`, and it should keep `video` scenes as `video`.

Image/video generation should dispatch from `visual_mode`:

- `video` owns `video_url` and any anchor metadata.
- `full_frame` owns `image_url` and `frame_urls`.
- `popup_sequence` owns transparent cutout `visual_layers`.
- `flipflop` owns two panel `visual_layers`.

Compatibility fields are synchronized before persistence and render input generation.

## Frontend Behavior

Every scene picker should expose one control named visual mode, with four options:

- Video
- Full frame
- Popup sequence
- Flip-flop

The UI should not show separate media source and animation type controls for the same scene. Test Lab should use the same four-mode control and enable/disable mode-specific stages from that selection.

## Testing

Add backend tests for normalization, legacy derivation, assignment application, and generation dispatch. Add frontend tests or focused build coverage for the unified option mapping where practical.

## Documentation

Update `AGENTS.md` so future work treats `visual_mode` as canonical and only uses `media_source` / `visual_treatment` as compatibility fields.
