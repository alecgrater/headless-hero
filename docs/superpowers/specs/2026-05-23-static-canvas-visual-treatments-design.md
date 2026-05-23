# Static Canvas Visual Treatments - Design Spec

## Context

Headless Hero currently treats most narration scenes as complete full-frame visuals: one generated scene image, multiple full-frame images, video clips, or full-screen `aha_subtitle` text. That model is compatible with traditional AI image generation, but it forces every scene to be a complete painting. It makes visual variety expensive, makes timing smaller visual beats harder, and does not match the simpler staged cartoon look we want for many videos.

The new direction is a global static canvas: every scene renders over one video-level background color. Legacy visuals still work because full-frame images and videos simply cover the canvas. New visual treatments can leave the canvas visible and layer smaller generated panels on top of it.

This first phase intentionally implements only the foundation plus three treatments:

- `full_frame`
- `popup_sequence`
- `flipflop`

The design must remain easy to extend with future treatments such as `aha_card`, `character_walkon`, and `thought_bubbles`.

## Goals

- Add an always-on static canvas beneath every scene.
- Store one global canvas color per project/video.
- Store a reusable app-level palette of previously selected canvas colors across projects.
- Add `visual_treatment` as a separate concept from `media_source`.
- Block visual treatment assignment until voiceover timing exists.
- Implement `full_frame`, `popup_sequence`, and `flipflop`.
- Generate smaller panel assets for layered treatments without requiring transparent cutouts.
- Add UI controls and explanatory blurbs so the feature is understandable in the timeline/media workflow.
- Add dev-dashboard logging for assignment, blocking, generation, render selection, cache hits, and fallbacks.
- Keep the schema extensible for later layer/action-based treatments.

## Non-Goals

- No `static_background_partial_scene` treatment in this phase.
- No `aha_card` implementation in this phase.
- No `character_walkon` implementation in this phase.
- No `thought_bubbles` implementation in this phase.
- No transparent cutout generation requirement in this phase.
- No manual raw layer editor in this phase.
- No per-segment canvas colors. The canvas color is one global value per video.

## Product Model

### Static Canvas

The static canvas is always present. It is not a separate mode users turn on and off. Each scene renders on top of it:

```text
StaticCanvas
TreatmentRenderer
Subtitles / Eli / overlays
Audio
```

For legacy scenes, the treatment renderer covers the canvas completely:

```text
StaticCanvas
Full-frame image or video
Subtitles / overlays
Audio
```

For layered scenes, the canvas remains visible:

```text
StaticCanvas
Panel 1 pops in
Panel 2 pops in
Panel 3 pops in
Subtitles / overlays
Audio
```

### Media Source vs Visual Treatment

`media_source` answers where the asset comes from.

Examples:

- `ai`
- `ai_video`
- `stock_photo`
- `gameplay_video`
- `user_upload`

`visual_treatment` answers how the scene is staged.

Phase 1 values:

```ts
type VisualTreatment = "full_frame" | "popup_sequence" | "flipflop";
```

Example scene state:

```json
{
  "media_source": "ai",
  "visual_treatment": "popup_sequence"
}
```

## Data Model

### ScriptContent

Add a video-level canvas object to `ScriptContent`:

```python
class VisualCanvas(BaseModel):
    background_color: str = "#F6C54A"
```

```python
class ScriptContent(BaseModel):
    visual_canvas: VisualCanvas = VisualCanvas()
```

The color must be normalized to uppercase six-digit hex, for example `#F6C54A`. Invalid values fall back to the app default and log a warning.

### App-Level Palette

Persist the cross-project color history in app settings. The implementation should use the existing settings storage pattern rather than adding a second settings system.

Recommended setting key:

```text
VISUAL_CANVAS_COLOR_PALETTE
```

Value shape:

```json
["#F6C54A", "#A7D8F0", "#F2EFE6"]
```

When the user selects a valid color:

1. Save it to the current script's `visual_canvas.background_color`.
2. Add it to the front of the app-level palette if missing.
3. Keep the palette deduped.
4. Keep a reasonable cap, such as the 24 most recent colors.

### Scene

Add treatment and layer fields:

```python
class VisualLayer(BaseModel):
    id: str
    type: str                         # "image" for Phase 1
    asset_kind: str = "panel"          # "full_frame" | "panel" | "cutout"
    image_url: str = ""
    prompt: str = ""
    placement: str = "center"          # "left" | "center" | "right" | grid/slot values later
    enter_at_seconds: float = 0.0
    exit_at_seconds: float | None = None
    animation: str = "none"            # "none" | "pop_in"
```

```python
class Scene(BaseModel):
    visual_treatment: str = "full_frame"
    visual_layers: list[VisualLayer] = []
```

The layer schema is intentionally broader than Phase 1. Later treatments can add layer types such as `text`, `bubble`, `shape`, and `character`, plus action types such as `orbit`, `shake`, `pulse`, and `crowd_in`.

### TypeScript Mirrors

Mirror the same fields in `frontend/src/types/script.ts` and `remotion/src/types.ts`.

`visual_treatment` should be typed as:

```ts
"full_frame" | "popup_sequence" | "flipflop"
```

Keep renderer-facing types permissive enough that old scripts without the field default to `full_frame`.

## Treatment Definitions

### `full_frame`

Default and backwards-compatible treatment.

Behavior:

- Existing image/video rendering covers the static canvas.
- Current `StaticImageScene`, `MultiFrameScene`, and `VideoScene` behavior remains available.
- Existing `visual_beat` values may continue to influence full-frame rendering until future cleanup.
- This treatment is valid for all formats and all media sources.

Use when:

- A scene benefits from a full environmental illustration.
- The scene uses stock photo, gameplay video, uploaded video, or AI video.
- The analyzer is uncertain.

### `popup_sequence`

A layered scene where two to four generated panels appear one by one on narration beats.

Behavior:

- Uses `asset_kind="panel"` image layers.
- Panels are rectangular mini-illustrations placed over the static canvas.
- Panels appear left-to-right for three items, or balanced around center for two/four items.
- Each panel pops in at a word/phrase-aligned timestamp.
- Once visible, panels stay visible through the end of the scene unless the generated plan explicitly exits them.
- Normal scene audio plays continuously.
- Standard bottom subtitles may stay enabled, but the implementation should watch for visual crowding in QA.

Use when:

- Narration contains a list, sequence, or repeated structure.
- The sentence has clear beats, such as "keep your head down, not express feelings, never be different."
- A single full-frame image would be too static or too literal.

Assignment signals:

- Comma-separated list items.
- Phrases joined by "and", "or", "then", "first/second/third".
- Repeated grammatical structure.
- Three short examples or consequences.

Layer example:

```json
[
  {
    "id": "panel_keep_head_down",
    "type": "image",
    "asset_kind": "panel",
    "prompt": "A small framed cartoon panel of a child keeping their head down at a school desk...",
    "placement": "left",
    "enter_at_seconds": 1.1,
    "animation": "pop_in"
  },
  {
    "id": "panel_hide_feelings",
    "type": "image",
    "asset_kind": "panel",
    "prompt": "A small framed cartoon panel of a child hiding their feelings...",
    "placement": "center",
    "enter_at_seconds": 2.3,
    "animation": "pop_in"
  },
  {
    "id": "panel_never_different",
    "type": "image",
    "asset_kind": "panel",
    "prompt": "A small framed cartoon panel of a child trying not to stand out...",
    "placement": "right",
    "enter_at_seconds": 3.5,
    "animation": "pop_in"
  }
]
```

### `flipflop`

A rhythmic two-state treatment that alternates between two complementary visuals every 0.5 seconds.

Behavior:

- Generates two complementary assets.
- Alternates A/B at a deterministic cadence, defaulting to every 0.5 seconds.
- Uses snappy cuts by default. A tiny scale or squash accent may be added in Remotion if it improves energy without causing visual jitter.
- Assets may be panels or full-frame compositions in the internal schema, but Phase 1 should start with panels unless a full-frame fallback is simpler for the existing renderer.

Use when:

- Narration expresses contrast, back-and-forth pressure, temptation, repetition, two emotional states, or before/after tension.
- The scene needs an animated feel but not true video generation.

Assignment signals:

- "On one hand / on the other hand."
- "Again and again."
- "Part of him wanted X, but part of him feared Y."
- "Every day looked the same."
- "Before / after."

Layer example:

```json
[
  {
    "id": "state_a",
    "type": "image",
    "asset_kind": "panel",
    "prompt": "A small framed cartoon panel showing the character trying to focus at work...",
    "placement": "center",
    "enter_at_seconds": 0.0,
    "animation": "none"
  },
  {
    "id": "state_b",
    "type": "image",
    "asset_kind": "panel",
    "prompt": "A matching cartoon panel showing the character overwhelmed by worries...",
    "placement": "center",
    "enter_at_seconds": 0.5,
    "animation": "none"
  }
]
```

## Voiceover Timing Gate

Visual treatment assignment must not run until every target scene has voiceover timing:

```text
audio_duration_seconds > 0
word_timestamps present and non-empty
```

This gate applies to UI-triggered analysis and API-triggered analysis.

If the user tries to analyze before voiceover exists:

- Disable the action or return a clear blocked response.
- Explain that visual treatments need voiceover timing so panels can appear on the right words.
- Log the blocked state to the dev dashboard.

This mirrors the existing rule that media analysis requires voiceover durations, but this feature also depends on word-level timing.

## Analyzer

Add a visual treatment analyzer separate from media source analysis. It can live near `backend/pipeline/media_analyzer.py` if that keeps UI workflows simple, but the responsibilities should stay distinct.

Inputs:

- Script content
- Scene narration
- Scene format
- Voiceover duration
- Word timestamps
- Existing media source

Outputs:

- `visual_treatment`
- `visual_layers`
- Optional reasoning string for the UI

Rules:

- `ai_video`, `gameplay_video`, `stock_photo`, and `user_upload` default to `full_frame` in Phase 1.
- Title cards stay `full_frame`.
- Scenes without word timestamps stay `full_frame` and log a warning if analysis was requested.
- `popup_sequence` requires two to four clear beats.
- `flipflop` requires a strong two-state or repetitive structure.
- `life-as-a` and `youtube-listicle` both support all Phase 1 treatments.
- In `life-as-a`, visual treatment prompts must respect active protagonist rules when panels show the protagonist.

LLM output should be validated and normalized. Unknown treatments become `full_frame`.

## Panel Generation

Phase 1 introduces panel generation, but not transparent cutouts.

Definitions:

- `full_frame`: complete 1920x1080 visual that covers the entire video frame.
- `panel`: smaller rectangular illustration placed on top of the static canvas.
- `cutout`: isolated transparent subject/object; deferred.

Panel prompt requirements:

- Use the same Headless Hero flat 2D cartoon style.
- Describe the panel as a small framed illustration, not a full video background.
- Keep the subject readable at smaller size.
- Avoid large text inside generated images.
- Avoid detailed backgrounds unless needed for comprehension.
- Preserve protagonist identity rules for `life-as-a` and Eli-disabled projects.

Example prompt template:

```text
Create a small framed Headless Hero cartoon illustration panel for a layered scene.
This panel will sit on a flat static color background, so it should read clearly at reduced size.
Do not design a full 1920x1080 background scene. Keep the composition simple, bold, and readable.
No text in the image unless explicitly requested.

Panel subject:
{panel_prompt}
```

Panel assets can be generated at a smaller stable aspect ratio, such as 4:3 or 1:1, then placed by Remotion. The first implementation may still generate them at the existing image size and crop/contain them in the renderer if that reduces risk, but the data model should treat them as panels.

## Remotion Rendering

Add `StaticCanvas`:

- Reads `visual_canvas.background_color` from composition props.
- Fills the full composition.
- Should work for horizontal and vertical renders.

Add `TreatmentRenderer` or extend `SceneRenderer` with a treatment dispatch:

```text
full_frame       -> existing visual dispatch
popup_sequence   -> layered panel renderer
flipflop         -> two-state alternating renderer
unknown/missing  -> full_frame
```

`popup_sequence` renderer:

- Computes stable slots by layer placement.
- Uses `enter_at_seconds` converted to frames.
- Applies `pop_in` with scale and opacity spring.
- Keeps layout dimensions stable so panels do not shift as they appear.

`flipflop` renderer:

- Alternates the two assets every 0.5 seconds.
- Uses scene frame/fps for deterministic timing.
- Falls back to first layer if only one valid image exists.
- Falls back to `full_frame` if no treatment assets exist.

Existing subtitles and overlays remain above the treatment renderer. Any future text-heavy treatment can opt out of standard subtitles, but Phase 1 does not need that behavior.

## Frontend UI

### Canvas Color Controls

Add a canvas color control near the timeline/media configuration surface. The exact placement can follow existing timeline panel organization, but it should be easy to reach before rendering.

Controls:

- Hex input.
- Live color swatch.
- `Select` button.
- Palette of previously selected colors as clickable swatches.
- Validation message for invalid hex input.

Suggested blurb:

```text
The canvas color sits behind every scene. Full-frame visuals cover it completely; popup and flipflop treatments let it show through.
```

Behavior:

- Typing a valid hex updates the swatch preview.
- `Select` saves the color to the current project and app palette.
- Clicking a saved swatch selects and saves that color.
- Palette persists across projects.

### Visual Treatment Controls

In the Media Source page or a nearby timeline tab, add a Visual Treatment section.

Suggested section blurb:

```text
Visual treatment controls how a scene is staged. Media source chooses where assets come from; treatment chooses how they appear on the canvas.
```

Treatment labels and blurbs:

- **Full frame**: "A normal scene image or video fills the whole frame and covers the canvas."
- **Popup sequence**: "Two to four small illustrated panels appear on narration beats, usually left to right."
- **Flipflop**: "Two complementary visuals alternate every half second for a simple animated feel."

UI states:

- Before voiceover: disable analysis and show "Generate voiceover first so treatments can sync to words."
- After voiceover: enable treatment analysis.
- During analysis: show progress and log messages.
- After analysis: show each scene's selected treatment with a short reason.
- Manual override: allow choosing `full_frame`, `popup_sequence`, or `flipflop` per scene.

Manual treatment override should preserve the user's choice unless they explicitly rerun analysis and accept replacement. If the existing app does not have an override/lock pattern yet, store a simple treatment source flag such as `visual_treatment_source: "auto" | "manual"` only if needed by the implementation.

### Scene Rows

Scene rows that currently show media source should also show visual treatment. Keep this compact:

```text
Media: AI
Treatment: Popup sequence
```

For video-backed scenes, suppress panel/frame counts and mark them as video scenes, consistent with the existing project rule.

## API

Add or extend endpoints to support:

- Get/set project canvas color.
- Get app-level canvas palette.
- Analyze visual treatments for a script.
- Apply visual treatment assignments.
- Manually update a scene's visual treatment.

The API should follow existing request/response naming conventions:

- `UpdateVisualCanvasRequest`
- `UpdateVisualCanvasResponse`
- `AnalyzeVisualTreatmentsRequest`
- `AnalyzeVisualTreatmentsResponse`
- `UpdateVisualTreatmentRequest`
- `UpdateVisualTreatmentResponse`

All endpoints auto-resolve brand/project context the same way existing script endpoints do. Do not add `brand_id` to request bodies.

## Dev Dashboard Logging

The dev dashboard already persists and streams Python logs. The implementation should add clear, searchable log prefixes so the new feature is easy to debug.

Recommended prefixes:

- `[VISUAL_CANVAS]`
- `[VISUAL_TREATMENT]`
- `[PANEL_GEN]`
- `[REMOTION_TREATMENT]`

Required log events:

- Canvas color updated: script id, old color, new color.
- Palette updated: added color, palette size.
- Treatment analysis requested: script id, scene count, format id.
- Treatment analysis blocked: missing audio durations, missing word timestamps, affected scene ids.
- Treatment selected per scene: scene id, treatment, brief reason, layer count.
- Treatment normalized/fallback: unknown treatment, invalid layer, missing timing, fallback target.
- Panel generation started: scene id, layer id, prompt summary.
- Panel cache hit: scene id, layer id.
- Panel generation complete: scene id, layer id, output path.
- Panel generation fallback/failure: scene id, layer id, exception summary.
- Remotion treatment dispatch: scene id, treatment, layer count.
- Remotion fallback: scene id, requested treatment, fallback reason.

These logs should use existing `logging.getLogger(__name__)` patterns so they automatically appear in the dev dashboard.

## Testing

Backend tests:

- Canvas color validation normalizes valid hex and rejects invalid values.
- Palette saves colors in most-recent-first order and dedupes.
- Treatment analysis blocks when audio duration is missing.
- Treatment analysis blocks when word timestamps are missing.
- Unknown treatment normalizes to `full_frame`.
- `popup_sequence` assignments contain two to four layers with increasing timings.
- `flipflop` assignments contain two layers.
- `life-as-a` scenes can receive Phase 1 treatments without violating protagonist prompt rules.

Frontend tests or manual QA:

- Hex input preview updates.
- Invalid hex shows a helpful message.
- Selecting a color saves it and adds it to palette.
- Treatment analysis is disabled before voiceover.
- Scene rows show media source and treatment separately.
- Manual override changes treatment.

Remotion verification:

- `full_frame` render matches current behavior.
- Static canvas is visible behind `popup_sequence`.
- Popup panels appear at the expected timestamps.
- `flipflop` alternates every 0.5 seconds.
- Missing/invalid layers fall back without crashing.
- Horizontal and vertical renders are nonblank and correctly framed.

## Rollout

1. Add data model and defaulting.
2. Add static canvas rendering under current scenes.
3. Add color UI and palette persistence.
4. Add treatment field and UI display.
5. Add voiceover timing gate.
6. Add analyzer for `full_frame`, `popup_sequence`, and `flipflop`.
7. Add panel generation path.
8. Add Remotion treatment renderers.
9. Add dev dashboard logging.
10. Add tests and render verification.

## Future Treatments

These treatments are intentionally out of scope for Phase 1, but the layer/action model should make them natural additions.

### `aha_card`

An `aha_card` is a static-canvas scene designed for a single emotional or intellectual punch. It usually combines one character, object, or panel on one side with large editorial text on the other. The text is not standard subtitles; it is a graphic emphasis layer. It should be short, bold, and readable at thumbnail scale, ideally two to seven words.

Visual style:

- Headless Hero flat 2D cartoon style.
- Text should feel hand-drawn or cartoon-editorial rather than corporate.
- Most letters are black.
- The most intense word or phrase is red.
- Text should have strong contrast against the canvas.
- The layout should avoid the bottom subtitle area unless standard subtitles are suppressed.

Timing:

1. Canvas appears.
2. Character/image/panel lands first.
3. Main phrase appears.
4. Red emphasis word snaps, pulses, or slightly shakes.
5. The composition holds long enough to read.

Good uses:

- Shocking realizations.
- Emotional labels.
- Reversals.
- Key claims.
- "This is the point" moments.

Future schema needs:

- `text` layers.
- Emphasis spans inside text.
- Optional standard subtitle suppression.
- Text animation actions such as `snap_in`, `pulse`, and `shake`.

Prompt seed:

```text
Create an aha-card visual treatment for this narration beat. Use the static canvas as the background. Place a simple character or panel on one side and large editorial text on the other. Keep the phrase short and graphic. Most words should be black; the most intense word or phrase should be red. The text should match a hand-drawn Headless Hero cartoon style and be readable at small size.
```

### `character_walkon`

A `character_walkon` is a staged performance scene. An isolated character slides in from the edge of frame, lands in a clear pose, reacts to the narration, then exits or holds. The scene should feel like a character acting on a simple stage, not a complete generated background.

Visual style:

- Static canvas remains visible.
- Character is a transparent cutout or sprite.
- Motion is produced in Remotion with transforms, not baked into generated video.
- Entrance can include slide, squash/stretch, and bounce.
- Idle can include slight sway or head tilt.
- Exit can mirror entrance or happen after a reaction beat.

Character rules:

- In `life-as-a`, use the active protagonist.
- If Eli is enabled, use Eli.
- If Eli is disabled, use the project-specific main character reference.
- Do not invent anonymous replacement protagonists.

Good uses:

- Introducing a role.
- Embodying a feeling.
- Reacting beside a panel.
- Pointing to text.
- Looking overwhelmed.
- Walking into a problem.
- Exiting after a punchline.

Future schema needs:

- `character` layers.
- Transparent cutout generation.
- Character reference selection.
- Actions such as `slide_in`, `hold`, `point`, `react`, `slide_out`.

Prompt seed:

```text
Create a character walk-on treatment. Use the static canvas as a simple stage. The active character enters from one edge, lands in a readable pose, reacts to the narration, and either holds or exits. The character must remain visually consistent with the project protagonist and should be generated as an isolated cutout suitable for Remotion animation.
```

### `thought_bubbles`

A `thought_bubbles` scene centers a character while multiple text bubbles appear around them in sync with list items or worries in the narration. After the bubbles appear, they can animate around the character to show mental pressure or competing priorities.

Example narration:

```text
The guy had a lot to worry about. Taxes, family, work.
```

Behavior:

1. Character appears in the center.
2. Bubble "taxes" pops in when that word is spoken.
3. Bubble "family" pops in on its word.
4. Bubble "work" pops in on its word.
5. During the next narration phrase, bubbles orbit, pulse, shake, crowd inward, or rearrange.

Visual style:

- Bubbles are Remotion-rendered, not generated text inside images.
- Text remains editable and crisp.
- Bubbles should feel hand-drawn and match the cartoon style.
- Keep bubble count readable, usually three to six.

Good uses:

- Anxiety.
- Competing priorities.
- Social pressure.
- Choices.
- Accusations.
- Rumors.
- Memories.
- Too many things happening at once.

Future schema needs:

- `bubble` layers.
- `text` layers inside bubbles.
- Word-aligned entry timing.
- Group actions such as `orbit`, `shake`, `crowd_in`, and `pulse`.

Prompt seed:

```text
Create a thought-bubbles treatment. Place the active character in the center on the static canvas. Identify the list items or worries in the narration, then create one editable text bubble for each item. Each bubble should appear when its word or phrase is spoken. After all bubbles appear, animate them to show pressure, such as orbiting, pulsing, shaking, or crowding inward.
```

### `cutout_reaction_stack`

A `cutout_reaction_stack` places several transparent cutout characters or symbolic objects around the static canvas as reactions to the narration. Unlike `popup_sequence`, these are not rectangular panels. They are isolated subjects that can scale, lean, shake, point, or crowd the frame.

Good uses:

- "Everyone reacted differently."
- Crowds.
- Social judgment.
- Comparison.
- Multiple symbolic objects around a protagonist.

Future schema needs:

- `cutout` asset generation.
- Multiple image layers with transparent backgrounds.
- Actions such as `pop_in`, `lean`, `shake`, `point`, and `crowd`.

Prompt seed:

```text
Create a cutout reaction stack. Use the static canvas as the background. Generate isolated cartoon cutouts for each reaction or symbolic object. Arrange them around the frame so they feel like reactions closing in on the main idea. Do not use rectangular panels.
```

### `diagram_build`

A `diagram_build` is an explanatory scene where simple shapes, arrows, labels, and small icons build over time. It should feel hand-drawn and editorial, not like a corporate slide.

Good uses:

- Systems.
- Cause and effect.
- Timelines.
- Feedback loops.
- "This led to that" explanations.

Future schema needs:

- `shape` layers.
- `arrow` layers.
- `label` layers.
- Icon or mini-panel layers.
- Actions such as `draw_on`, `connect`, `highlight`, and `rearrange`.

Prompt seed:

```text
Create a diagram-build visual treatment. Use the static canvas as the background. Build the explanation with hand-drawn arrows, labels, simple shapes, and small cartoon icons. Elements should appear in sync with the narration and make the cause-and-effect relationship clear without becoming a corporate slide.
```

## Open Questions For Implementation

- Whether panel assets should be generated at a smaller native size immediately or generated with the existing dimensions and displayed as panels first.
- Whether manual treatment overrides need a persistent source/lock field in Phase 1 or can simply write the selected treatment.
- Whether `popup_sequence` should suppress standard bottom subtitles when panels are dense. The first implementation can keep subtitles and rely on QA.
