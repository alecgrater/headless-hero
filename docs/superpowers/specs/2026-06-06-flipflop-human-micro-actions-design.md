# Flip-Flop Human Micro-Actions Design

## Goal

Make `visual_mode="flipflop"` more reliable by restricting it to human or character two-frame micro-actions chosen from a small action vocabulary. Flip-flop should look like simple animation: the same character, outfit, camera, crop, and canvas remain stable while one tiny facial or body-language action changes.

## Current Context

Flip-flop already renders as alternating transparent cutouts over `visual_canvas.background_color`. State B already uses State A as a reference during cutout generation, which is the right asset model for consistency.

The weak point is semantic looseness. A scene can currently be `flipflop` without naming the exact motion it intends to animate. Generic "State A" and "State B" prompts leave too much room for drift, broad contrast, or unrelated visual changes.

## Product Behavior

`visual_mode="flipflop"` requires a top-level `flipflop_action` field. The action is the semantic contract for the two generated states. It is not user-facing in normal Timeline editing.

Allowed values:

```text
blink
speaking_mouth
eye_glance
eyebrow_raise
head_nod
explaining_hand_raise
thinking_pose
pointing_gesture
counting_fingers
small_shrug
```

The scriptwriter chooses `flipflop` and `flipflop_action` together from the full scene context. The backend trusts valid, human-supported choices rather than trying to second-guess every reasonable action. Invalid flip-flop scenes downgrade to `full_frame`.

## Routing Rules

Script generation should choose `flipflop` only when the scene is centered on a human, human-like character, or clearly personified character, and one allowed micro-action naturally supports the narration and visual prompt.

Use these reliability tiers in prompt guidance:

- Most reliable: `blink`, `speaking_mouth`, `eye_glance`, `eyebrow_raise`
- Reliable when supported: `head_nod`, `explaining_hand_raise`, `thinking_pose`
- Use only with clear prompt support: `pointing_gesture`, `counting_fingers`, `small_shrug`

The tiers are soft preferences, not quotas. When multiple actions fit equally well, prefer the earlier and more stable tier. When the narration or visual prompt clearly calls for a lower-tier action, use that action.

Avoid `flipflop` for object-only scenes, location changes, before/after contrast, different eras, comparison beats, process diagrams, statistics, or any action that requires multiple subjects or a large pose/environment change.

## Validation

After parsing generated script JSON, validation should apply these rules:

- If `visual_mode` is not `flipflop`, `flipflop_action` is ignored or cleared.
- If `visual_mode` is `flipflop` and `flipflop_action` is missing or not in the allowlist, downgrade the scene to `full_frame`.
- If `visual_mode` is `flipflop` but the narration and visual prompt do not indicate a human or character subject, downgrade the scene to `full_frame`.
- If `visual_mode` is `flipflop` and `flipflop_action` is valid with a human or character subject, preserve it.

Do not provide a compatibility default for older flip-flop scenes. Older projects may lose flip-flop rendering if they lack a valid action, and that is acceptable for this change.

## Scene Data

The scene JSON shape is:

```json
{
  "visual_mode": "flipflop",
  "flipflop_action": "blink",
  "visual_layers": [
    {
      "id": "scene_001_state_a",
      "type": "image",
      "asset_kind": "cutout",
      "prompt": "State A prompt derived from blink...",
      "placement": "center",
      "enter_at_seconds": 0,
      "animation": "none"
    },
    {
      "id": "scene_001_state_b",
      "type": "image",
      "asset_kind": "cutout",
      "prompt": "State B prompt derived from blink...",
      "placement": "center",
      "enter_at_seconds": 0,
      "animation": "none"
    }
  ]
}
```

`flipflop_action` belongs on the scene, not inside `visual_layers`. Layers are generated from that semantic action.

## Action State Definitions

Backend code should own deterministic State A and State B wording for each action:

| Action | State A | State B |
| --- | --- | --- |
| `blink` | eyes open, neutral natural face | eyes closed in a quick blink, same face and head position |
| `speaking_mouth` | mouth closed or lightly resting | mouth slightly open as if speaking one syllable |
| `eye_glance` | eyes looking forward | eyes glance slightly to the side or down, head unchanged |
| `eyebrow_raise` | neutral eyebrows | one or both eyebrows slightly raised in curiosity or emphasis |
| `head_nod` | head level and facing forward | chin slightly dipped in a small nod |
| `explaining_hand_raise` | hand relaxed near body | one hand raised near chest as if explaining |
| `thinking_pose` | hand away from chin | hand near chin in a thinking pose |
| `pointing_gesture` | hand relaxed or half-raised | one finger pointing toward an implied subject or screen area |
| `counting_fingers` | one finger raised | two fingers raised on the same hand |
| `small_shrug` | arms relaxed | shoulders and palms slightly raised in a small shrug |

Every State B prompt should preserve identity, outfit, style, camera angle, crop, scale, and cutout silhouette, changing only the named action.

## Prompting

Script prompts should describe `flipflop_action` as required whenever `visual_mode="flipflop"`. They should give the allowlist, action definitions, reliability tiers, and avoidance rules.

Layer generation should stop using generic "State A" and "State B" wording for flip-flop. It should call a centralized action-definition helper to build prompts for both states. State B should continue using State A as the reference image.

Generated images remain transparent or chroma-keyed human cutouts over the renderer-owned canvas. Do not add full scene backgrounds for flip-flop.

## UI And Test Lab

Timeline should not expose a normal `flipflop_action` dropdown. The goal is high-confidence automatic selection, not manual inspection.

Test Lab should expose `flipflop_action` when `visual_mode="flipflop"` so each allowed action can be tested deliberately. Switching modes must not rewrite narration, visual prompt, or other scene text.

Developer-facing metadata may show the selected action in logs, manifests, or debug panels where existing visual-mode metadata is surfaced.

## Cache And Staleness

`flipflop_action` must be part of:

- scene model serialization
- validation behavior
- generated layer prompt construction
- cutout prompt cache fingerprints
- Test Lab run manifests
- render sidecars where visual-layer metadata is already preserved

Changing `flipflop_action` should regenerate State A and State B assets because the visible motion contract changed.

## Failure Handling And Observability

Invalid flip-flop scenes should downgrade to `full_frame` before image generation. The downgrade should emit a structured fallback event because it changes visual output.

Generation should log the selected `flipflop_action` for flip-flop scenes and warnings for missing, invalid, or non-human flip-flop requests. Logs must not include full prompts, full narration, secrets, OAuth data, or absolute generated asset paths.

## Tests

Backend tests:

- scene model accepts valid `flipflop_action` values
- invalid `flipflop_action` values fail validation or downgrade to `full_frame`
- generated scripts with `flipflop` and missing action downgrade to `full_frame`
- generated scripts with valid human flip-flop actions preserve `flipflop`
- object-only or non-human flip-flop scenes downgrade to `full_frame`
- generated visual layers use action-specific State A and State B prompts
- `flipflop_action` changes the cutout prompt fingerprint

Frontend/Test Lab tests:

- Test Lab exposes the action selector only for `flipflop`
- Test Lab sends selected `flipflop_action` to the backend
- switching visual modes does not rewrite narration or visual prompt
- Timeline does not add a normal action dropdown

Remotion tests:

- existing A/B cadence remains unchanged
- cutout rendering stays centered over the canvas
- renderer does not require full backgrounds for flip-flop

Docs/tests:

- AGENTS.md describes human-only flip-flop actions and the required `flipflop_action` field
- visual-mode prompt tests include the allowlist and reliability tiers

## Acceptance Criteria

- New generated flip-flop scenes always include a valid `flipflop_action`.
- Flip-flop is human or character only.
- Invalid flip-flop scenes downgrade to `full_frame` rather than using a generic fallback.
- State A and State B prompts are deterministic per action.
- State B still uses State A as reference.
- Flip-flop remains transparent cutouts over the canvas background.
- Test Lab can exercise all 10 actions.
- Normal Timeline editing does not require manual action selection.
