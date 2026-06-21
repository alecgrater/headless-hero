# Full-Frame Blink Audit Design

## Purpose

Turn blink from a standalone visual mode into an automatic scene enhancement for normal media-backed scenes. Before enabling it in production, add a Test Lab audit that exercises full-size project images from `Your Life At Every Level Of Working At Burger King` so renderer-owned blink overlays can be evaluated against real generated scenes.

## Decision

Use full-image eye detection and an in-place Remotion overlay. Do not crop the person out, generate a blinking replacement, and composite the person back into the image.

The in-place overlay is the simpler forward design because the original full-frame image remains the only image layer. Eye/skin anchors are normalized against the image frame, and Remotion draws the eyelid erase masks and lid strokes over the same image node. Camera drift, zoom punch, vertical layout transforms, and scene transitions therefore move the base image and blink overlay together.

Cropping remains useful for the existing Test Lab cutout/debug path, but it should not become the production full-frame blink strategy. Cropping introduces matte edges, silhouette mismatch, occlusion errors, and exact re-placement work that the full-image overlay avoids.

## Test Lab: Blink Audit

Add a new Test Lab tab named `Blink Audit`.

The first audit source is the local script:

- Title: `Your Life At Every Level Of Working At Burger King`
- Script id: `9dacedc774514306ae1acb85215449e1`

The tab loads the script content and finds normal full-size scene images for media-backed scenes. It should ignore title cards and non-image layered modes. For each candidate, the tab shows:

- Scene label or id
- Still preview
- Blink preview
- Detection status
- Eligibility status
- Rejection reason when ineligible

The audit endpoint should persist lightweight reports under `data/test-lab/full-frame-blink-audits` so results survive reloads, matching the Test Lab habit of making diagnostics browsable.

## Detection And Eligibility

Create a backend detection module that analyzes a full-frame image and returns normalized blink anchor metadata compatible with the existing Remotion blink overlay geometry:

- `eye_left`
- `eye_right`
- `mouth`
- `brow_left`
- `brow_right`
- `skin_fill`
- local eye erase boxes and sampled skin colors when available

The v1 implementation should be conservative. A scene is eligible only when:

- the scene is not a title card
- the scene uses a media-backed visual mode: `full_frame`, `multi_frame`, `continuous`, or another mode that renders a normal image
- an image exists on disk
- one dominant face/character can be identified
- both eyes are detected
- the face is large enough for the eyelid overlay to read
- the face is not too profile, too occluded, too close to the frame edge, or too ambiguous
- local skin/color sampling can plausibly erase the open eyes before drawing closed lids

When any criterion fails, the result is an explicit ineligible status with a stable reason. Do not silently guess eye positions.

## Renderer

Move the deterministic blink overlay into a reusable Remotion component that can be applied to normal media-backed scenes. The old `visual_mode="blink"` renderer may continue to use the same geometry for existing Test Lab/debug compatibility, but production full-frame blink should not depend on cutout layers.

For a normal image scene, render:

1. The normal image or frame.
2. The blink overlay inside the same positioned image container.
3. The existing whole-scene camera effects around that combined image layer.

This keeps Ken Burns style motion and blinking aligned.

## Production Follow-Up

After the Test Lab audit proves the detector is reliable, production can use the same detector during image generation or pre-render preparation.

Production assignment should be deterministic:

- Eligible scene: 50% chance to blink.
- Random gate key: stable hash of `script_id + scene_id`.
- Ineligible scene: no blink.
- Missing or stale anchor metadata: no blink, with a diagnostic reason in dev logs.

`visual_mode` remains the composition field. Blink becomes an enhancement field or metadata value, not a visual mode selected by the scriptwriter.

## Documentation And Conventions

Update `AGENTS.md` when implementation changes the workflow:

- `blink` should no longer be treated as a production visual-mode path.
- Full-frame blink uses in-place detected anchors and renderer-owned overlays.
- Test Lab `Blink Audit` is the manual readiness surface before enabling automatic production blink.

Update in-app workflow docs to mention the new Blink Audit tab as the place to validate full-frame blink behavior before production rollout.

## Testing

Backend tests should cover:

- audit source discovery for the Burger King script
- candidate filtering
- eligible and ineligible detector results
- persisted report shape
- deterministic production 50% gate helper, if added in the same implementation pass

Frontend tests should cover:

- the `Blink Audit` tab appears
- the tab loads report data
- eligible and rejected scenes render distinct statuses
- still and blink previews are exposed

Remotion tests should cover:

- the full-image blink overlay uses existing anchor metadata
- the overlay is rendered inside the normal image layer
- whole-scene camera effects remain available for `full_frame`, `multi_frame`, and `continuous` scenes with blink enhancement metadata
