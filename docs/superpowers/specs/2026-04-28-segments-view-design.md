# Segments View — Design Spec

**Date:** 2026-04-28  
**Status:** Approved

## Overview

Add a "Segments" tab as the third view in the timeline page's tab group (alongside Timeline and Media Sources). The view presents scenes grouped by segment in a card-based grid layout, with an inline-expanding PropertiesPanel for editing the selected scene.

## Architecture

**Approach:** Standalone `SegmentsTab` component (Approach A). One new file receives existing state and callbacks from TimelinePage. Reuses the existing PropertiesPanel component for scene editing.

**Tab state change:**
```typescript
type ActiveTab = "timeline" | "media-sources" | "segments";
```

## New File

`frontend/src/components/timeline/SegmentsTab.tsx`

### Props

```typescript
interface SegmentsTabProps {
  content: ScriptContent;
  selectedSceneId: string | null;
  onSelectScene: (sceneId: string | null) => void;
  onUpdateScene: (sceneId: string, updates: Partial<Scene>) => void;
  onGenerateImage: (sceneId: string) => void;
  onGenerateAudio: (sceneId: string) => void;
  generatingSceneIds: Set<string>;
  generatingAudioSceneIds: Set<string>;
}
```

All props already exist in TimelinePage — passed through unchanged.

## Layout

### Segment Group

- **Header row:** Color dot (from `segment.circle_color`, fallback to `SEGMENT_COLORS` in constants.ts) + segment name (bold, white) + scene count (muted gray) + collapse/expand chevron
- **Card grid:** flex-wrap, 3 columns on wide screens, responsive (2 on medium, 1 on narrow)
- **Collapsed state:** Chevron rotates, cards hidden with height transition

### Scene Card

Top to bottom:

1. **Top bar:** Scene ID (monospace, muted), badges (purple "title" pill if `is_title_card`, media source icon), duration label aligned right (from `audio_duration_seconds` if available, else `duration_estimate_seconds`)
2. **Thumbnail area:** Conditional — shown only if `image_url` exists (rendered as background-cover image). If generating, show spinner overlay. If no image, this section is collapsed (not an empty placeholder).
3. **Narration preview:** 2-line clamped text of `scene.narration`
4. **Status row:** Small colored dots — green if `audio_url` exists, violet if `fx` is non-null, teal if `eli_overlay` is non-null

### Card States

- **Default:** `bg-neutral-900 border border-neutral-800 rounded-lg`
- **Hover:** `hover:border-neutral-600 transition-colors`
- **Selected:** `ring-2 ring-violet-500 shadow-lg shadow-violet-500/10`

### Inline PropertiesPanel

- Renders below the selected scene's parent segment (between that segment's card grid and the next segment header)
- Uses the existing `PropertiesPanel` component with all its current functionality (narration edit, visual prompt edit, media source selection, generate buttons, micro-timeline)
- Smooth expand/collapse via `max-height` + `overflow-hidden` transition (or similar CSS approach)

## Interactions

| Action | Result |
|--------|--------|
| Click unselected card | Select scene, expand PropertiesPanel below parent segment |
| Click different card in same segment | PropertiesPanel stays, content updates |
| Click card in different segment | Old panel collapses, new one expands below new segment |
| Click already-selected card | Deselect, collapse PropertiesPanel |
| Collapse segment with selected scene inside | Deselect scene first, collapse panel |

No drag-and-drop reordering in this iteration.

## Changes to Existing Files

### `TimelinePage.tsx`

1. Add `"segments"` to `activeTab` state type
2. Add third tab button in the tab bar
3. Conditionally render `<SegmentsTab>` when `activeTab === "segments"`
4. Pass existing props through

### No other files modified

PropertiesPanel, useTimelineState, types — all unchanged.

## Styling Notes

- Follow existing Tailwind 4 dark theme conventions (`bg-neutral-950/900`, `text-neutral-100/400`)
- Segment color dots match the existing `SEGMENT_COLORS` array in `constants.ts`
- Card widths: `min-w-[280px] max-w-[400px] flex-1` within a flex-wrap container
- Duration badge: `text-xs text-neutral-400` aligned top-right of card
- Status dots: 6px circles with appropriate colors, displayed in a row at card bottom
