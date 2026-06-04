# Flip-Flop Cutout Animation Design

## Goal

Replace the current full-frame `flipflop` behavior with cropped subject animation everywhere. Flip-flop should read as a simple two-state character or subject motion loop over the static canvas, not as two complete scene images snapping back and forth.

The new default mental model is a human or character cutout alternating between two compatible body-language/action states: talking mouth changes, head tilt, hand gesture, pointing, leaning, shrugging, pacing, holding an object, or performing a small action. Object-only flip-flops are allowed only when the narration or manual prompts explicitly call for an object action.

## Current Context

`flipflop` already means same-subject micro-animation in the active project rules, script prompt, visual-mode policy, analyzer tests, Test Lab labels, and Remotion timing. The mismatch is the asset model: the current generation path treats flip-flop layers as full-bleed panels, so two whole backgrounds alternate. That makes the beat feel like two static images fighting each other instead of one subject moving.

The app already has useful cutout infrastructure:

- `popup_sequence` generates and crops transparent cutouts.
- `comparison_board` renders cutouts over the static canvas.
- `pipeline.test_lab_popup_crop` has chroma keying helpers for trimming transparent PNGs.
- Remotion already renders `asset_kind="cutout"` layers without frames or baked backgrounds.

## Product Behavior

`visual_mode="flipflop"` keeps the same canonical mode name and still uses `visual_layers`, but its layer assets become cropped cutouts instead of full-frame panels.

Every generated flip-flop scene should have two visible states:

- State A: the initial character/subject pose.
- State B: the next compatible pose, expression, mouth shape, or action state.

Remotion alternates the active cutout from frame zero in the existing ABABAB rhythm. The background is the scene or video `visual_canvas.background_color`, plus any renderer-owned scene treatment that remains compatible. There should be no full generated background image for flip-flop.

## Routing Rules

Script generation should choose `flipflop` when the scene is naturally about a character or human-like subject doing a tiny repeated or two-state action. Strong examples:

- talking with visible mouth/body-language changes
- nodding, leaning, pointing, shrugging, pacing, gesturing
- hand/arm movement while holding, sorting, typing, stirring, counting, opening, or closing something
- a close character reaction where face, eyes, or posture changes slightly

Avoid `flipflop` for:

- broad before/after or then/now contrast
- different locations, eras, social classes, or outcomes
- unrelated emotional states
- side-by-side comparison needs
- gradual transformation that needs more than two states
- item lists or multiple independent examples

Prefer other modes in those cases:

- `comparison_board` for two or three contrasted subjects, choices, roles, or outcomes.
- `continuous` for one subject/environment changing over time.
- `multi_frame` for independent visual examples or quick cuts.
- `full_frame` when one static image communicates the beat best.

Post-voiceover analysis should preserve explicit `flipflop` scenes, fill missing two-state cutout layers, and only infer new `flipflop` assignments from strong character/body/body-part motion cues. Generic object motion should not promote to flip-flop unless the narration explicitly names a simple object action.

## Scene Data

The JSON shape remains deterministic and compatible with existing `visual_layers`:

```json
{
  "visual_mode": "flipflop",
  "visual_layers": [
    {
      "id": "scene_001_state_a",
      "type": "image",
      "asset_kind": "cutout",
      "prompt": "State A cutout prompt...",
      "placement": "center",
      "enter_at_seconds": 0,
      "animation": "none"
    },
    {
      "id": "scene_001_state_b",
      "type": "image",
      "asset_kind": "cutout",
      "prompt": "State B cutout prompt...",
      "placement": "center",
      "enter_at_seconds": 0,
      "animation": "none"
    }
  ]
}
```

`image_url` and `frame_urls` should be empty for flip-flop scenes. The returned layers own their transparent `image_url` or renderer `image_path`. Existing legacy layers with `asset_kind="panel"` should be treated as stale and regenerated through the new cutout path when images are refreshed.

## Prompting

Flip-flop prompts should ask for isolated chroma-background subjects, not complete scenes.

Shared prompt requirements:

- same character identity or same specific subject in both states
- same style, approximate camera angle, scale, and crop
- preferably waist-up or full-body depending on the action
- clean closed silhouette for programmatic cropping
- solid chroma background that does not appear in the subject
- no full scene background, no scenery, no panel frame, no split screen, no readable text

State B should use State A as an identity/style reference where the image client supports references. It should only change the relevant pose, expression, mouth shape, hand position, or simple action state.

## Generation Flow

Add a flip-flop-specific generation path beside `generate_popup_sequence_cutouts` and `generate_comparison_board_cutouts`.

For each flip-flop scene:

1. Build or preserve two `asset_kind="cutout"` layer prompts.
2. Generate State A as a chroma subject source.
3. Generate State B as a chroma subject source, using State A as a reference when available.
4. Key out the chroma background and trim transparent padding using the shared crop helper.
5. Persist both transparent PNGs under the project scene assets.
6. Return updated `visual_layers` containing the cutout asset URLs and metadata.

Manual scene regeneration, batch image generation, and Test Lab should all route `flipflop` through this path. `generate_visual_layer_panels` should no longer be used for flip-flop.

The chroma crop helper currently lives in the popup crop lab module. Implementation should either move the reusable key/trim functions into a production helper module or import a shared helper from a neutral location so production flip-flop generation does not depend on a Test Lab-only module boundary.

## Renderer

Remotion keeps the existing active-layer timing:

- alternate every 0.5 seconds
- start alternating from frame zero
- include all available valid states

The visual difference is layout:

- render the active layer as a centered cutout over the canvas
- use `object-fit: contain`
- keep wrapper background transparent
- avoid panel frames, image borders, or full-frame cover crops
- size the cutout large enough that the subject carries the scene

If both states exist, ABABAB creates the motion. If only one valid cutout exists, render it as a static cutout fallback over the canvas instead of failing the scene.

Standard subtitles and Eli overlays remain supported unless implementation testing shows that specific layouts collide. Whole-scene camera FX should be blocked or carefully reviewed for flip-flop because scaling/panning the canvas can make cutout alternation feel jittery.

## Test Lab

Test Lab keeps the current flip-flop controls:

- Narration
- Visual prompt
- State A
- State B

The helper text should describe the new contract: two cropped character/body-language states over the canvas. Switching to flip-flop must not rewrite narration, visual prompt, or state text.

Test Lab runs should use the same production cutout generation path. Run manifests should preserve:

- `visual_mode`
- `visual_layers`
- layer `asset_kind`
- source/crop output paths where available
- any warnings from chroma removal or missing layers

## Cache And Staleness

Flip-flop cache fingerprints should include:

- scene visual prompt
- State A prompt
- State B prompt
- visual canvas background color
- model/provider settings that affect generation
- cutout renderer behavior version
- crop/keying behavior version
- generated layer asset paths or source metadata

Older flip-flop renders/layers without `asset_kind="cutout"` should be stale. Full-frame panel assets should not be reused after this change.

## Failure Handling And Observability

If State B generation fails but State A succeeds, keep a static State A cutout and log a warning. If State A fails but State B succeeds, use State B as the static fallback and log a warning. If both states fail or crop to nearly empty output, fall back to the normal full-frame generation path when possible.

Generation should log status and warnings for:

- starting flip-flop cutout generation
- missing or legacy panel layers being regenerated
- chroma crop producing empty or tiny cutouts
- using a single-state fallback
- falling back to full-frame

These logs should show up anywhere current visual generation and Test Lab logs surface pipeline-visible state.

## Tests

Backend tests:

- explicit flip-flop scenes produce two `asset_kind="cutout"` layers
- body-language narration can infer flip-flop
- generic contrast does not infer flip-flop
- flip-flop generation routes to the new cutout function, not panel generation
- stale panel layers are regenerated as cutouts
- single-state and full-frame fallbacks are handled

Frontend/Test Lab tests:

- flip-flop controls still expose State A and State B
- helper copy describes cropped subject/body-language states
- switching visual modes does not rewrite scene text

Remotion tests:

- active flip-flop layer alternates from frame zero
- cutout layers render centered over transparent/canvas background
- panel/full-frame cover styling is not applied to flip-flop cutouts
- one valid layer renders as a static cutout fallback

Docs/tests:

- visual mode docs, AGENTS.md, and settings catalog describe flip-flop as cropped subject animation
- script prompt tests assert the cutout/body-language definition and contrast avoidance

## Acceptance Criteria

- No active production path generates full-frame flip-flop panels.
- Flip-flop generated assets are transparent/cropped cutouts over `visual_canvas.background_color`.
- Script and analyzer routing strongly prefer human or character body-language subjects.
- Broad contrast is still routed away from flip-flop.
- Test Lab can generate and inspect the new behavior without a full project render.
- Legacy full-frame flip-flop assets are treated as stale and replaced on regeneration.
- The renderer produces ABABAB motion from frame zero using cutouts.
