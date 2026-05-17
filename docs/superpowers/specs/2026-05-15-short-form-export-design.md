---

title: Short Form Export  
date: 2026-05-15  
status: draft

---

# Short Form Export

Export a project as 8 standalone vertical short-form videos — one per segment — at 1080×1920 / 30 FPS, fully re-laid-out for the 9:16 frame rather than mechanically refitted from the 1920×1080 long-form video.

## Goals

*   Produce 8 platform-native short-form MP4s per project (TikTok / Reels / YouTube Shorts).
*   Re-design every visual element (image, subtitles, Eli, title card, FX, transitions) for the 9:16 frame; nothing is letterboxed or cropped from the long-form output.
*   Hook each short with a strong intro: a redesigned vertical title card whose backdrop is the segment's square illustration and whose text reveals the segment name with a punchy entrance.
*   Reuse all existing assets — no new voiceover generation, no new image generation. Render is one click from inside the Export panel.

## Non-Goals

*   Regenerating any audio. The existing per-scene VOs (including the first scene of each segment, which is already a title card with narration that names the segment) are reused as-is.
*   Regenerating images (Gemini calls). The existing per-scene 1920×1080 images and per-segment square illustrations are reused.
*   Publishing shorts directly to social platforms (out of scope).
*   Adapting "long-form-only" overlays (chapter map zoom, chapter indicator bar, segment timer, segment counter). These are stripped from shorts.

---

## Output

*   Format: 1080×1920, 30 FPS, H.264 MP4.
*   Count: exactly one short per segment (typically 8).
*   Destination: `~/Downloads/{sanitized project name}/` (folder is created if missing — same pattern as the long-form export).
*   Filenames: `[short form N/8] {sanitized project name}.mp4`, N = 1..8.
*   Behavior: clicking render always overwrites the destination file. The intermediate Remotion render cached at `data/projects/{script_id}/renders/shorts/{N}.mp4` is recomputed only if a source asset (scene audio, image) has a newer mtime.

---

## Composition per Short

Each short is structured as:

1.  **Title card scene** — the segment's existing first scene (`is_title_card=True`), re-laid-out for vertical with the special title-card visual (see Title Card Scene). Duration = the scene's existing `audio_duration_seconds`.
2.  **Remaining segment scenes** in order, each rendered with the standard vertical layout described below.

What is stripped vs. the long-form composition:

*   No animated chapter map zoom.
*   No global chapter indicator bar.
*   No segment timer.
*   No segment counter.

What is kept:

*   Per-scene `transition_in` (cut / fade\_black / flash\_white / wipe) — Claude already assigned these for visual rhythm.
*   Per-scene `zoom_punch` FX, applied to the middle image zone only (blur bands stay still).
*   "aha subtitle" scenes (the dramatic glow-orb word-reveal scenes) — same component, with a font-size ramp re-tuned for vertical width (see Subtitle Re-Tuning).

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

*   Top and bottom blur bands display the same source image scaled to cover their band, with CSS `filter: blur(40px) brightness(0.4) saturate(0.6)` (final values to be tuned visually — the goal is dim enough that white text overlays with high contrast).
*   The focal image is the unmodified source, scaled to 1080w with `object-fit: cover` cropping any extra height bleed (typically none since source is 16:9 = ~607 h at 1080 w).
*   Eli is positioned absolutely at the top center of the upper blur band (no longer corner PIP).
*   Subtitles are positioned in the bottom blur band, centered horizontally and vertically within the band.

### Eli adjustments

*   Default short-form position: top-center (override of the long-form corner PIP).
*   Default short-form size: 380×380 (larger than long-form ~250×250 because the upper blur band has the room and we want more emotional connection in shorts).
*   `contains_person` suppression rule still applies: if the focal image already contains Eli, the overlay is disabled for that scene.

### Multi-frame and subtitle-frame scenes

Multi-frame scenes (crossfading multiple `_fX.png` images) work unchanged — the focal-image slot becomes a crossfade region instead of a static image. Frames marked `source: subtitle` in `frame_directives` render text-on-black inside the focal slot as before.

---

## Title Card Scene

The title card scene is the segment's existing first scene (`is_title_card=True`). The audio and duration come from that scene's existing narration recording — no new ElevenLabs call. Only the visual is redesigned for vertical.

### Backdrop

*   Source: the existing per-segment square illustration at `data/projects/{script_id}/images/title_card_{idx}.png` (already generated by the long-form title-card pipeline).
*   Scaled to fill the full 1080×1920 frame with `object-fit: cover` (the square will be center-cropped vertically since it's wider than tall after scaling to 1080w; the cover behavior keeps it full-bleed).
*   A darken / blur layer (`filter: blur(20px) brightness(0.5)` or similar — tuned visually) is applied across the entire frame so text reads cleanly. No Eli on title cards.

### Text content

*   Two on-screen strings, no joining:
    *   Upper zone: `stripped_title` — the project title with leading digits + whitespace removed. Regex: `^\d+\s+`. Examples: `"8 Unsolved Crimes That Still Baffle Detectives to This Day"` → `"Unsolved Crimes That Still Baffle Detectives to This Day"`; `"How to Train Your Dragon"` → unchanged.
    *   Lower zone: `segment.name` (e.g., `"The Isdal Woman"`).
*   Neither string is spoken by a dedicated VO — the scene's existing narration audio plays underneath.

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

### Reveal animation

The reveal is "all at once" per zone — no word-by-word ramp.

*   `t = 0`: stripped title appears instantly in the upper zone (no entrance animation, just on). It holds static for the rest of the scene.
*   `t = TITLE_CARD_BEAT_SECONDS` (constant, ~0.5 s): segment name pops into the lower zone with a one-shot flourish:
    *   Spring scale: 0.6 → 1.05 → 1.0 (overshoot then settle).
    *   Opacity: 0 → 1 over ~120 ms.
    *   Glow burst: a radial flare behind the text that blooms to ~1.4× the text bounding box and fades to 0 over ~400 ms.
*   After the flourish, the segment name holds static. The scene's existing audio continues playing through to its natural end.

### Duration

*   Scene duration = the existing scene's `audio_duration_seconds`. No padding, no new audio source.
*   If the audio is shorter than `TITLE_CARD_BEAT_SECONDS + flourish duration`, the flourish still completes (the visual outlasts the audio by a few frames at most — fine).

### Voiceover

*   None generated. The scene's existing narration plays as-is.
*   Note: the existing title-card-scene narration is whatever Claude wrote (defaults to `"Welcome to {seg.name}."` if absent). The spoken segment name and the on-screen segment name will match, but the audio may contain additional words. The pop-in is timed by constant, not synced to a specific word in the audio.

---

## Subtitle Re-Tuning

Subtitles in shorts overlay the bottom blur band (centered within ~656 px of vertical space and the full 1080 px width). The visual style (gradient text, glow shadow) is preserved.

*   Increase the default font size ramp for the narrower line width. Proposed starting values, to be tuned visually:
    *   `< 40` chars → 96 px (was 96 in long-form)
    *   `< 80` chars → 80 px (was 72)
    *   `≥ 80` chars → 64 px (was 56)
*   Max-width tightens from `85%` to `92%` since we have less horizontal room.
*   The same per-word reveal animation runs against the existing scene `word_timestamps` — no new audio generation needed for narration scenes.

The same retuning applies to the "aha subtitle" full-frame scenes, with the caveat that those scenes don't have the band split — they occupy the full vertical frame with centered text.

---

## Export Panel UI Changes

Rename the existing `"Render"` tab to `"Render - Long Form"` with a one-line description directly under the tab heading:

> _Renders the full long form video at 1920×1080 16:9 30FPS._

Add a new tab `"Render - Short Form"` with the description:

> _Renders 8 short form videos, corresponding to the 8 segments. 1080x1920 9:16 30FPS._

`TABS` array becomes: `render-long`, `render-short`, `thumbnails`, `seo`. Tab badge for `render-short` lights up green when all 8 shorts are rendered.

The existing `"Export All"` button in the panel header continues to operate on the long-form pipeline only — short-form rendering is initiated from inside the Short Form tab. (Bundling shorts into "Export All" is out of scope for this iteration.)

### Short Form tab body

A single card, "Render Shorts":

*   Top-level button: `"Render All N Shorts"` (sequential render, single progress bar that updates label to "Rendering short N/M").
*   List of N rows, one per segment: segment name, per-row preview thumbnail (first frame), per-row "Render" / "Re-render" button, per-row download / show-in-folder link once rendered.
*   No prerequisites — render is always available since all required assets (per-segment images, narration audio) exist as soon as the long-form pipeline has run.
*   If a required asset is missing for a particular segment (e.g., title-card image not yet generated, narration audio missing), that row is disabled with an inline message naming the missing asset and a hint to run the long-form pipeline first.

### Visibility outside the tab

Add a status pill to the Timeline page header (next to the existing render/export indicators), showing `"Short Form: X/N rendered"`. Clicking the pill opens the Export panel on the Short Form tab.

---

## Architecture

### Python (backend)

New module `backend/pipeline/short_form_render.py`:

*   `render_short_segment(script_id, segment_idx, content, brand, on_progress) -> str` — renders a single short, returns web-relative path.
*   `render_all_shorts(script_id, content, brand, on_progress) -> list[str]` — sequential wrapper, reports overall progress.
*   Internally:
    *   Builds Remotion input props for one segment (the segment's existing scenes, with the first scene rendered using the short-form title-card layout).
    *   Calls `_run_remotion(composition_id="ShortFormVideo", ...)` with `width=1080, height=1920`.
    *   Re-encodes via the existing `_reencode_h264` helper.
    *   Copies to `~/Downloads/{project}/[short form N/8] {project}.mp4` using a small adaptation of the existing `_copy_to_downloads` helper (the helper writes `dest_name` into a folder named after `title`; we'll pass the formatted short filename as `dest_name`).

Helper: `strip_leading_number(title: str) -> str` using `re.sub(r"^\d+\s+", "", title)` — used by the Remotion props builder to compute the upper-zone text.

New API routes in `backend/api/render.py` (or a new `short_form.py`):

*   `POST /api/render/short-form` → background job rendering all 8.
*   `POST /api/render/short-form/{segment_idx}` → background job rendering one.
*   `GET /api/render/short-form/status/{job_id}` → reuse the existing render-job status shape.

No new voiceover endpoints, no new pipeline modules for intros, no new fields on `ScriptContent`. The short-form render reads the segment's existing first scene (audio, duration, image) directly.

### Remotion (renderer)

New composition registered in `remotion/src/Root.tsx`:

```
<Composition
  id="ShortFormVideo"
  component={ShortFormVideo}
  fps={30}
  width={1080}
  height={1920}
  durationInFrames={300}
  defaultProps={{...}}
  calculateMetadata={({ props }) => {
    // sum(scene durations) — no chapter transitions, no separate intro segment
  }}
/>
```

New file `remotion/src/ShortFormVideo.tsx`:

*   Sequences: each segment scene back-to-back. The first scene of the segment (the existing title-card scene) is rendered via `ShortTitleCardScene`; subsequent scenes use the standard scene renderer wrapped in `VerticalSceneLayout`.
*   No `AnimatedChapterMap`, no `ChapterIndicator`, no `SegmentTimer`, no `SegmentCounter`.
*   Passes a new `orientation: "vertical"` flag (or `mode: "short"`) down to scene renderers so they can switch layouts.

New scene component `remotion/src/scenes/ShortTitleCardScene.tsx`:

*   Renders the per-segment square illustration (`title_card_{idx}.png`) with `object-fit: cover` fill + darken/blur overlay.
*   Plays the existing scene audio (passed in via props, same path as the long-form scene's narration audio).
*   Renders two static text zones: stripped long-form title (upper zone, instant on at frame 0) and segment name (lower zone, pop-in flourish at `TITLE_CARD_BEAT_SECONDS`).
*   Pop-in animation: spring scale 0.6 → 1.05 → 1.0, opacity 0 → 1 over ~120 ms, plus a one-shot radial glow burst that blooms to ~1.4× the text bounding box and fades to 0 over ~400 ms.

Layout wrapper `remotion/src/scenes/VerticalSceneLayout.tsx`:

*   Wraps the existing `StaticImageScene` / `MultiFrameScene` / `SubtitleScene` outputs.
*   Renders the top blur band, focal image slot, bottom blur band.
*   Positions Eli overlay top-center in the top band.
*   Positions subtitle layer inside the bottom band.
*   For "aha subtitle" full-frame scenes, bypasses the band split and uses the full vertical frame (these scenes have no focal image anyway).

Updates to existing components:

*   `SceneRenderer` — accepts an `orientation` prop; when `vertical`, wraps the output in `VerticalSceneLayout` and passes a layout context that subtitle/Eli sub-components read for positioning + sizing.
*   `SubtitleScene` font-size ramp — accept an `orientation` prop and switch the `getFontSize` ramp.
*   Eli overlay component — accept an `orientation` prop and switch position from corner to top-center + scale to 380×380.
*   Zoom-punch — scoped to the focal image slot (already inside `VerticalSceneLayout`), so no scope change needed beyond confirming the punch only animates the focal image element, not the band backgrounds.

### Frontend (React)

New components under `frontend/src/components/timeline/short-form/`:

*   `ShortFormTab.tsx` — the new export-panel tab body, mounts the single render card.
*   `RenderShortsCard.tsx` — render-all + per-segment renders + downloads.
*   `ShortFormStatusPill.tsx` — header pill on the Timeline page.

`frontend/src/api.ts`:

*   `renderShortFormAll()` / `renderShortFormOne(segmentIdx)`.
*   `getShortFormRenderStatus(jobId)`.

`frontend/src/types/render.ts`:

*   No new types beyond render-job status (already typed).

`ExportPanel.tsx`:

*   Update `TABS` array, rename existing render tab, add description rendering for the active tab.
*   Add `render-short` tab body that mounts `<ShortFormTab />`.

---

## Edge Cases and Failure Modes

*   **Project has != 8 segments.** Filename template still uses `N/M` where `M` is the actual segment count (e.g., `[short form 3/6]`). Tab title remains "Render - Short Form"; the description text is generic ("one per segment") rather than hard-coded "8".
*   **A segment has only the title card scene (no narration scenes after it).** The short is just the title card scene — still rendered, still exported. UI displays the row normally.
*   **A segment's scene has no audio.** Falls through the existing render path that uses `duration_estimate_seconds` when `audio_duration_seconds == 0`. No special handling required. For the title card scene specifically, if its audio is missing the scene still renders with the visual reveal, but with no sound; row UI flags this as "narration audio missing — generate voiceovers in the long-form tab first".
*   **Per-segment title-card image missing.** Render is blocked for that segment with an inline message ("Title card image missing — re-run long-form pipeline"); other segments are unaffected.
*   **User edits a segment name after the long-form audio was generated.** The short displays the new on-screen segment name in the lower zone but the audio still references the old name (since the existing title-card-scene narration was recorded against the old name). This is acceptable — same drift would affect the long-form. No special detection in V1.
*   **Render fails partway through "Render All".** Already-rendered files remain on disk. Job status reports which segments completed and which failed. User can re-trigger via per-segment buttons.
*   **Eli is in the focal image (`contains_person`).** Eli overlay disabled for that scene, same as long-form.
*   **Source image missing for a non-title scene.** Existing fallback path renders text-on-black; same behavior in vertical layout (the focal image slot renders the fallback).

---

## Risks and Open Questions

*   **Visual tuning is non-trivial.** Blur/dim values, font ramps, Eli positioning, and the title-card text typography (especially the segment name pop-in flourish) all need iteration in a real browser-preview render. Build a small dev affordance (e.g., a preview button in the Render Shorts card that renders one segment's first 5 seconds) to shorten the tuning loop.
*   **Square per-segment image quality.** `title_card_{idx}.png` was generated at `SQUARE_IMAGE_SIZE` (1024×1024). When stretched to 1080×1920 with cover, slight upscaling occurs. Should be visually acceptable but verify on a real project before locking in.
*   **Title-card-scene audio content varies.** The existing title-card-scene narration is whatever Claude wrote — usually `"Welcome to {seg.name}."` or a similar single sentence, but occasionally longer. The pop-in is timed by `TITLE_CARD_BEAT_SECONDS` constant, not audio-synced, so the visual reveal looks right regardless. If we later want the pop-in to land on the moment the segment name is spoken, the existing scene's `word_timestamps` make that possible — out of scope for V1.
*   **Subtitle highlight feature interaction.** The long-form `subtitle_highlight_enabled` toggle is currently passed through to `SceneRenderer`. Decide whether shorts inherit this toggle or always run with subtitle highlights on (assumption: inherit, no special handling).
*   **Background music / global audio.** No global music exists in long-form; if it's added later, the short-form render path must be updated to include it for shorts as well.

---

## Acceptance Criteria

*   "Render - Long Form" and "Render - Short Form" tabs both present in the Export panel with the specified descriptions.
*   Short Form tab renders a single "Render Shorts" card. No intros card, no gating modal.
*   "Render All N Shorts" produces N MP4 files in `~/Downloads/{project}/` with the exact filename pattern, each 1080×1920 / 30 FPS / H.264.
*   Each short opens with a title-card scene that reuses the segment's existing first-scene audio. The stripped long-form title is visible statically in the upper zone from t=0; the segment name pops into the lower zone at `t = TITLE_CARD_BEAT_SECONDS` with a spring-scale + glow-burst flourish and then holds static.
*   Each non-title scene in the short displays the focal image in the middle band, blurred-dim copies of that image in the top and bottom bands, Eli top-center, and subtitles centered in the bottom band.
*   Per-scene transitions and zoom-punch FX render correctly in vertical.
*   "aha subtitle" scenes use the retuned font ramp and render in the full vertical frame.
*   Stripped: no chapter map zoom, no global progress bar, no segment timer, no segment counter in any short.
*   Re-clicking render overwrites the destination file.
*   No ElevenLabs calls are made by the short-form pipeline.
