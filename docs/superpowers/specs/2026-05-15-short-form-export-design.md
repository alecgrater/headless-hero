---
title: Short Form Export
date: 2026-05-15
status: draft
---

# Short Form Export

Export a project as 8 standalone vertical short-form videos — one per segment — at 1080×1920 / 30 FPS, fully re-laid-out for the 9:16 frame rather than mechanically refitted from the 1920×1080 long-form video.

## Goals

- Produce 8 platform-native short-form MP4s per project (TikTok / Reels / YouTube Shorts).
- Re-design every visual element (image, subtitles, Eli, title card, FX, transitions) for the 9:16 frame; nothing is letterboxed or cropped from the long-form output.
- Hook each short with a strong intro: a redesigned title card that names the series and the segment, with a freshly generated voiceover.
- Keep the operation self-service inside the existing Export panel; warn the user if pre-requisites are missing.

## Non-Goals

- Regenerating the per-scene narration audio. The existing scene VOs are reused as-is.
- Regenerating images (Gemini calls). The existing per-scene 1920×1080 images and per-segment square images are reused.
- Publishing shorts directly to social platforms (out of scope).
- Adapting "long-form-only" overlays (chapter map zoom, chapter indicator bar, segment timer, segment counter). These are stripped from shorts.

---

## Output

- Format: 1080×1920, 30 FPS, H.264 MP4.
- Count: exactly one short per segment (typically 8).
- Destination: `~/Downloads/{sanitized project name}/` (folder is created if missing — same pattern as the long-form export).
- Filenames: `[short form N/8] {sanitized project name}.mp4`, N = 1..8.
- Behavior: clicking render always overwrites the destination file. The intermediate Remotion render cached at `data/projects/{script_id}/renders/shorts/{N}.mp4` is recomputed only if a source asset (intro audio, scene audio, image) has a newer mtime.

---

## Composition per Short

Each short is structured as:

1. **Title card scene** (~3–5 s, duration = generated intro VO duration).
2. **Segment narration scenes** in order, each rendered with the standard vertical layout described below.

What is stripped vs. the long-form composition:

- No animated chapter map zoom.
- No global chapter indicator bar.
- No segment timer.
- No segment counter.

What is kept:

- Per-scene `transition_in` (cut / fade_black / flash_white / wipe) — Claude already assigned these for visual rhythm.
- Per-scene `zoom_punch` FX, applied to the middle image zone only (blur bands stay still).
- "aha subtitle" scenes (the dramatic glow-orb word-reveal scenes) — same component, with a font-size ramp re-tuned for vertical width (see Subtitle Re-Tuning).

---

## Vertical Scene Layout (narration scenes)

The 1080×1920 frame is partitioned vertically into three zones derived from the existing 1920×1080 image, scaled to fit width:

```
+--------------------------+  y=0
|                          |
|   TOP BLURRED BAND       |  ~656 px tall
|   (blur + dimmed copy    |
|    of focal image)       |
|                          |
|   [ Eli overlay,         |
|     top-center,          |
|     ~380×380 ]           |
|                          |
+--------------------------+  y≈656
|                          |
|   FOCAL IMAGE            |  ~608 px tall
|   (1080×608, scaled      |    (16:9 source @ 1080w)
|    16:9 source)          |
|                          |
+--------------------------+  y≈1264
|                          |
|   BOTTOM BLURRED BAND    |  ~656 px tall
|   (blur + dimmed copy    |
|    of focal image)       |
|                          |
|   [ Subtitles overlay    |
|     centered in band ]   |
|                          |
+--------------------------+  y=1920
```

Rendering rules:

- Top and bottom blur bands display the same source image scaled to cover their band, with CSS `filter: blur(40px) brightness(0.4) saturate(0.6)` (final values to be tuned visually — the goal is dim enough that white text overlays with high contrast).
- The focal image is the unmodified source, scaled to 1080w with `object-fit: cover` cropping any extra height bleed (typically none since source is 16:9 = ~607 h at 1080 w).
- Eli is positioned absolutely at the top center of the upper blur band (no longer corner PIP).
- Subtitles are positioned in the bottom blur band, centered horizontally and vertically within the band.

### Eli adjustments

- Default short-form position: top-center (override of the long-form corner PIP).
- Default short-form size: 380×380 (larger than long-form ~250×250 because the upper blur band has the room and we want more emotional connection in shorts).
- `contains_person` suppression rule still applies: if the focal image already contains Eli, the overlay is disabled for that scene.

### Multi-frame and subtitle-frame scenes

Multi-frame scenes (crossfading multiple `_fX.png` images) work unchanged — the focal-image slot becomes a crossfade region instead of a static image. Frames marked `source: subtitle` in `frame_directives` render text-on-black inside the focal slot as before.

---

## Title Card Scene

The title card is fully redesigned for shorts.

### Backdrop

- Source: the existing per-segment square illustration at `data/projects/{script_id}/images/title_card_{idx}.png` (already generated by the long-form title-card pipeline).
- Scaled to fill the full 1080×1920 frame with `object-fit: cover` (the square will be center-cropped vertically since it's wider than tall after scaling to 1080w; the cover behavior keeps it full-bleed).
- A darken / blur layer (`filter: blur(20px) brightness(0.5)` or similar — tuned visually) is applied across the entire frame so text reads cleanly. No Eli on title cards.

### Text content

- Build a single display string: `"{stripped_title} — {segment.name}"`.
- `stripped_title` = the video title with leading digits + whitespace removed. Regex: `^\d+\s+`. Examples:
  - `"8 Unsolved Crimes That Still Baffle Detectives to This Day"` → `"Unsolved Crimes That Still Baffle Detectives to This Day"`.
  - `"How to Train Your Dragon"` → `"How to Train Your Dragon"` (no leading digits, no change).
- Em-dash separator (`"—"`) is the spoken/visual handoff between the title and the segment name.

### Text layout (two-zone)

```
+--------------------------+  y=0
|                          |
|   ZONE 1: TITLE          |
|   "Unsolved Crimes That  |  Smaller (~64 px),
|    Still Baffle ..."     |  secondary weight,
|                          |  centered, neutral color
+--------------------------+  y=960  (mid-frame)
|                          |
|   ZONE 2: SEGMENT NAME   |
|   "The Isdal Woman"      |  Larger (~110 px),
|                          |  primary weight,
|                          |  accent color
|                          |
+--------------------------+  y=1920
```

- Zone 1 (title) occupies roughly the upper half; Zone 2 (segment name) the lower half.
- Both zones reveal **word-by-word** synced to the new intro VO's `word_timestamps`, using the same animation primitive as the existing `SubtitleScene` aha-moment reveal (spring scale + Y translate + opacity ramp per word).
- The em-dash itself is not rendered as a word; it's the implicit handoff from Zone 1 to Zone 2 in the text stream.
- The word-to-zone assignment is determined by the index of the em-dash in the display string: words before the em-dash → Zone 1; words after → Zone 2.

### Voiceover

- New ElevenLabs call per segment, voicing the display string verbatim (em-dash spoken as a natural pause).
- Stored at `data/projects/{script_id}/audio/short_intro_{idx}.mp3` with sidecar `word_timestamps`.
- Title card scene duration = generated VO duration (no padding).

---

## Subtitle Re-Tuning

Subtitles in shorts overlay the bottom blur band (centered within ~656 px of vertical space and the full 1080 px width). The visual style (gradient text, glow shadow) is preserved.

- Increase the default font size ramp for the narrower line width. Proposed starting values, to be tuned visually:
  - `< 40` chars → 96 px (was 96 in long-form)
  - `< 80` chars → 80 px (was 72)
  - `≥ 80` chars → 64 px (was 56)
- Max-width tightens from `85%` to `92%` since we have less horizontal room.
- The same per-word reveal animation runs against the existing scene `word_timestamps` — no new audio generation needed for narration scenes.

The same retuning applies to the "aha subtitle" full-frame scenes, with the caveat that those scenes don't have the band split — they occupy the full vertical frame with centered text.

---

## Voiceover Generation Flow (intros)

Short-form intros are generated as a separate, explicit step in the project UI.

### Backend

- New endpoint: `POST /api/voice/generate-short-intros` — starts a background job that, for each segment, builds the display string and calls ElevenLabs to produce `short_intro_{idx}.mp3` + `word_timestamps`.
- New endpoint: `POST /api/voice/generate-short-intro/{segment_idx}` — single-segment re-generation.
- Job status via existing `/api/voice/...` polling pattern (mirror `voice/generate-batch`).
- Stored in `script_json` as a new field on `ScriptContent`:

  ```python
  short_intros: list[ShortIntro] | None
  # ShortIntro = { segment_idx: int, audio_url: str, duration_seconds: float,
  #                word_timestamps: list[dict], display_text: str }
  ```

- Idempotent: if `short_intros[i]` already exists and the underlying title/segment_name strings haven't changed, the regenerate-all action skips it (single-segment regenerate is force).

### Frontend

The Short Form export tab is structured as **two stacked cards**:

1. **Card 1 — "Short Form Intros"**
   - Status header: `"8/8 generated"` (green) or `"0/8 generated — required before render"` (amber).
   - List of 8 rows, one per segment: segment name, display-text preview, audio scrubber (when generated), per-row "Generate" / "Regenerate" button.
   - Top-level button: `"Generate All Intros"` (or `"Regenerate All"` if all present).
   - During generation, shows a progress bar with per-segment current step.

2. **Card 2 — "Render Shorts"**
   - Disabled state if intros < 8/8, with a warning banner: *"Generate short-form intro voiceovers first."* The card body is dimmed and buttons are inert.
   - When intros complete:
     - Top-level button: `"Render All 8 Shorts"` (sequential render, single progress bar that updates label to "Rendering short N/8").
     - List of 8 rows mirroring card 1: per-row preview thumbnail (first frame), per-row "Render" / "Re-render" button, per-row download / show-in-folder link once rendered.
   - If the user clicks any render action while intros are missing (e.g., via a stale state), a confirm modal appears:
     - Title: *"Generate intros first?"*
     - Body: *"You haven't generated short-form intro voiceovers yet. They're required for the title cards. Generate now and then render?"*
     - Buttons: *"Generate & Render"* (chains the two operations) / *"Cancel"*.

### Visibility outside the tab

Add a status pill to the Timeline page header (next to the existing render/export indicators), showing `"Short Form: intros X/8 · renders X/8"`. Clicking the pill opens the Export panel on the Short Form tab.

---

## Export Panel UI Changes

Rename the existing `"Render"` tab to `"Render - Long Form"` with a one-line description directly under the tab heading:

> *Renders the full long form video at 1920×1080 16:9 30FPS.*

Add a new tab `"Render - Short Form"` with the description:

> *Renders 8 short form videos, corresponding to the 8 segments. 1080x1920 9:16 30FPS.*

`TABS` array becomes: `render-long`, `render-short`, `thumbnails`, `seo`. Tab badge for `render-short` lights up green when all 8 shorts are rendered.

The existing `"Export All"` button in the panel header continues to operate on the long-form pipeline only — short-form rendering is initiated from inside the Short Form tab. (Bundling shorts into "Export All" is out of scope for this iteration.)

---

## Architecture

### Python (backend)

New module `backend/pipeline/short_form_render.py`:

- `render_short_segment(script_id, segment_idx, content, brand, on_progress) -> str` — renders a single short, returns web-relative path.
- `render_all_shorts(script_id, content, brand, on_progress) -> list[str]` — sequential wrapper, reports overall progress.
- Internally:
  - Builds Remotion input props for one segment (intro + narration scenes).
  - Calls `_run_remotion(composition_id="ShortFormVideo", ...)` with `width=1080, height=1920`.
  - Re-encodes via the existing `_reencode_h264` helper.
  - Copies to `~/Downloads/{project}/[short form N/8] {project}.mp4` using a small adaptation of the existing `_copy_to_downloads` helper (the helper writes `dest_name` into a folder named after `title`; we'll pass the formatted short filename as `dest_name`).

New module `backend/pipeline/short_form_intros.py`:

- `generate_short_intros(script_id, content, force=False) -> list[ShortIntro]` — orchestrates ElevenLabs calls per segment, writes audio + word_timestamps into `script_json`.
- `generate_short_intro(script_id, segment_idx, content) -> ShortIntro` — single segment.
- Title-stripping helper: `strip_leading_number(title: str) -> str` using `re.sub(r"^\d+\s+", "", title)`.

New API routes in `backend/api/render.py` (or a new `short_form.py`):

- `POST /api/render/short-form` → background job rendering all 8.
- `POST /api/render/short-form/{segment_idx}` → background job rendering one.
- `GET /api/render/short-form/status/{job_id}` → reuse the existing render-job status shape.

New API routes in `backend/api/voiceover.py`:

- `POST /api/voice/generate-short-intros` → background job generating 8 intros.
- `POST /api/voice/generate-short-intro/{segment_idx}` → single segment.
- Status via existing render-job pattern.

`backend/models/script.py`:

- Add `ShortIntro` pydantic model.
- Add `short_intros: list[ShortIntro] | None = None` to `ScriptContent`.

### Remotion (renderer)

New composition registered in `remotion/src/Root.tsx`:

```ts
<Composition
  id="ShortFormVideo"
  component={ShortFormVideo}
  fps={30}
  width={1080}
  height={1920}
  durationInFrames={300}
  defaultProps={{...}}
  calculateMetadata={({ props }) => {
    // intro_duration + sum(scene durations) — no chapter transitions
  }}
/>
```

New file `remotion/src/ShortFormVideo.tsx`:

- Sequences: title card (duration = `intro.duration_seconds`) → each segment scene back-to-back.
- No `AnimatedChapterMap`, no `ChapterIndicator`, no `SegmentTimer`, no `SegmentCounter`.
- Passes a new `orientation: "vertical"` flag (or `mode: "short"`) down to scene renderers so they can switch layouts.

New scene component `remotion/src/scenes/ShortTitleCardScene.tsx`:

- Renders the segment image with `object-fit: cover` fill + darken/blur overlay.
- Splits display text on the em-dash, renders two zones with the existing per-word reveal animation from `SubtitleScene`.

Layout wrapper `remotion/src/scenes/VerticalSceneLayout.tsx`:

- Wraps the existing `StaticImageScene` / `MultiFrameScene` / `SubtitleScene` outputs.
- Renders the top blur band, focal image slot, bottom blur band.
- Positions Eli overlay top-center in the top band.
- Positions subtitle layer inside the bottom band.
- For "aha subtitle" full-frame scenes, bypasses the band split and uses the full vertical frame (these scenes have no focal image anyway).

Updates to existing components:

- `SceneRenderer` — accepts an `orientation` prop; when `vertical`, wraps the output in `VerticalSceneLayout` and passes a layout context that subtitle/Eli sub-components read for positioning + sizing.
- `SubtitleScene` font-size ramp — accept an `orientation` prop and switch the `getFontSize` ramp.
- Eli overlay component — accept an `orientation` prop and switch position from corner to top-center + scale to 380×380.
- Zoom-punch — scoped to the focal image slot (already inside `VerticalSceneLayout`), so no scope change needed beyond confirming the punch only animates the focal image element, not the band backgrounds.

### Frontend (React)

New components under `frontend/src/components/timeline/short-form/`:

- `ShortFormTab.tsx` — the new export-panel tab, composes the two cards.
- `ShortIntrosCard.tsx` — card 1: status header, per-segment list, generate buttons.
- `RenderShortsCard.tsx` — card 2: render-all + per-segment renders + downloads.
- `ShortFormStatusPill.tsx` — header pill on the Timeline page.

`frontend/src/api.ts`:

- `generateShortIntros()` / `generateShortIntro(segmentIdx)`.
- `getShortIntroStatus(jobId)`.
- `renderShortFormAll()` / `renderShortFormOne(segmentIdx)`.
- `getShortFormRenderStatus(jobId)`.

`frontend/src/types/render.ts`:

- Add `ShortIntro` type matching the backend model.
- Extend `ScriptContent` (or wherever timeline state is typed) with `short_intros`.

`ExportPanel.tsx`:

- Update `TABS` array, rename existing render tab, add description rendering for the active tab.
- Add `render-short` tab body that mounts `<ShortFormTab />`.

---

## Edge Cases and Failure Modes

- **Project has != 8 segments.** Filename template still uses `N/M` where `M` is the actual segment count (e.g., `[short form 3/6]`). Tab title remains "Render - Short Form"; the description text is generic ("one per segment") rather than hard-coded "8".
- **A segment has only the title card scene (no narration).** The short is just the title card — still rendered, still exported. UI displays the row normally.
- **A segment's narration scene has no audio.** Falls through the existing render path that uses `duration_estimate_seconds` when `audio_duration_seconds == 0`. No special handling required.
- **User edits the project title or a segment name after generating intros.** The "Generate All Intros" button shows "Regenerate (stale)" when any current display string differs from the stored `display_text`. Per-row indicator flags exactly which intros are stale.
- **ElevenLabs intro generation fails for one segment.** That row stays in error state with a retry button; other segments are unaffected. Render card remains disabled until all 8 succeed (or user explicitly chooses to render only the segments with valid intros — V2; for V1 the gate is all-or-nothing).
- **Render fails partway through "Render All".** Already-rendered files remain on disk. Job status reports which segments completed and which failed. User can re-trigger via per-segment buttons.
- **Eli is in the focal image (`contains_person`).** Eli overlay disabled for that scene, same as long-form.
- **Source image missing for a scene.** Existing fallback path renders text-on-black; same behavior in vertical layout (the focal image slot renders the fallback).

---

## Risks and Open Questions

- **Visual tuning is non-trivial.** Blur/dim values, font ramps, Eli positioning, and the title-card text typography all need iteration in a real browser-preview render. Build a small dev affordance (e.g., a preview button in the Render Shorts card that renders one segment's first 5 seconds) to shorten the tuning loop.
- **Square per-segment image quality.** `title_card_{idx}.png` was generated at `SQUARE_IMAGE_SIZE` (1024×1024). When stretched to 1080×1920 with cover, slight upscaling occurs. Should be visually acceptable but verify on a real project before locking in.
- **Subtitle highlight feature interaction.** The long-form `subtitle_highlight_enabled` toggle is currently passed through to `SceneRenderer`. Decide whether shorts inherit this toggle or always run with subtitle highlights on (assumption: inherit, no special handling).
- **Background music / global audio.** No global music exists in long-form; if it's added later, the short-form render path must be updated to include it for shorts as well.

---

## Acceptance Criteria

- "Render - Long Form" and "Render - Short Form" tabs both present in the Export panel with the specified descriptions.
- Short Form tab renders the two-card UI; render is gated on intros until all 8 are generated.
- "Generate All Intros" produces 8 MP3 files with word_timestamps; status pill on the timeline reflects the count.
- "Render All 8 Shorts" produces 8 MP4 files in `~/Downloads/{project}/` with the exact filename pattern, each 1080×1920 / 30 FPS / H.264.
- Each short opens with a title card whose audio reads "{stripped title} — {segment name}", whose text appears word-by-word in two zones synced to that audio, with the title image as a darkened/blurred backdrop and no Eli.
- Each narration scene in the short displays the focal image in the middle band, blurred-dim copies of that image in the top and bottom bands, Eli top-center, and subtitles centered in the bottom band.
- Per-scene transitions and zoom-punch FX render correctly in vertical.
- "aha subtitle" scenes use the retuned font ramp and render in the full vertical frame.
- Stripped: no chapter map zoom, no global progress bar, no segment timer, no segment counter in any short.
- Re-clicking render overwrites the destination file.
