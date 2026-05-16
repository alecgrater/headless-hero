# Eli Procedural Animation Rebuild

## Context

The current Eli animation system looks choppy and unnatural. It works by switching between 150+ pre-generated pose images via AI-generated keyframe timelines (6-8 pose changes per scene). The discrete image-swapping is the root cause — no matter how smoothly you crossfade, switching between completely different drawings looks robotic.

This rebuild replaces the entire keyframe-based system with a **one pose per scene + procedural idle motion** approach. The goal is animation that looks like a talented college-grad student hand-animated it — slightly imperfect, organic, with traditional animation principles (anticipation, follow-through, settle).

## Design

### Core Model Change

**Before:** `EliOverlay { enabled, corner, keyframes: EliKeyframe[] }` where each keyframe has `start_frame`, `end_frame`, `frame_id`, `transition`

**After:** `EliOverlay { enabled, corner, frame_id }` — one pose for the entire scene, all motion is procedural.

### Claude's Simplified Role

Instead of generating complex keyframe timelines with timing and transitions, Claude picks **one pose per scene** that matches the narration's emotional tone. The prompt provides the narration text and the list of available frame IDs. Output is just `{ corner, frame_id }`.

### Procedural Motion Layers (Remotion)

All character "life" comes from layered CSS transforms computed per-frame. Key design principle: **never perfectly repeat**. Layer sines at irrational frequency ratios so the combined motion drifts organically.

#### 1. Breathing (~3.5s base cycle)
- `scaleY`: 1.0 + 0.004 × sin(t × 2π / 3.5) + 0.0015 × sin(t × 2π / (3.5 × φ))
- `translateY`: -2px × sin(t × 2π / 3.5)
- Breathing leads other motion layers by ~0.3s phase offset

#### 2. Body Sway (~7s cycle)
- `translateX`: ±3px sine wave
- `rotate`: ±0.8° sine with +0.5 radian phase offset from translateX
- Cycle related to breathing by golden ratio (never syncs up)

#### 3. Head Micro-Tilts (~5s cycle)
- `rotate`: ±1.5° with custom slow-out bezier easing
- Phase offset from sway using √2 ratio
- Easing approximates hand-keyframed feel (ease into holds, not mechanical)

#### 4. Eye Blinks (event-driven)
- Pre-computed deterministic schedule from scene seed (reproducible renders)
- Interval: 3-6 seconds between blinks (randomized)
- Duration: 120-200ms (4-6 frames at 30fps)
- 20% chance of double-blink (second blink 200ms after first)
- 10% chance of slow contemplative blink (300ms)
- Implementation: quick vertical squash (`scaleY(0.92)` + `translateY(+3px)`) for 3-4 frames with ease-in/out. Classic animation trick — at webcam-overlay size, a brief squash reads as a blink to the viewer without needing dedicated blink frames.

#### 5. Lip Sync (existing, kept)
- `getMouthOpenness()` from phrase_timestamps
- Stack open + closed mouth frames with complementary opacities
- Ramp open 40ms before phrase, hold during, fade close 110ms after

### Scene Transitions

- **Exit** (last 12 frames): translateY 0 → +60px with `Easing.in(quad)`, opacity 1 → 0
- **Entrance** (first 14 frames): translateY +60px → 0 with spring overshoot (damping: 10, mass: 0.6, stiffness: 120), slight scale overshoot 1.02 → 1.0
- Brief ~6-frame gap between exit and entrance where Eli is offscreen

### Animation Principles

| Principle | Implementation |
|-----------|----------------|
| Irregularity | Sine frequencies at irrational ratios (1.0, φ=1.618, √2=1.414) |
| Slow-out easing | Custom bezier(0.25, 0.05, 0.1, 1.0) for holds |
| Follow-through | Spring entrance with underdamping (overshoot then settle) |
| Blink character | Squash-blinks with clusters, double-blinks, varied durations |
| Breath leads | Breathing phase leads other layers by 0.3s |
| Determinism | All random params seeded from hash(sceneId + frame_id) |

### What Gets Removed

- `EliKeyframe` model (backend + frontend + Remotion)
- `keyframes` array from `EliOverlay`
- `ELI_ANIMATOR_SYSTEM` prompt (complex keyframe generation instructions)
- Variant cycling system (v2/v3/v4 frame rotation)
- `EliLane.tsx` micro-timeline editor component
- Keyframe post-processing/validation (gap-filling, overlap resolution, min-duration enforcement)
- `variant_counts` plumbing through render pipeline

### What Stays

- Frame library (150 poses × 2 mouth states)
- Character frame generation pipeline (`character_frames.py`, `api/character.py`)
- Corner alternation between scenes (left↔right, 70% bottom)
- `contains_person` suppression
- Phrase timestamps → mouth openness blend
- "Add Eli" button and generation flow in timeline UI
- Character settings section in frontend

### Backward Compatibility

Old scripts in the DB have `eli_overlay` dicts with `keyframes` arrays. The new Remotion component handles this gracefully:
```typescript
const frameId = overlay.frame_id || overlay.keyframes?.[0]?.frame_id;
if (!frameId) return null;
```
Regenerating Eli for a scene overwrites with the new format.

## Files to Modify

| File | Action |
|------|--------|
| `backend/models/script.py` | Remove EliKeyframe, simplify EliOverlay |
| `backend/pipeline/eli_animator.py` | Rewrite: simple pose selection |
| `backend/prompts.py` | Replace ELI_ANIMATOR_SYSTEM with pose-picker prompt |
| `backend/api/eli.py` | Simplify scene_data passed to generator |
| `backend/pipeline/remotion_render.py` | Remove variant_counts plumbing |
| `remotion/src/types.ts` | Simplify EliOverlay, remove EliKeyframe |
| `remotion/src/effects/overlays/EliOverlay.tsx` | Complete rewrite (procedural idle) |
| `remotion/src/scenes/SceneRenderer.tsx` | Update conditional + props |
| `frontend/src/types/script.ts` | Remove EliKeyframe, simplify EliOverlay |
| `frontend/src/components/timeline/micro-timeline/EliLane.tsx` | Delete |
| `frontend/src/components/timeline/SceneMicroTimeline.tsx` | Remove EliLane integration |
| `frontend/src/components/timeline/TimelinePage.tsx` | Minor text updates |

## Verification

1. **Backend**: Run `uv run python -c "from backend.pipeline.eli_animator import generate_scene_eli"` — verify import works
2. **Generate**: Call `/api/eli/generate` for a script, verify response has `{ enabled, corner, frame_id }` per scene
3. **Render preview**: Render a single scene with `npx remotion render` and inspect:
   - Breathing visible but subtle
   - Blinks fire at natural intervals
   - Mouth syncs to speech
   - No pose switching within scene
   - Entrance has spring overshoot
4. **Full render**: Run full YOLO pipeline end-to-end, watch output video
5. **Old scripts**: Load a script with old-format `eli_overlay` (has `keyframes`), render without crash
6. **Frontend**: "Add Eli" button works, no console errors about missing properties
