# Eli Vortex Thumbnail Design

**Date:** 2026-04-14
**Status:** Approved

## Summary

Replace the Eli corner overlay system (both in thumbnails and video) with a Gemini-powered thumbnail transformation. Instead of hand-coding visual effects, generate a base title card composite with Pillow, then pass it to Gemini alongside a user-uploaded reference thumbnail and an Eli character frame. Gemini handles all creative work: glowing magic borders on circles, inserting Eli popping out of one random circle, and punching up the title for higher CTR.

## What Changes

### Remove
- **Corner Eli overlay on title card** — Layer 8 (`_overlay_eli_frame()`) in `title_card_composer.py`
- **Corner Eli overlay in video** — `EliOverlay.tsx` rendering in `SceneRenderer.tsx`, `eli_animator.py` generation, `/api/eli/*` endpoints
- **Solid circle outline + energy ring** — Layers 5/5b in `title_card_composer.py` (Gemini replaces these with glowing borders)

### Add
- **Settings UI**: Upload reference thumbnail images (style guides for Gemini)
- **Gemini image transformation step** after base title card compositing
- **New prompt pipeline**: base composite + reference thumbnail + Eli frame + video title → Gemini → final thumbnail

### Keep As-Is
- Base title card compositing (background, circles, images, labels, title text) — becomes the "input" to Gemini
- Video content (scenes, audio, FX, subtitles — all unchanged)
- Character frame library (still used — a random frame is passed to Gemini)
- Title card zoom scenes in the video (use the base composite, not the Gemini-enhanced one)
- No-title variant (`composite_title_card_notitle.png`) — stays Pillow-only, used for video zoom scenes

## Pipeline Flow

```
1. Compose base title card (existing Pillow pipeline, minus Eli corner overlay
   and minus circle outline/energy ring layers)
   → composite_title_card_base.png

2. Select inputs:
   - Base composite image
   - Random reference thumbnail (from user's uploaded collection)
   - Random Eli character frame (prefer thumbnail_frames with open mouth)
   - Video title + segment names (for context)

3. Send to Gemini with prompt:
   "Use the reference thumbnail to guide your edits to this title card.
    Choose one of the segment circles at random and replace it with
    the character (provided) popping out of that circle, the same way
    the character appears in the reference thumbnail. Also update the
    styling of all circle borders and the title text to be more punchy
    and visible, matching the reference style. Do all this in the name
    of having a higher CTR on YouTube."

4. Save Gemini output → composite_title_card.png (final thumbnail)
```

### Fallback
If no reference thumbnails are uploaded, skip the Gemini transformation step and use the base composite as the final thumbnail (same behavior as today minus the Eli corner overlay).

## CTR Expression Tiers

Gemini selects the appropriate expression/pose based on the video title and topic. The prompt includes guidance on three expression tiers for reference:

### 1. Pattern Interrupt (High Surprise)
Trigger "What happened?" response. Best for shocking/unexpected content.
- **Gasped Breath**: Mouth slightly open, eyes wide, eyebrows raised
- **Wince/Cringe**: One eye squinting, mouth pulled to side ("How is this real?")
- **Wide-Eyed Hyper-Focus**: Leaning into camera, dilated pupils

### 2. Negative Tension (Anxiety & Concern)
Trigger survival instinct to "avoid the mistake." Best for warning/cautionary content.
- **Forehead Furrow**: Brows pinched, hand on chin/forehead
- **Tears/Red Eyes**: Glistening eyes, empathy-driving
- **Secretive "Shush"**: Finger to lips, eyes darting ("insider" curiosity)

### 3. Action-Oriented (Excitement & Joy)
Best for travel, tech reviews, challenge content.
- **Mid-Laugh**: Genuine squinty-eyed laugh
- **"Look at This" Gaze**: Not at camera, looking with wonder at subject
- **Exertion/Struggle**: Teeth grit, brow sweating

These tiers are included in the Gemini prompt as guidance. We send Gemini a random Eli character frame, and Gemini adapts the character's expression and pose in its output to match the tier that best fits the video title/topic. Gemini has full creative control — it may modify the character's expression from the provided frame.

## Storage

| Path | Purpose |
|------|---------|
| `data/character/thumbnail_references/` | User-uploaded reference thumbnail images (gitignored) |
| `data/projects/{script_id}/images/composite_title_card_base.png` | Base Pillow composite (input to Gemini) |
| `data/projects/{script_id}/images/composite_title_card.png` | Final Gemini-enhanced thumbnail |
| `data/projects/{script_id}/renders/thumbnails/0.png` | Copy of final thumbnail for export |

## Settings UI

Add a **"Thumbnail References"** subsection to the existing Character settings section (`CharacterSection.tsx`):
- Drag-and-drop or file picker upload area
- Grid of uploaded reference thumbnails with delete buttons
- Brief help text: "Upload thumbnails from channels you admire. These guide the style of your generated thumbnails."
- No limit on count, but UI shows a manageable grid

## API Endpoints

### New: Thumbnail Reference Management
- `GET /api/character/thumbnail-references` — List uploaded reference filenames + URLs
- `POST /api/character/thumbnail-references` — Upload a new reference image (multipart form)
- `DELETE /api/character/thumbnail-references/{filename}` — Remove a reference image

### Modified: Thumbnail Generation
- `POST /api/thumbnail/recomposite` — Updated to:
  1. Generate base composite (existing Pillow pipeline, no Eli overlay, no outline/energy ring)
  2. If reference thumbnails exist: run Gemini transformation
  3. Save both base and final versions

## Gemini Integration

### Image Transformation Call
The existing `google_image_client.py` already supports `reference_image_path` for multi-modal input. Extend this to accept multiple reference images:
- Base title card composite (the image to transform)
- Reference thumbnail (the style guide)
- Eli character frame (the character to insert)

All three are sent as image parts alongside the text prompt. Gemini returns a single transformed image.

### Prompt Structure
```
You are a YouTube thumbnail optimizer. You have been given:
1. A base title card image with circular segment thumbnails arranged in a grid
2. A reference thumbnail showing the target visual style
3. A character image to insert into the title card

Your task:
- Study the reference thumbnail's visual style (circle borders, glow effects,
  character positioning, title treatment)
- Choose one of the segment circles at random and replace its image with the
  provided character popping out of that circle, matching how the character
  appears in the reference thumbnail (head extending past circle, hands gripping edge)
- Apply the reference thumbnail's circle border styling (glowing magical borders)
  to ALL circles in the image
- Update the title text styling to be more punchy, bold, and attention-grabbing,
  matching the reference thumbnail's title treatment
- The video title is: "{title}"
- Optimize everything for maximum YouTube CTR

Keep the segment label badges readable. Keep the overall layout intact.
Return the modified image.
```

## Files to Modify

| File | Change |
|------|--------|
| `backend/pipeline/title_card_composer.py` | Remove `_overlay_eli_frame()` call. Remove Layer 5 (circle outline) and Layer 5b (energy ring). Keep `include_eli` param for backwards compat but default to False. |
| `backend/pipeline/thumbnail.py` | Add `gemini_enhance_thumbnail()` function: takes base composite + reference + Eli frame → calls Gemini → saves result |
| `backend/api/character.py` | Add thumbnail reference upload/list/delete endpoints |
| `backend/api/thumbnail.py` | Update `recomposite` to call Gemini enhancement after base composition |
| `backend/integrations/google_image_client.py` | Add `transform_image()` function that sends multiple images + prompt to Gemini |
| `frontend/src/components/settings/CharacterSection.tsx` | Add "Thumbnail References" upload/grid section |
| `frontend/src/api.ts` | Add `getThumbnailReferences()`, `uploadThumbnailReference()`, `deleteThumbnailReference()` |
| `remotion/src/scenes/SceneRenderer.tsx` | Remove EliOverlay rendering block |
| `remotion/src/effects/overlays/EliOverlay.tsx` | Delete file (no longer used) |
| `backend/api/eli.py` | Delete file (no longer generating animation keyframes) |
| `backend/pipeline/eli_animator.py` | Delete file (no longer generating animation keyframes) |
| `backend/models/script.py` | Keep `eli_overlay` field on Scene for backwards compat (existing scripts), but no longer generated |
| `frontend/src/components/timeline/TimelinePage.tsx` | Remove "Add Eli" button and eli-related UI |

## What Pillow Does vs What Gemini Does

| Pillow (base image) | Gemini (transformation) |
|---------------------|------------------------|
| Background gradient | Glowing magic circle borders |
| Circle images (masked to circles) | Eli popping out of one circle |
| Segment label badges | Punchier title styling |
| Title text (basic rendering) | Overall CTR optimization |
| Grid layout positioning | Expression/pose selection |

## Edge Cases

- **No reference thumbnails uploaded**: Skip Gemini step, use base composite as final thumbnail (graceful fallback)
- **No character frames generated**: Skip Eli insertion in prompt, still apply border/title styling
- **Gemini fails or returns error**: Fall back to base composite, log warning
- **Multiple reference thumbnails**: Pick one at random each time (variety in output style)
- **Recomposite without regenerating circles**: Works — base composite rebuilds from cached circle images, then Gemini transforms
