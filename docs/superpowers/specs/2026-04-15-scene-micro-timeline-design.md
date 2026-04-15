# Scene Micro-Timeline: Within-Scene Visual Timing Control

**Date:** 2026-04-15
**Status:** Design

## Problem

Visual events within scenes (image crossfades, zoom punches, Eli pose changes, and scene visual boundaries) are either auto-calculated or AI-generated with no manual control. Users need frame-precise timing adjustments to align visuals with narration — e.g., making a photo appear exactly when the narrator mentions it, or syncing a crossfade to a specific word.

## Solution

A per-scene micro-timeline in the preview panel that visualizes all visual events as draggable markers on top of the audio waveform. Users play audio, pause at the right moment, and place or nudge markers using keyboard shortcuts and drag interactions.

## Component Architecture

### Layout

The micro-timeline lives in the existing preview panel area, below the Remotion Player and extending the current WaveformSplitter:

```
┌─────────────────────────────────────────────────┐
│  Remotion Player (16:9 preview)                 │
├─────────────────────────────────────────────────┤
│  Waveform  ▁▂▃▅▇▅▃▂▁▂▃▅▆▅▃▁▂▃▅▇▅▃▁           │
│  Words     |Hello|world|this|is|a|volcano|...   │
│  ────────────────── playhead ▼ ─────────────────│
│  Images    ┃ photo1.png  ┃→┃ photo2.png  ┃→┃   │
│  FX        ·······⚡zoom·························│
│  Eli       ┃ neutral ┃→┃ excited ┃→┃ thinking ┃│
│  In/Out    [  ┃▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓┃    ]  │
├─────────────────────────────────────────────────┤
│  ▶ Play   ◀ -1f  ▶ +1f   Set Marker   0:02.13 │
└─────────────────────────────────────────────────┘
```

### New Components

- **`SceneMicroTimeline.tsx`** — Container that renders the event lanes below the waveform. Shares playhead position with the WaveformSplitter's wavesurfer instance.
- **`ImageLane.tsx`** — Draggable crossfade point markers for multi-frame scenes.
- **`FxLane.tsx`** — Draggable zoom punch trigger marker.
- **`EliLane.tsx`** — Draggable Eli pose transition markers (start_frame/end_frame boundaries).
- **`InOutLane.tsx`** — Draggable left/right handles controlling when the visual appears and disappears within the scene's audio duration.

### Lane Visibility Rules

Lanes only render when the scene has relevant data:

| Scene type | Images | FX | Eli | In/Out |
|------------|--------|----|-----|--------|
| Multi-frame (2+ images) | Yes | If zoom_punch exists | If eli_overlay exists | Always |
| Static single-image | No | If zoom_punch exists | If eli_overlay exists | Always |
| Title card | No | No | No | Always |
| aha_subtitle | No | No | No | Always |

The In/Out lane is always present for any scene with audio — it's the universal visual timing control.

### Audio-Required Gate

The micro-timeline requires audio to function. If a scene has no generated audio:

- All editing lanes are hidden
- The micro-timeline area shows: **"Generate voiceover to enable timing controls"** with a button to generate audio for this scene
- Rationale: without audio, there's no waveform, no word markers, and the scene duration is just an estimate that will change when audio is generated — invalidating any timing work

## Data Model Changes

### New Fields on Scene

```python
# In backend/models/script.py Scene model

frame_timings: list[float] | None = None
# Seconds into scene when each frame starts (multi-frame scenes only).
# e.g., [0.0, 2.3, 5.1] = frame 1 at 0s, frame 2 at 2.3s, frame 3 at 5.1s.
# None = auto-calculate even splits (current behavior, backward compatible).

visual_in_seconds: float = 0.0
# Visual starts this many seconds into the audio.
# 0.0 = image appears immediately (current behavior).

visual_out_seconds: float = 0.0
# Visual ends this many seconds before audio ends.
# 0.0 = image shows until end (current behavior).
```

### Existing Fields Made Editable (No Model Changes)

- **`ZoomPunchFX.trigger_frame: int`** — Already exists. Micro-timeline makes it draggable instead of AI-set-once.
- **`EliKeyframe.start_frame: int` / `end_frame: int`** — Already exist. Micro-timeline makes them draggable.

### Storage

All fields live in the `script_json` blob (same as fx, eli_overlay, word_timestamps). No database migrations. Persisted via the existing `PUT /api/scripts/{script_id}` endpoint.

### TypeScript Mirror

Add matching optional fields to the Scene interface in `frontend/src/types/`:

```typescript
frame_timings?: number[] | null;
visual_in_seconds?: number;
visual_out_seconds?: number;
```

## Interaction Model

### Playback & Navigation

- **Space** — Play/pause audio (existing)
- **Click waveform** — Jump playhead to that position
- **`[` / `]`** — Nudge playhead by 1 frame (1/30s ≈ 33ms)
- **`Shift+[` / `Shift+]`** — Nudge playhead by 10 frames (~333ms)
- Playhead position always displayed as `M:SS.ms` (e.g., `0:02.13`)
- Playhead syncs across waveform and all event lanes

### Placing Markers

1. Select a lane by clicking it or pressing `1-4` (1=Images, 2=FX, 3=Eli, 4=In/Out)
2. Play audio, pause at the desired moment
3. Press `M` (or click "Set Marker" button) to place the event at the playhead position
4. For multi-marker events (crossfades, eli keyframes): each press of `M` places the next marker in sequence

### Dragging Markers

- All markers are draggable along the horizontal timeline axis
- While dragging, a tooltip shows the exact time (seconds and frame number)
- Word boundaries appear as subtle snap guides — markers gravitate toward them within ~100ms proximity
- Hold **Shift while dragging** to disable word-snap for frame-precise placement

### Fine-Tuning

- Click a placed marker to select it (highlighted state)
- **`[` / `]`** — Nudge selected marker by 1 frame (when a marker is selected, these nudge the marker instead of the playhead)
- **`Shift+[` / `Shift+]`** — Nudge selected marker by 10 frames
- **Delete/Backspace** — Remove selected marker (reverts that event to auto-calculated timing)
- **Escape** — Deselect marker, then deselect lane

### In/Out Handles

- Drag from the **left edge** of the In/Out lane to set `visual_in_seconds`
- Drag from the **right edge** to set `visual_out_seconds`
- Double-click a handle to reset to 0 (full duration)
- Handles are clamped to leave at least 0.5s of visible content between them

### Split Shortcut

- **`S`** — Split scene at playhead position (triggers existing word-boundary-snapped split flow)
- Same behavior as clicking "Split Here" in the current waveform splitter, just keyboard-driven

## Edge Cases & Constraints

### Marker Conflicts

- **Crossfade markers** must stay in chronological order. Dragging marker 2 before marker 1 causes them to swap rather than overlap.
- **Eli keyframes** cannot overlap. Dragging one into another's range pushes the neighbor.
- **In-point** cannot exceed out-point. Clamped to always leave ≥0.5s of visible content.

### Regeneration Invalidation

- **Audio regenerated:** All manually placed timings become potentially wrong (different duration, different word boundaries). Keep markers but flag them as stale (yellow highlight) with a warning: "Audio changed — timing markers may need adjustment."
- **FX or Eli regenerated by AI:** New AI values replace manual edits. Show confirmation before regenerating: "This will overwrite your manual timing adjustments for this scene."

### Undo

- All micro-timeline edits flow through `updateScene()` in `useTimelineState`, so they're covered by the existing 50-item undo stack.
- Drag operations fire on mouseup (single undo entry per drag), not continuously during drag.

### Preview Sync

- The Remotion Player in the preview panel reflects timing changes after a short debounce (~300ms), so users can see the effect of adjustments without a full render.

## Remotion Integration

### Props Bridge

Add new fields to `_scene_to_input_props()` in `backend/pipeline/remotion_render.py`:

```python
"frame_timings": scene.frame_timings,          # list[float] | None
"visual_in_seconds": scene.visual_in_seconds,  # float
"visual_out_seconds": scene.visual_out_seconds, # float
```

Add matching fields to Remotion's `remotion/src/types.ts`.

### Rendering Behavior

**Multi-frame crossfades (`frame_timings`):**
- If `frame_timings` is provided, `MultiFrameScene.tsx` uses explicit second values converted to frames (`startFrame = timing * fps`) instead of even splits.
- If null/undefined, falls back to current even-split behavior (backward compatible).
- Crossfade duration between frames stays the same — only the transition point moves.

**Zoom punch (`trigger_frame`):**
- Already passed through and respected by Remotion. No rendering changes needed.

**Eli keyframes (`start_frame`/`end_frame`):**
- Already passed through and respected by Remotion. No rendering changes needed.

**Visual in/out (`visual_in_seconds`/`visual_out_seconds`):**
- New rendering logic in Remotion's scene renderer.
- During `visual_in_seconds` period: show black (or optionally hold last frame of previous scene).
- During `visual_out_seconds` period: cut to black (or optionally start next scene's visual early).
- Audio continues playing throughout — only the visual layer is affected.
- This is the only piece requiring new Remotion rendering logic.

## Keyboard Shortcuts

### New Micro-Timeline Shortcuts

Only active when a scene with audio is selected:

| Key | Action | Context |
|-----|--------|---------|
| `S` | Split scene at playhead | Micro-timeline focused |
| `M` | Place/advance marker at playhead | With a lane selected |
| `[` | Nudge playhead or selected marker -1 frame | Always |
| `]` | Nudge playhead or selected marker +1 frame | Always |
| `Shift+[` | Nudge -10 frames | Always |
| `Shift+]` | Nudge +10 frames | Always |
| `Delete` | Remove selected marker (revert to auto) | With marker selected |
| `1-4` | Select lane (1=Images, 2=FX, 3=Eli, 4=In/Out) | Micro-timeline focused |
| `Escape` | Deselect marker / deselect lane | Micro-timeline focused |

### Existing Shortcuts (Unchanged)

| Key | Action |
|-----|--------|
| `↑` / `↓` | Select previous/next scene |
| `Space` | Play/pause audio |
| `P` | Toggle properties panel |
| `Delete` | Delete selected scene (when no marker selected) |
| `⌘G` | Generate image for scene |
| `⌘⇧G` | Generate all images |
| `⌘Z` | Undo |
| `⌘S` | Save |
| `⌘E` | Open export panel |
| `?` / `⌘/` | Toggle keyboard shortcut cheat sheet |

### Cheat Sheet Icon

- **Location:** Top app bar (Electron title/nav bar), right-aligned
- **Icon:** Keyboard glyph (`⌨`) or question mark badge
- **Behavior:** Click opens the `ShortcutHelpOverlay` modal
- **Sections:** Timeline Navigation, Scene Editing, Micro-Timeline, Global
- **Also toggled by:** `?` key and `⌘/` (existing behavior, now promoted to a visible icon)

## Summary of Changes

### New Files
- `frontend/src/components/timeline/SceneMicroTimeline.tsx` — Container component
- `frontend/src/components/timeline/micro-timeline/ImageLane.tsx`
- `frontend/src/components/timeline/micro-timeline/FxLane.tsx`
- `frontend/src/components/timeline/micro-timeline/EliLane.tsx`
- `frontend/src/components/timeline/micro-timeline/InOutLane.tsx`

### Modified Files
- `backend/models/script.py` — Add `frame_timings`, `visual_in_seconds`, `visual_out_seconds` to Scene
- `backend/pipeline/remotion_render.py` — Pass new fields in `_scene_to_input_props()`
- `frontend/src/types/` — Add matching TypeScript fields to Scene interface
- `frontend/src/components/timeline/useKeyboardShortcuts.tsx` — Add new shortcuts, group into sections
- `frontend/src/components/timeline/ShortcutHelpOverlay` — Expand with sections, promote to global
- `remotion/src/types.ts` — Add new input prop fields
- `remotion/src/scenes/MultiFrameScene.tsx` — Respect `frame_timings` if provided
- `remotion/src/scenes/` (scene renderer) — Implement `visual_in_seconds`/`visual_out_seconds` black frames
- Top app bar component — Add cheat sheet icon button
