# Scene Preview & Time-Based Split — Design Spec

## Context

The timeline editor currently has no video preview — users must run a full CLI render to see how scenes look. Scene splitting is text-based (sentence boundary), which breaks audio/text sync. This spec adds:

1. **Remotion Player** — real-time in-app preview of individual scenes (image + audio + subtitles + FX)
2. **Time-based splitting** — click a waveform to split a scene at an exact audio timestamp
3. **Properties popup** — the existing scene editor becomes a slide-over, freeing the bottom panel for the Player

## Architecture: Remotion Player Integration

### Cross-Project Import Strategy

The Remotion scene components (`SceneRenderer`, `StaticImageScene`, etc.) live in `remotion/src/`. Rather than duplicating them, the frontend imports them via a Vite alias:

```
frontend/vite.config.ts:  @remotion-src → ../remotion/src/
```

**Key constraints:**
- `remotion`, `@remotion/player`, `@remotion/google-fonts`, `@remotion/paths` are installed in **frontend's** `node_modules` (pinned to `4.0.441` to match `remotion/package.json`). This prevents dual-React-instance crashes.
- Only scene component files are imported (not `Root.tsx` or `styles.css` which register compositions and import Tailwind)
- `tsconfig.app.json` expanded to include `../remotion/src` and add path alias

### Asset Path Mapping

Remotion CLI receives filesystem paths (`/Users/.../data/projects/.../scene_001.png`). The browser-based Player needs HTTP URLs. A utility function `sceneToRemotionInput()` converts:

| Frontend `Scene` field | Remotion `SceneInput` field | Conversion |
|---|---|---|
| `image_url` | `image_path` | `assetUrl(image_url)` → `http://localhost:8420/static/...` |
| `audio_url` | `audio_path` | `assetUrl(audio_url)` |
| `frame_urls` | `frame_paths` | `frame_urls.map(assetUrl)` |
| `audio_duration_seconds \|\| duration_estimate_seconds` | `duration_seconds` | Direct |
| `fx`, `word_timestamps`, `visual_beat`, etc. | Same fields | Direct mapping |

### New Composition: SingleScenePreview

A thin wrapper in `remotion/src/SingleScenePreview.tsx` that renders one `SceneRenderer` — no `Composition` registration, no global overlays (chapter indicators, segment timers). Used exclusively by the `<Player>` component.

## UI Layout: PreviewPanel

Replaces `PropertiesPanel` at the bottom of the timeline page.

```
┌──────────────────────────────────────────────────────────────┐
│ Scene: scene_003 · Caffeine        │ ⚙ Properties │ ▶ 0:03 / 0:08 │
├──────────────────────────────────────────────────────────────┤
│                                           │                  │
│  ┌─────────────────────────────────┐      │ Audio Waveform   │
│  │                                 │      │ ~~~~~~~~~~~~~~~~ │
│  │    Remotion Player (16:9)       │      │    ︱ split mark  │
│  │    Image + Audio + Subtitles    │      │                  │
│  │                                 │      │ [Split Here]     │
│  └─────────────────────────────────┘      │                  │
│  ◄════════════════●════════════════►      │                  │
└──────────────────────────────────────────────────────────────┘
```

- **Left**: Remotion Player (16:9 aspect ratio, fills available height, `controls` enabled for scrub/play/pause)
- **Right**: Waveform display via wavesurfer.js + split controls
- **Header**: Scene ID, segment name, Properties button, playback time

### Properties Popup

The existing `PropertiesPanel` (narration, visual prompt, title card, audio controls, FX display, image preview) opens as a right-side slide-over (~500px wide) via the Properties button or `P` keyboard shortcut.

## Time-Based Scene Splitting

### Frontend: WaveformSplitter Component

Uses `wavesurfer.js` (v7) to render the audio waveform. Click on waveform → places a split marker snapped to nearest word boundary (if `word_timestamps` available). "Split Here" / "Cancel" buttons appear. Confirm triggers the backend split.

### Backend: POST /api/scripts/{id}/split-scene

**Request:** `{ scene_id: str, split_time_ms: int }`

**Algorithm:**
1. Find the word boundary (`word.end_ms`) closest to `split_time_ms`, clamped so neither half is empty
2. Use `actual_split_ms` (the snapped value) for all subsequent operations
3. FFmpeg re-encode split: two commands producing `scene_A.mp3` and `scene_B.mp3`
4. Split `word_timestamps`: first half unchanged, second half zero-rebased (`start_ms -= actual_split_ms`)
5. Reconstruct narration from word tokens (more accurate than text splitting)
6. Set `audio_duration_seconds` for both halves from timestamps
7. Scene B gets new UUID, clears `image_url`/`frame_urls`/`fx` (visuals no longer match truncated narration)
8. Replace original scene in segment with [scene_A, scene_B], persist to DB

**FFmpeg commands:**
```
ffmpeg -y -i input.mp3 -ss 0 -to {split_s} -c:a libmp3lame -b:a 192k first.mp3
ffmpeg -y -i input.mp3 -ss {split_s} -c:a libmp3lame -b:a 192k second.mp3
```

Re-encode (not `-c copy`) avoids frame-boundary audio glitches.

**Response:** Full updated script (same format as GET /api/scripts/{id}).

### Sync Improvements

The existing text-based `splitScene()` in `useTimelineState.ts` splits narration at sentence boundaries and proportionally estimates duration. After splitting, audio/text/timing are out of sync until audio is regenerated. The new time-based split preserves exact sync because audio, timestamps, and narration are all cut at the same millisecond/word boundary.

**Auto-save race condition mitigation:** The `splitSceneAtTime` method clears the debounce timer before calling the API, and sets `isDirty(false)` on success, preventing stale auto-saves from overwriting the backend's split result.

## Frontend Type Changes

Add to `Scene` interface in `frontend/src/types/script.ts`:
```ts
word_timestamps?: WordTimestamp[];
title_card_zoom_target?: { x: number; y: number; radius: number };
```

Add `WordTimestamp` interface (matching `remotion/src/types.ts`).

## Files Created

| File | Purpose |
|------|---------|
| `remotion/src/SingleScenePreview.tsx` | Single-scene composition for Player |
| `frontend/src/components/timeline/PreviewPanel.tsx` | New bottom panel with Player + waveform |
| `frontend/src/components/timeline/PropertiesPopup.tsx` | Slide-over wrapper for PropertiesPanel |
| `frontend/src/components/timeline/WaveformSplitter.tsx` | Waveform display + split marker UI |
| `frontend/src/utils/sceneToRemotionInput.ts` | Scene type conversion utility |
| `backend/pipeline/audio_split.py` | FFmpeg audio split + word-timestamp logic |

## Files Modified

| File | Change |
|------|--------|
| `frontend/package.json` | Add remotion, @remotion/player, @remotion/google-fonts, @remotion/paths, wavesurfer.js |
| `frontend/vite.config.ts` | Add `@remotion-src` path alias |
| `frontend/tsconfig.app.json` | Add baseUrl, paths, expand include |
| `frontend/src/types/script.ts` | Add WordTimestamp, title_card_zoom_target to Scene |
| `frontend/src/api.ts` | Add splitSceneAtTime() function |
| `frontend/src/components/timeline/TimelinePage.tsx` | Swap PropertiesPanel → PreviewPanel + PropertiesPopup |
| `frontend/src/components/timeline/useTimelineState.ts` | Add splitSceneAtTime() method |
| `frontend/src/components/timeline/useKeyboardShortcuts.tsx` | Add P shortcut for properties toggle |
| `frontend/src/components/timeline/PropertiesPanel.tsx` | Remove outer layout classes (handled by popup wrapper) |
| `backend/api/scripts.py` | Add POST /{id}/split-scene endpoint |

## Verification

1. **Player renders correctly:** Select a scene with image + audio → Player shows the scene with subtitles, FX, and synchronized audio
2. **Player scrubbing:** Drag scrubber → frame updates instantly, audio seeks correctly
3. **Properties popup:** Click Properties button or press P → slide-over opens with all editing fields functional
4. **Time-based split:** Click waveform → marker appears at nearest word boundary → "Split Here" → scene splits into two with correct audio, timestamps, and narration
5. **Split sync check:** Play both halves after split → audio matches narration, subtitles appear at correct times
6. **Auto-save safety:** Verify no race conditions by splitting while dirty state exists
