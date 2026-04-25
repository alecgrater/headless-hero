# Active Word Highlight — Design Spec

## Context

Subtitle captions currently render as phrase-level blocks — all words in white, appearing and disappearing together. There's no visual connection between what's being said *right now* and the text on screen. Adding an active word highlight (karaoke-style) improves both engagement polish and comprehension by guiding the viewer's eye to the current word as it's spoken.

All required timing data (`word_timestamps` with per-word `start_ms`/`end_ms`) already exists from ElevenLabs TTS. This feature requires no new backend AI calls or data generation — it's purely a rendering enhancement with a global toggle.

## Design

### Visual Effect

As narration plays, the currently-spoken word turns **amber (#F59E0B)** with a **soft amber glow**, while all other words remain white. The highlight advances word-by-word based on ElevenLabs word timestamps.

- **Active word color:** `#F59E0B` (amber-500)
- **Active word glow:** `textShadow: 0 0 12px rgba(245, 158, 11, 0.4)`
- **Inactive words:** `#fff` with existing dark shadow `0 2px 8px rgba(0,0,0,0.8)`
- **No scale change** — words stay the same size, only color/glow shifts
- **Transition:** Instant snap per word (no crossfade between words — the timestamps are precise enough)

### Scope

- Applies to all narrated scenes rendered through `SubtitleOverlay`
- **Excluded:** Title card scenes (no SubtitleOverlay), aha_subtitle scenes (own renderer)
- Global toggle, default **on**

### Data Model

**`ScriptContent`** (`backend/models/script.py`):
```python
subtitle_highlight_enabled: bool = True
```
Follows the exact pattern of `segment_timer_enabled`.

**`FullVideoProps`** (`remotion/src/types.ts`):
```typescript
interface SubtitleHighlightConfig {
  enabled: boolean;
}

// Added to FullVideoProps:
subtitle_highlight?: SubtitleHighlightConfig | null;
```
Follows the exact pattern of `segment_timer?: SegmentTimerConfig`.

### Files to Modify

1. **`backend/models/script.py`** — Add `subtitle_highlight_enabled: bool = True` to `ScriptContent`
2. **`remotion/src/types.ts`** — Add `SubtitleHighlightConfig` interface and field on `FullVideoProps`
3. **`remotion/src/effects/typography/Subtitles.tsx`** — Core change: accept highlight config, apply per-word amber+glow styling based on frame vs word timing
4. **`remotion/src/scenes/SceneRenderer.tsx`** — Pass `subtitleHighlight` prop down to `SubtitleOverlay`
5. **`remotion/src/compositions/FullVideo.tsx`** (or wherever FullVideoProps flows to SceneRenderer) — Thread the config through
6. **`backend/pipeline/remotion_render.py`** — Include `subtitle_highlight` in the JSON props passed to Remotion
7. **Frontend toggle** — Add checkbox to timeline UI (follow segment timer toggle pattern)

### Remotion Implementation (Core Logic)

In `SubtitleOverlay`, the word `<span>` loop (line 115-127) already renders each word individually. The change:

```tsx
// For each word in the active phrase:
const wordStartFrame = Math.round((w.start_ms / 1000) * fps);
const wordEndFrame = Math.round((w.end_ms / 1000) * fps);
const isActiveWord = highlightEnabled && frame >= wordStartFrame && frame <= wordEndFrame;

// Style:
color: isActiveWord ? "#F59E0B" : "#fff",
textShadow: isActiveWord
  ? "0 0 12px rgba(245, 158, 11, 0.4), 0 2px 8px rgba(0, 0, 0, 0.8)"
  : "0 2px 8px rgba(0, 0, 0, 0.8)",
```

### Frontend Toggle

Add a checkbox to the timeline properties or export panel:
- Label: "Highlight active word"
- Mirrors the segment timer toggle pattern
- Updates `script_json.subtitle_highlight_enabled` via existing PUT `/api/scripts/{id}` endpoint

## Verification

1. Run `npm run dev` to start the full stack
2. Generate or load a script with voiceover (needs `word_timestamps`)
3. Render a scene preview — verify the active word highlights in amber with glow as narration plays
4. Toggle the setting off — verify subtitles render in plain white (current behavior)
5. Render full video — verify highlight works across all narrated scenes
6. Verify title card scenes and aha_subtitle scenes are unaffected
