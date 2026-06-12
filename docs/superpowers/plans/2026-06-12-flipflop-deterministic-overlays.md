# Flip-Flop Deterministic Overlay Recovery

## Problem

Real Test Lab runs showed that the shared A/B state-sheet approach still depended on Gemini preserving the same head pose, body scale, skin rendering, and silhouette across two cells. Even after stronger prompts, chroma fixes, and registration tolerance changes, the provider could return two visibly different characters or states too different to align. The registration error was correct; the asset model was too fragile.

## Decision

For new Test Lab flip-flop runs, generate exactly one neutral transparent human/character base cutout. Pass `flipflop_action` to Remotion and let the renderer toggle deterministic micro-expression overlays every 0.5 seconds for the reliable face-only actions:

- `speaking_mouth`
- `blink`
- `eye_glance`
- `eyebrow_raise`

Pose/body actions stay in the action vocabulary for compatibility and future exploration, but the deterministic renderer does not draw overlays for them.

## Implementation Plan

1. Add a base-cutout generator in `backend/pipeline/image_gen.py` that keys and trims one neutral character cutout, writes source metadata, and fingerprints the composed prompt plus keying algorithm version.
2. Route Test Lab `visual_mode="flipflop"` through the base-cutout generator instead of `generate_flipflop_cutouts`.
3. Keep the old two-state generator and renderer path for existing assets/tests, but do not use it for new explicit Test Lab flip-flop runs.
4. Include `flipflop_action` in Remotion scene input props.
5. Add renderer-owned overlay helpers and tests for 0.5-second toggling and action mapping.
6. Update guardrails and AGENTS conventions so future work treats A/B generation as legacy compatibility, not the primary design.

## Acceptance

- Explicit Test Lab flip-flop generation produces one cutout layer.
- The old A/B generator is not called by Test Lab flip-flop runs.
- Remotion can render a one-layer flip-flop scene from persisted props alone.
- Focused backend and frontend tests cover the generation route and renderer mapping.
- Full backend and frontend suites pass before commit.
