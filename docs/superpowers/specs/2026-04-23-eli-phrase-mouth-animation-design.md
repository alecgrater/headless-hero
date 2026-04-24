# Eli Phrase-Based Mouth Animation

## Problem

The Eli character's mouth animation is jittery. The current `getMouthOpenness()` function in `remotion/src/effects/overlays/EliOverlay.tsx` reacts to every individual word timestamp — ramping mouth openness up and down every ~0.3-0.5 seconds. This creates constant micro-transitions that look unnatural. A real speaker keeps their mouth open while talking through a phrase and only closes it during deliberate pauses.

## Solution

Replace the per-word mouth logic with phrase-level mouth animation:

1. **Backend** computes phrase groups from word timestamps during voiceover generation
2. **Phrase groups** are stored on each Scene in `script_json` as `phrase_timestamps`
3. **Remotion** reads `phrase_timestamps` instead of deriving mouth state from individual words

## Phrase Grouping Algorithm

**Adaptive threshold** — the pause duration that triggers a mouth-close is derived from the audio itself, not hardcoded:

1. Compute all inter-word gaps: `gap[i] = word[i+1].start_ms - word[i].end_ms`
2. Find the median gap
3. Set close-mouth threshold = `median_gap × 3` (clamped to `[200ms, 800ms]`)
4. Walk words sequentially: if the gap to the next word is below threshold, they're in the same phrase. If above, start a new phrase.
5. Each phrase becomes `{start_ms, end_ms}` where `start_ms` = first word's `start_ms`, `end_ms` = last word's `end_ms`

**Edge cases:**
- Single-word scene → one phrase spanning that word
- No word timestamps → `phrase_timestamps` is `None`, Remotion keeps mouth closed
- All gaps below threshold → one phrase for the entire scene

## Data Model

### Backend: `PhraseTimestamp` (Pydantic model in `backend/models/script.py`)

```python
class PhraseTimestamp(BaseModel):
    start_ms: int
    end_ms: int
```

### Scene field addition

```python
class Scene(BaseModel):
    ...
    phrase_timestamps: list[dict] | None = None  # PhraseTimestamp dicts
```

### Remotion: `PhraseTimestamp` interface in `remotion/src/types.ts`

```typescript
export interface PhraseTimestamp {
  start_ms: number;
  end_ms: number;
}
```

### SceneInput addition

```typescript
export interface SceneInput {
  ...
  phrase_timestamps?: PhraseTimestamp[] | null;
}
```

## Mouth Animation Behavior

**Snap open, fade close** — mimics how real mouths work:

- **Phrase starts:** Mouth opens in ~30-50ms (near-instant snap)
- **During phrase:** Mouth stays at 1.0 (fully open frame)
- **Phrase ends:** Mouth fades closed over ~100-120ms (gentle ramp to 0.0)
- **Between phrases / silence:** Mouth stays at 0.0 (static closed frame)

The `getMouthOpenness()` function is rewritten to loop over `phrase_timestamps` instead of `word_timestamps`. If `phrase_timestamps` is null/missing, return 0 (mouth closed).

## Files to Modify

### Backend

| File | Change |
|------|--------|
| `backend/models/script.py` | Add `PhraseTimestamp` model; add `phrase_timestamps` field to `Scene` |
| `backend/pipeline/voiceover.py` | Add `compute_phrase_timestamps()` function; call it after TTS returns word timestamps |
| `backend/api/voiceover.py` | Pass computed `phrase_timestamps` through to `update_scene()` for both single and batch endpoints |

### Remotion

| File | Change |
|------|--------|
| `remotion/src/types.ts` | Add `PhraseTimestamp` interface; add field to `SceneInput` |
| `remotion/src/effects/overlays/EliOverlay.tsx` | Rewrite `getMouthOpenness()` to use phrase_timestamps; update `Props` to accept phrase_timestamps; remove word_timestamps dependency from mouth logic |
| `remotion/src/scenes/SceneRenderer.tsx` | Pass `phrase_timestamps` to `EliOverlay` component |

### Data bridge (Python → Remotion)

| File | Change |
|------|--------|
| `backend/pipeline/remotion_render.py` | Include `phrase_timestamps` in scene data passed to Remotion JSON |

## Migration

None. Existing scripts without `phrase_timestamps` will have `null` for the field. Remotion treats `null` as mouth-closed (matches the fallback in `getMouthOpenness()`). To get phrase-based mouth animation on old scripts, regenerate voiceover.

## Verification

1. Generate voiceover for a test script → confirm `phrase_timestamps` appears in the script_json blob
2. Inspect phrase grouping: check that phrases span multiple words and gaps between phrases are at natural pause points
3. Render a scene preview with Eli overlay → confirm mouth opens smoothly at phrase start, stays open, closes gently between phrases
4. Compare against current behavior — should be visibly less jittery
5. Test edge cases: single-word scene, scene with no audio, very fast narration, slow narration with long pauses
