# Flipflop Renderer-Owned Context Design

## Decision

Flipflop should no longer generate or render an AI-created environment background. Going forward, `visual_mode="flipflop"` uses two generated transparent human/character state cutouts plus a renderer-owned context stage.

The context stage is selected by a small explicit field:

```ts
flipflop_context?: "plain" | "desk" | "classroom" | "office" | "kitchen" | "shop" | "lab" | "street"
```

The field is optional in incoming data, but generation and validation should normalize it before render. Missing or unclear contexts should resolve to `"plain"` or `"desk"`. The renderer owns the visual stage for each context with simple deterministic shapes such as wall/floor bands, desk strips, boards, shelves, counters, windows, lab benches, or street silhouettes.

Existing generated flipflop background layers do not need compatibility preservation. New generation should stop creating, caching, or rendering flipflop environment image layers.

## Problem

Recent flipflop output improved asset registration by using a shared A/B state sheet and State A bbox registration, but two quality problems remain:

- State A and State B can still jump because the image model may draw the face, torso, or silhouette landmarks in different positions inside the keyed region. Bbox alignment makes the PNG canvas consistent; it does not guarantee anatomical landmark alignment.
- AI-generated environment backgrounds make transparent cutouts look pasted into a complete illustrated scene. The generated room often includes perspective, clutter, foreground props, or implied subject placement that conflicts with the separately rendered character cutout.

This design solves the second problem. It intentionally leaves the state-jump problem visible as a follow-up.

## Goals

- Keep the character cutout isolated and stable over a deterministic stage.
- Provide enough context for the viewer to understand the setting without generating a full room.
- Make flipflop behave more like other renderer-owned layered modes: generated assets supply subjects; Remotion owns layout and context.
- Avoid carrying legacy flipflop background baggage forward.
- Keep the implementation low-risk by preserving the existing two-cutout generation path and A/B alternation cadence.

## Non-Goals

- Do not add a new visual mode.
- Do not solve landmark-level A/B registration in this change.
- Do not preserve old generated flipflop environment backgrounds.
- Do not add a normal Timeline dropdown for flipflop action or context unless the implementation discovers an existing editor surface that must expose the field.
- Do not ask an LLM to generate context SVG, canvas code, or per-scene shape layouts.

## Scene Contract

Required for valid flipflop scenes:

- `visual_mode: "flipflop"`
- `flipflop_action`: one allowed human micro-action
- `flipflop_context`: normalized context preset
- `visual_layers`: exactly two generated image cutouts for State A and State B after asset generation

The two state layers remain `type="image"` and `asset_kind="cutout"`. They should use stable ids such as `{scene_id}_state_a` and `{scene_id}_state_b`.

Flipflop scenes should not include a `full_frame` or `panel` background layer. If a generated background layer is present, normalization should drop it for new output.

## Context Selection

Context selection should be deterministic and conservative.

Fresh script generation may emit `flipflop_context` when choosing `visual_mode="flipflop"`. If script generation omits it, backend validation or layered visual analysis should infer it from narration and `visual_prompt` using simple keyword rules.

Suggested initial mapping:

- `"classroom"`: classroom, school, teacher, student, whiteboard, lecture, homework
- `"office"`: office, meeting, spreadsheet, document, email, desk job, cubicle
- `"kitchen"`: kitchen, restaurant, cooking, chef, fryer, counter, food service
- `"shop"`: store, cashier, customer, register, retail, bar, cafe
- `"lab"`: lab, scientist, experiment, microscope, clinic, medical
- `"street"`: street, sidewalk, city, car, bus, outside
- `"desk"`: laptop, computer, books, paperwork, study, writing, generic work table
- `"plain"`: unclear, abstract, or when a clean character beat is better than context

If multiple contexts match, prefer the most specific setting in this order: `kitchen`, `shop`, `lab`, `classroom`, `office`, `street`, `desk`, `plain`.

## Remotion Behavior

`TreatmentRenderer` should render flipflop as:

1. Global static canvas color.
2. `FlipflopContextStage` for the normalized `flipflop_context`.
3. The active State A/B cutout, centered with the existing flipflop frame style.

The existing A/B cadence remains unchanged: alternate from frame zero every 0.5 seconds. `enter_at_seconds` must not delay State B participation.

The context stage should use simple, low-detail shapes with fixed positions. It should avoid readable text, logos, heavy perspective, full-room detail, or foreground clutter. It should leave the central subject area visually calm so the cutout feels intentionally staged rather than pasted.

## Asset Generation

Flipflop generation should only create the shared state sheet and the two transparent cutouts. It should stop generating the environment background image and stop writing background prompt markers for flipflop.

The state sheet prompt remains responsible for:

- one shared two-cell sheet
- matching identity, style, crop, scale, canvas position, and bounding box
- chroma background
- no scenery, props, labels, text, or full background

The existing bbox registration step can stay in place. It helps but is not considered sufficient for blink stability.

## Cache And Sidecars

Flipflop render cache fingerprints should include:

- `visual_mode`
- `flipflop_action`
- `flipflop_context`
- State A/B cutout image paths and source metadata
- renderer context version
- existing subtitle/settings inputs that already affect render output

Changing the renderer-owned context shapes should bump a context-stage version string so old renders are treated as stale.

Generated asset cache keys for State A/B should not include `flipflop_context` unless cutout prompts start using it. The context is a renderer concern, not a character asset concern.

## Test Lab

Test Lab should continue exposing flipflop action selection. It should also expose a compact flipflop context selector when `visual_mode="flipflop"`.

Switching the context selector must not rewrite narration, visual prompt, caption text, stat fields, or other mode-specific scene text.

Run manifests should include `flipflop_action`, `flipflop_context`, and the generated cutout layer metadata.

## Fallbacks And Observability

If `flipflop_context` is missing or invalid, normalize to `"plain"` and record a structured fallback event because render-visible behavior changed.

If cutout generation fails, preserve the existing fallback behavior for broken layered assets: fall back to a stable existing visual path rather than rendering a broken flipflop.

Generation and render logs should clearly distinguish flipflop state cutout generation from renderer-owned context staging. Logs should not imply an environment background image was generated.

## Tests

Backend tests should cover:

- `Scene` accepts and normalizes valid `flipflop_context` values.
- Invalid/missing context normalizes to `"plain"` or inferred context.
- Flipflop layer normalization emits exactly two cutout layers and no background layer.
- Flipflop generation does not call image generation for an environment background.
- Render cache fingerprints include `flipflop_context` and renderer context version.

Remotion/frontend tests should cover:

- `FlipflopContextStage` renders deterministic presets.
- `TreatmentRenderer` stages context behind A/B cutouts.
- Background image layers are not required for flipflop.
- Test Lab context changes preserve scene text.

Docs/tests should update the Visual Modes catalog and asset ownership docs in the implementation change.

## Follow-Up: Blink Jump

This change does not fully solve the visible A/B jump in blink scenes. After renderer-owned context lands, the next flipflop quality task should address state alignment directly.

Likely approaches:

- Constrain flipflop to the most reliable actions until registration improves, especially `speaking_mouth`, `eye_glance`, and `eyebrow_raise`.
- Add post-process alignment based on face/body landmarks.
- Add stronger alpha-mask anchoring, such as aligning eyes/head/torso anchors instead of only the outer bbox.

This follow-up should stay visible because renderer-owned context will make the pasted-background problem better, but it will not stop blinking faces from jumping if State A/B landmarks are generated in different positions.
