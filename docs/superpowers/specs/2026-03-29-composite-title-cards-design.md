# Composite Grid Title Card System

**Date:** 2026-03-29
**Status:** Design approved, pending implementation

## Problem

The current title card system generates individual solid-color PNG images with centered text for each segment. This produces a generic look that doesn't match the visual style of successful educational YouTube channels (e.g., "Everything Professor"), which use a single composite grid card showing all segments as circular images with labels.

## Solution

Replace the per-segment solid-color title cards with a single composite grid title card that:
- Displays all segments as AI-generated circular images in a grid
- Shows a condensed video title at the top with one word highlighted in an accent color
- Animates a zoom from the full card to each segment's circle at segment transitions
- Doubles as the YouTube thumbnail

## Design

### Script Generation

Claude generates additional fields during script generation:

**ScriptContent level:**
- `card_title` — condensed 2-4 word uppercase title (e.g., "TYPES OF DREAMS")
- `card_title_highlight_word` — the word to render in accent color (e.g., "DREAMS")

**Segment level:**
- `circle_color` — hex color for the circle background, chosen thematically by Claude
- `title_card_image_prompt` — visual prompt for the AI-generated circle image, using the same brand art style as regular scenes

**Constraints:**
- Segment count must be exactly 6, 8, 10, or 12
- Grid layouts: 6→2×3, 8→2×4, 10→2×5, 12→3×4

### Image Generation

Each segment's `title_card_image_prompt` is fed through the existing Gemini image pipeline to generate a square image. These are stored as `title_card_{segment_idx}.png`.

### Pillow Compositing

A new `title_card_composer.py` module creates the composite:
1. 1920×1080 white canvas
2. Title text at top (bold, uppercase, highlight word in brand accent color)
3. Circle-crop each AI image → place on colored circle backgrounds → arrange in grid
4. Segment labels below each circle (bold, uppercase, small, dark text)
5. Output: `composite_title_card.png`

### Video Rendering

Each title card scene uses the composite PNG with an FFmpeg zoompan filter:
- Starts at zoom=1 (full card visible)
- Zooms to frame the target segment's circle
- Duration matches the narration audio length
- Zoom target coordinates calculated from grid position

### Thumbnail

The composite card replaces fal.ai thumbnail generation when the title_cards modifier is active.

## Files Changed

| File | Change |
|------|--------|
| `backend/models/script.py` | Add `card_title`, `card_title_highlight_word` to ScriptContent; `circle_color`, `title_card_image_prompt` to Segment; `title_card_zoom_target` to Scene |
| `backend/pipeline/scriptwriter.py` | Constrain segment count to even values (6/8/10/12) |
| `backend/pipeline/modifiers/title_cards.py` | Rewrite prompt injection, post-processing, and pre-render hooks |
| `backend/pipeline/title_card_composer.py` | **NEW** — Pillow compositing module |
| `backend/pipeline/title_card.py` | Replace solid-color FFmpeg generation with AI image gen + Pillow compositing |
| `backend/pipeline/ffmpeg_builder.py` | Add `build_title_card_zoom_cmd()` for zoom animation |
| `backend/pipeline/video_render.py` | Use zoom command for title card scenes |
| `backend/pipeline/thumbnail.py` | Use composite card when available |
| `backend/api/thumbnail.py` | Check for composite card before fal.ai generation |
| `pyproject.toml` | Add Pillow dependency |

## Verification

1. Generate a script → verify new fields populated
2. Generate images → verify circle images created
3. Check composite → verify grid layout and styling
4. Preview title card scene → verify zoom animation
5. Render full video → verify segment transitions
6. Check thumbnail → verify matches composite card
7. Test all grid sizes (6, 8, 10, 12)
