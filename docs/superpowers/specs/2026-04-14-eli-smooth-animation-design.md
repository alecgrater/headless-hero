# Eli Smooth Animation Design

## Context

After expanding the Eli character frame library from 300 to 1,056 frames (adding 3-5 variants per pose for micro-animation), the overlay animation became choppy and off-putting. Two issues compound:

1. **Variant cycling** hard-swaps between independently-generated illustration variants every 6 frames (~200ms), causing visible jitter since the variants aren't sequential animation frames
2. **Pose-to-pose transitions** are mostly hard cuts (Claude's default), with crossfades only lasting 6 frames (~200ms) when used

Previously with 300 frames (no variants), the character held still within each pose, giving a charming paper-cutout puppet feel. The goal is to restore smooth, intentional animation while using all 1,056 frames.

**Target feel:** Smooth transitions but still clearly an illustrated character — gentle living illustration, not fluid cartoon. Hybrid between polished cutout (Kurzgesagt) and paper puppet charm.

## Design

### 1. Slow Variant Crossfade (replaces hard-swap cycling)

**File:** `remotion/src/effects/overlays/EliOverlay.tsx`

**Current behavior:** `getVariant()` selects a variant index, hard-swaps to a new variant every 6 frames (~200ms). Single `<Img>` element.

**New behavior:**
- Render **two variant image layers** (absolutely positioned, stacked)
- Crossfade between variants over **~90 frames (~3 seconds at 30fps)**
- When crossfade completes, "next" becomes "current", a new "next" variant is selected from the pseudo-random sequence
- Variant selection uses the same deterministic LCG approach, just with longer cycle length
- Opacity: current layer fades from 1→0, next layer fades from 0→1 (linear interpolation)
- Both layers use the same mouth state (open/closed) at any given frame

This creates a slow, dreamy weight-shift effect rather than jittery frame swapping.

**Edge case — concurrent with pose crossfade:** During a pose-to-pose crossfade, variant cycling pauses (freeze the current variant for each pose). The pose blend already provides visual motion; blending variants simultaneously would create a confusing 4-layer stack.

### 2. Longer Pose-to-Pose Crossfade (200ms → 500ms)

**File:** `remotion/src/effects/overlays/EliOverlay.tsx`

Change `CROSSFADE_FRAMES` constant from `6` to `15` (500ms at 30fps). The existing dual-layer opacity blend logic remains the same, just longer duration.

### 3. Claude Prompt: Default Crossfade, Cuts for Drama

**File:** `backend/pipeline/eli_animator.py`

Update `ELI_SYSTEM_PROMPT`:
- Change default transition recommendation from "cut" to "crossfade"
- Instruct Claude: "Use crossfade for most transitions. Reserve cut for dramatic moments only — surprise reveals, punchlines, sudden reactions, or comedic timing."
- This is a prompt-only change; the keyframe schema stays the same

### Summary of Constants

| Parameter | Before | After |
|-----------|--------|-------|
| Variant cycle length | 6 frames (200ms) | 90 frames (3s) crossfade |
| Variant transition | Hard swap | Opacity crossfade |
| Pose crossfade duration | 6 frames (200ms) | 15 frames (500ms) |
| Default pose transition | "cut" (Claude's tendency) | "crossfade" (prompt guidance) |

## Files Modified

1. `remotion/src/effects/overlays/EliOverlay.tsx` — Variant crossfade system + longer pose crossfade
2. `backend/pipeline/eli_animator.py` — Claude prompt update for default crossfade

## Verification

1. Run `npm run dev` and navigate to a script with Eli overlay enabled
2. Render a scene preview — verify:
   - Character holds poses with slow, gentle variant blending (no jitter)
   - Pose-to-pose transitions are smooth 500ms crossfades by default
   - Dramatic moments (if Claude chose "cut") still snap cleanly
   - Mouth open/closed still syncs correctly with narration
3. Full video render — watch through and confirm overall feel is "gentle living illustration"
4. Regenerate Eli animation for one scene (`POST /api/eli/regenerate`) and verify Claude now defaults to crossfade transitions
