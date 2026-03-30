# Multi-Frame Animated Scene Content — Testing Guide

This document describes the expected behavior of the multi-frame pipeline so you can systematically test every feature and know what's correct vs. broken.

---

## 1. Brand Profile — Visual DNA / Style String

### Where
Brand Form → below the Font carousel, above Content Modifiers.

### Expected Behavior
- A textarea labeled **"Visual DNA / Style Prompt"** appears with helper text: *"This exact text is prepended verbatim to every image generation prompt."*
- The field persists across save/reload of the brand profile.
- The value is stored in `brand_profiles.style_string` (TEXT column in SQLite).
- **Existing brands** created before this update will have an empty `style_string` — the migration adds the column with a default of `''`.
- Whatever you type here appears **first** in every composed image prompt, before the style guide, brand art style, color palette, font, and scene visual prompt.

### How to Test
1. Create a new brand → fill in the Style Prompt → save → reload the brand edit page → confirm the text persisted.
2. Edit an existing brand → the field should be empty but present.
3. Generate an image for a scene → check the backend logs or the prompt cache file (`data/projects/{script_id}/images/{scene_id}.prompt`) — the style_string should appear at the very top of the composed prompt.

---

## 2. Scene Data Model — New Fields

### Fields Added to Scene (stored in `script_json` blob)

| Field | Type | Default | Purpose |
|-------|------|---------|---------|
| `frame_count` | `int` | `0` | Desired number of frames (1-8). `0` = use legacy single-image path. |
| `frame_prompts` | `list[str]` | `[]` | One visual prompt per frame. Length should match `frame_count`. |
| `frame_urls` | `list[str]` | `[]` | Web-relative paths to generated frame images, populated after image gen. |
| `frame_seed` | `int \| null` | `null` | Optional seed for visual consistency across frames (Replicate only). |
| `scene_transition` | `str` | `""` | Transition from previous scene: `""` (hard cut), `"crossfade"`, `"slide_left"`, `"slide_right"`, `"push_up"`. |

### Backward Compatibility
- **Existing scripts** with `is_animated: true` + `visual_prompt_b` continue to work — the legacy A/B flip render path is untouched.
- `frame_count: 0` (or missing) means the scene uses the old single-image or A/B path.
- The `is_animated` and `visual_prompt_b` fields still exist and function.

### How to Test
1. Load an old script → open a scene in PropertiesPanel → the new fields should show with defaults (frame budget = 1, no frame prompts, transition = Hard Cut).
2. Save a script with frame_prompts → reload → confirm all frame data round-trips through the API.

---

## 3. PropertiesPanel — UI Changes

### Frame Budget Slider
- Located where the old "Animation / A/B flip" checkbox was.
- Range slider from **1 to 8**.
- Displays the current value as a number next to the label.
- Helper text: *"1 = static image, 2-8 = crossfade animation between frames"*
- Moving the slider:
  - **Increases**: adds empty string entries to `frame_prompts` array.
  - **Decreases**: trims entries from the end of `frame_prompts`.
  - Immediately calls `onUpdate` with both `frame_count` and `frame_prompts`.

### Per-Frame Prompt Textareas
- **Only visible when frame_count > 1.**
- One textarea per frame, labeled "Frame 1", "Frame 2", etc.
- Each is 2 rows tall with violet-tinted border.
- Editing a frame prompt updates local state on change; commits to parent on blur.
- Placeholder: *"Describe frame N visual..."*

### Frame Image Preview Strip
- **Only visible when `frame_urls` has > 1 entry** (i.e., after multi-frame generation).
- Horizontal row of small thumbnails (56px tall) with scroll overflow.
- Appears inside the frame budget section.

### Image Preview Area (main)
- When `frame_urls` has > 1 entry: shows a **3-column grid** of all frame thumbnails (64px tall each).
- When legacy A/B: shows side-by-side A/B preview (unchanged).
- When single image: shows full-width preview (unchanged).

### Generate Button Text
- `frame_count > 1`: **"Generate N Frames"** or **"Regenerate N Frames"**
- `is_animated` (legacy): **"Generate Images (A+B)"** or **"Regenerate Images (A+B)"**
- Otherwise: **"Generate Image"** / **"Regenerate Image"**

### Scene Transition Dropdown
- New dropdown below the frame budget section.
- Options: **Hard Cut** (default), **Crossfade**, **Slide Left**, **Slide Right**, **Push Up**.
- Helper text: *"Transition from previous scene into this one"*
- The first scene's transition value is ignored during rendering (nothing to transition from).

### Legacy A/B Compatibility
- If a scene has `is_animated: true` AND either no `frame_prompts` or `frame_count <= 1`:
  - Shows a **"Legacy A/B Flip"** label with a **"Convert to Multi-Frame"** button.
  - The Visual Prompt (B) textarea is shown below.
  - Clicking "Convert to Multi-Frame" sets `frame_count: 2`, creates `frame_prompts` from `[visual_prompt, visual_prompt_b]`, and sets `is_animated: false`.

### How to Test
1. Open any scene → frame budget slider should default to 1 (or whatever `frame_count` is).
2. Move slider to 3 → three "Frame N" textareas appear below.
3. Move slider back to 1 → textareas disappear.
4. Open a legacy animated scene → "Legacy A/B Flip" section with convert button should appear.
5. Click "Convert to Multi-Frame" → slider jumps to 2, two frame prompts are pre-filled from visual_prompt and visual_prompt_b.
6. Set scene transition to "Crossfade" → confirm it persists after navigating away and back.

---

## 4. Image Generation — Multi-Frame Path

### Single Scene Generation (`/api/visuals/generate`)
- When `frame_prompts` is non-empty in the request:
  - Calls `generate_scene_frames()` instead of `generate_scene_image()`.
  - Each frame is saved as `{scene_id}_f0.png`, `{scene_id}_f1.png`, etc.
  - Each has a `.prompt` cache file: `{scene_id}_f0.prompt`, etc.
  - Response includes `frame_urls: ["/static/projects/.../scene_001_f0.png", ...]`.
  - `image_url` is set to the first frame URL for backward compat.
- When `frame_prompts` is empty:
  - Falls through to legacy single/A-B path (unchanged).

### Prompt Composition Order
1. `style_string` (verbatim, from brand) — **first**
2. Style guide (from `prompts/image_gen_guide.md`)
3. Brand art style
4. Color palette
5. Brand font/typography
6. Frame-specific visual prompt

### Caching
- Each frame has its own `.prompt` marker file.
- If the composed prompt matches the cached marker and the `.png` exists, the frame is **skipped** (not regenerated).
- Changing **any part** of the prompt (style_string, brand_style, frame prompt text) invalidates the cache for that frame.

### Seed Parameter
- `frame_seed` is passed to the image generation provider.
- **Replicate (Flux)**: Actually uses the seed for deterministic output → frames with same seed should look visually consistent.
- **Google (Gemini)**: Accepts the parameter but ignores it (Gemini doesn't support seeds).
- `frame_seed: null` means no seed (random).

### Batch Generation (`generateAllImages`)
- Collects `frame_prompts` and `frame_seed` from each scene.
- Passes them through to `/api/visuals/generate` for each scene.
- Updates `frame_urls` in state after each successful generation.

### How to Test
1. Set frame_count to 3, write three frame prompts → click "Generate 3 Frames".
2. Check `data/projects/{script_id}/images/` → should see `{scene_id}_f0.png`, `_f1.png`, `_f2.png` and their `.prompt` files.
3. Click "Regenerate 3 Frames" without changing prompts → should be **instant** (cache hit, no API call).
4. Change one frame prompt → regenerate → only that frame should be regenerated (check file timestamps).
5. Set frame_count to 1 → generate → should create normal `{scene_id}.png` (legacy path).
6. Use batch "Generate All Images" with scenes that have frame_prompts → each should get multi-frame treatment.

---

## 5. FFmpeg Rendering — Multi-Frame Scenes

### Scene Video Rendering
When a scene has `frame_urls` with >1 entry:

1. Resolves local paths for `{scene_id}_f0.png`, `_f1.png`, etc.
2. Calls `build_multiframe_scene_video_cmd()`.
3. Each frame gets:
   - `-loop 1 -i frame.png` as input
   - Ken Burns zoompan filter (same effect/intensity applied to all frames)
   - Scaled and padded to output resolution
4. Frames are chained with `xfade=transition=fade:duration=0.4` crossfade filters.
5. Text overlay is applied on the final composed stream.
6. Audio is the last input, mapped separately.

### Per-Frame Duration Calculation
```
frame_duration = (total_duration + (N-1) * crossfade_duration) / N
```
- `crossfade_duration` defaults to 0.4 seconds.
- Example: 12s scene with 3 frames → frame_duration = (12 + 0.8) / 3 = 4.27s each.
- Minimum frame_duration is clamped to `crossfade_duration + 0.1` to prevent invalid filter graphs.

### Edge Cases
- **1 frame**: Falls back to standard `build_scene_video_cmd()` — identical to legacy single-image behavior.
- **Missing frame files**: If any `_fN.png` file doesn't exist on disk, those are skipped. If only 1 valid frame remains, falls back to single-image path.

### Cache Check
- Output mtime is compared against **ALL** frame image mtimes + audio mtime.
- If any source file is newer than the output, the scene is re-rendered.

### Fallback Chain (render_scene_video)
1. `frame_urls` has >1 entry → **multi-frame path**
2. `is_animated: true` + B image exists on disk → **legacy A/B flip path**
3. Otherwise → **single image + Ken Burns**

### How to Test
1. Generate 3 frames for a scene + generate audio → click "Preview Scene" → video should show smooth crossfades between the three frames with audio underneath.
2. Compare a 1-frame scene vs. an old scene with no frame_count → should render identically.
3. Re-render a multi-frame scene without changing anything → should be instant (cache hit).
4. Change one frame image → re-render → should re-render (cache miss).
5. Test with Ken Burns enabled → each frame should have the same motion effect.

---

## 6. Full Video Rendering — Scene Transitions

### How It Works
- When rendering the full YouTube video, `render_full_video()` collects each scene's `scene_transition` value.
- If **any** scene has a non-empty transition, it uses `build_concat_with_transitions_cmd()` instead of plain `build_concat_cmd()`.
- Supported transitions between scenes:
  - `""` (empty) or `"hard_cut"` → simple concat (no re-encode for that pair)
  - `"crossfade"` → FFmpeg `xfade=transition=fade` + `acrossfade`
  - `"slide_left"` → `xfade=transition=slideleft`
  - `"slide_right"` → `xfade=transition=slideright`
  - `"push_up"` → `xfade=transition=slideup`

### Important Details
- The xfade approach uses `offset=eof-0.4` meaning the crossfade starts 0.4s before the first clip ends.
- Audio uses `acrossfade` to smoothly blend between clips.
- If all transitions are hard cuts, the fast concat demuxer is used (no re-encode, instant).
- If **any** xfade transition exists, the entire video is re-encoded through filter_complex (slower but necessary).

### How to Test
1. Set all scenes to "Hard Cut" → render full video → should be fast (concat copy).
2. Set one scene to "Crossfade" → render full video → should show a smooth fade at that transition point. Video will take longer to render (re-encode).
3. Try "Slide Left" → the incoming scene should slide in from the right, pushing the previous scene out to the left.
4. Mix transitions: some hard cut, some crossfade, some slide → all should work together.

---

## 7. Script Generation — Multi-Frame Prompts

### What Changed
- The scriptwriter system prompt now instructs Claude to output `frame_count` and `frame_prompts` per scene instead of `is_animated` and `visual_prompt_b`.
- Budget guidelines:
  - Title/hook scenes: 6-8 frames
  - Key stat/dramatic: 4-5 frames
  - Standard explanation: 2-3 frames
  - Filler/transition: 1-2 frames
- Title card scenes should have `frame_count: 0` and empty `frame_prompts`.
- The `visual_prompt` field remains as the primary summary description.
- `animated_scene_count` is still accepted in the API request schema but **ignored** in prompt construction.

### How to Test
1. Generate a new script → each non-title scene should have `frame_count` (1-8) and matching `frame_prompts`.
2. Title card scenes should have `frame_count: 0` or missing.
3. Frame prompts should describe a **progression** — not random unrelated images.
4. The `visual_prompt` should be a summary that still makes sense as a standalone description.
5. Load the script in the storyboard → frame budget slider should reflect Claude's `frame_count`, frame prompt textareas should be pre-filled.

---

## 8. Backward Compatibility Checklist

| Scenario | Expected Behavior |
|----------|-------------------|
| Load old script (no frame fields) | All new fields default: frame_count=0, frame_prompts=[], etc. Scene renders as single image. |
| Old script with `is_animated: true` | Legacy A/B path works. PropertiesPanel shows "Legacy A/B Flip" section with convert button. |
| Generate image for legacy scene | Uses single-image `generate_scene_image()`. No frame files created. |
| Render legacy scene video | Uses `build_scene_video_cmd()` or `build_animated_scene_video_cmd()` as before. |
| `animated_scene_count` in API request | Still accepted, just ignored in prompt construction. No error. |
| Brand without `style_string` | Migration adds empty column. Image gen proceeds without style_string prefix. |
| Full video with no scene_transition values | Uses fast concat demuxer (same as before). |

---

## 9. File Layout Reference

### Generated Frame Images
```
data/projects/{script_id}/images/
  {scene_id}.png              # Legacy single image (or first frame alias)
  {scene_id}.prompt           # Legacy prompt cache
  {scene_id}_b.png            # Legacy B image (A/B flip)
  {scene_id}_b.prompt         # Legacy B prompt cache
  {scene_id}_f0.png           # Multi-frame: frame 0
  {scene_id}_f0.prompt        # Multi-frame: frame 0 prompt cache
  {scene_id}_f1.png           # Multi-frame: frame 1
  {scene_id}_f1.prompt        # Multi-frame: frame 1 prompt cache
  ...
```

### Rendered Videos
```
data/projects/{script_id}/renders/
  scenes/{scene_id}.mp4       # Individual scene video
  full_youtube.mp4            # Concatenated full video
  tiktok/{segment_idx}.mp4    # Per-segment TikTok clips
```

---

## 10. Known Limitations & Edge Cases

1. **Seed only works with Replicate/Flux.** Google Gemini ignores the seed parameter — frames may look visually different despite the same seed.

2. **xfade transition timing is approximate.** Scene-to-scene xfade uses `offset=eof-0.4` which relies on FFmpeg correctly detecting clip end. If clips have slightly mismatched durations, the crossfade timing may be slightly off.

3. **Re-encode penalty.** Any non-hard-cut scene transition forces the entire full video through filter_complex re-encode. For a 30-minute video with one crossfade, this is slower than pure concat copy.

4. **Frame count upper limit.** The slider goes to 8. More frames = more API calls = longer generation time. A scene with 8 frames and 10s audio means each frame shows for ~1.3 seconds with 0.4s crossfades.

5. **Short scenes with many frames.** If `(total_duration + (N-1)*0.4) / N < 0.5`, frames will be very brief. The code clamps to `crossfade_duration + 0.1 = 0.5s` minimum per frame, so the total video may be slightly longer than the audio.

6. **TikTok/shortform rendering.** Multi-frame scenes are rendered at 16:9 first, then converted to 9:16 with blurred background. The crossfade transitions happen in the 16:9 stage.
