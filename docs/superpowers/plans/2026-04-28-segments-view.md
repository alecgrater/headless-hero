# Segments View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Segments" tab as the third view in the timeline page, showing scenes grouped by segment in a card grid with a navigation sidebar and inline-expanding PropertiesPanel.

**Architecture:** Single new component `SegmentsTab.tsx` receives existing state/callbacks from TimelinePage. Two-column layout: fixed-width sidebar (segment navigation with intersection observer sync) + scrollable main area (segment groups with scene cards). Clicking a card selects it via the existing `state.selectScene()` mechanism; PropertiesPanel renders inline below the parent segment.

**Tech Stack:** React 19, TypeScript, Tailwind 4, existing PropertiesPanel component, IntersectionObserver API

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `frontend/src/components/timeline/SegmentsTab.tsx` | Create | Main segments view: sidebar + card grid + inline PropertiesPanel |
| `frontend/src/components/timeline/TimelinePage.tsx` | Modify (lines 221, 1212-1237, 1240-1315) | Add third tab state, button, and conditional render |

---

### Task 1: Create SegmentsTab component skeleton with sidebar

**Files:**
- Create: `frontend/src/components/timeline/SegmentsTab.tsx`

- [ ] **Step 1: Create SegmentsTab with props interface and two-column layout**

```tsx
import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { assetUrl } from "../../api";
import type { Scene, ScriptContent } from "../../types/script";
import { SEGMENT_COLORS } from "./constants";
import type { MicroTimelineHandle } from "./SceneMicroTimeline";
import PropertiesPanel from "./PropertiesPanel";

interface SegmentsTabProps {
  content: ScriptContent;
  scriptId: string;
  selectedSceneId: string | null;
  onSelectScene: (sceneId: string | null) => void;
  onUpdateScene: (sceneId: string, updates: Partial<Scene>) => void;
  onGenerateImage: (sceneId: string) => void;
  onGenerateAudio: (sceneId: string) => void;
  generatingSceneIds: Set<string>;
  generatingAudioSceneIds: Set<string>;
}

export default function SegmentsTab({
  content,
  scriptId,
  selectedSceneId,
  onSelectScene,
  onUpdateScene,
  onGenerateImage,
  onGenerateAudio,
  generatingSceneIds,
  generatingAudioSceneIds,
}: SegmentsTabProps) {
  const [collapsedSegments, setCollapsedSegments] = useState<Set<number>>(new Set());
  const [activeSegmentIdx, setActiveSegmentIdx] = useState(0);
  const mainRef = useRef<HTMLDivElement>(null);
  const segmentRefs = useRef<(HTMLDivElement | null)[]>([]);
  const microTimelineRef = useRef<MicroTimelineHandle>(null);

  const toggleCollapse = (idx: number) => {
    setCollapsedSegments((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) {
        next.delete(idx);
      } else {
        if (selectedSceneId) {
          const seg = content.segments[idx];
          if (seg.scenes.some((sc) => sc.id === selectedSceneId)) {
            onSelectScene(null);
          }
        }
        next.add(idx);
      }
      return next;
    });
  };

  const scrollToSegment = (idx: number) => {
    segmentRefs.current[idx]?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  // Intersection observer to track active segment in sidebar
  useEffect(() => {
    const container = mainRef.current;
    if (!container) return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            const idx = segmentRefs.current.indexOf(entry.target as HTMLDivElement);
            if (idx !== -1) setActiveSegmentIdx(idx);
          }
        }
      },
      { root: container, rootMargin: "-10% 0px -80% 0px", threshold: 0 },
    );
    segmentRefs.current.forEach((el) => {
      if (el) observer.observe(el);
    });
    return () => observer.disconnect();
  }, [content.segments.length]);

  const handleCardClick = (sceneId: string) => {
    if (selectedSceneId === sceneId) {
      onSelectScene(null);
    } else {
      onSelectScene(sceneId);
    }
  };

  // Find selected scene's segment index for inline panel placement
  const selectedSegmentIdx = selectedSceneId
    ? content.segments.findIndex((seg) => seg.scenes.some((sc) => sc.id === selectedSceneId))
    : -1;
  const selectedScene = selectedSceneId
    ? content.segments[selectedSegmentIdx]?.scenes.find((sc) => sc.id === selectedSceneId) ?? null
    : null;

  return (
    <div className="flex flex-1 overflow-hidden">
      {/* Sidebar */}
      <div className="w-[220px] shrink-0 border-r border-neutral-800/60 overflow-y-auto p-3">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-neutral-500 mb-3 px-2">
          Segments
        </p>
        {content.segments.map((seg, idx) => {
          const totalDuration = seg.scenes.reduce(
            (sum, sc) => sum + (sc.audio_duration_seconds || sc.duration_estimate_seconds),
            0,
          );
          const colorClass = SEGMENT_COLORS[idx % SEGMENT_COLORS.length];
          return (
            <button
              key={idx}
              onClick={() => scrollToSegment(idx)}
              className={`w-full text-left px-3 py-2.5 rounded-lg mb-1 transition-colors ${
                activeSegmentIdx === idx
                  ? "bg-neutral-800/50"
                  : "hover:bg-neutral-800/30"
              }`}
            >
              <div className="flex items-center gap-2">
                <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${colorClass}`} />
                <span className="text-sm font-medium text-neutral-100 truncate">
                  {seg.name}
                </span>
              </div>
              <p className="text-[11px] text-neutral-500 ml-[18px] mt-0.5">
                {seg.scenes.length} scenes · {Math.round(totalDuration)}s
              </p>
            </button>
          );
        })}
      </div>

      {/* Main card grid area */}
      <div ref={mainRef} className="flex-1 overflow-y-auto p-5 space-y-8">
        {content.segments.map((seg, segIdx) => {
          const colorClass = SEGMENT_COLORS[segIdx % SEGMENT_COLORS.length];
          const isCollapsed = collapsedSegments.has(segIdx);
          return (
            <div
              key={segIdx}
              ref={(el) => { segmentRefs.current[segIdx] = el; }}
            >
              {/* Segment header */}
              <button
                onClick={() => toggleCollapse(segIdx)}
                className="flex items-center gap-2 mb-3 group w-full text-left"
              >
                <span className={`w-3 h-3 rounded-full ${colorClass}`} />
                <h3 className="text-sm font-bold text-neutral-100">
                  {segIdx + 1}. {seg.name}
                </h3>
                <span className="text-xs text-neutral-500">
                  {seg.scenes.length} scenes
                </span>
                <span className="ml-auto text-neutral-500 group-hover:text-neutral-300 transition-colors">
                  {isCollapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
                </span>
              </button>

              {/* Card grid */}
              {!isCollapsed && (
                <div className="flex flex-wrap gap-3">
                  {seg.scenes.map((scene) => {
                    const duration = scene.audio_duration_seconds || scene.duration_estimate_seconds;
                    const isSelected = selectedSceneId === scene.id;
                    const isGeneratingImg = generatingSceneIds.has(scene.id);
                    return (
                      <div
                        key={scene.id}
                        onClick={() => handleCardClick(scene.id)}
                        className={`min-w-[280px] max-w-[400px] flex-1 rounded-lg border p-3 cursor-pointer transition-all ${
                          isSelected
                            ? "ring-2 ring-violet-500 shadow-lg shadow-violet-500/10 border-violet-500/50 bg-neutral-900"
                            : "border-neutral-800 bg-neutral-900 hover:border-neutral-600"
                        }`}
                      >
                        {/* Top bar */}
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <span className="text-[11px] font-mono text-neutral-500">{scene.id}</span>
                            {scene.is_title_card && (
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-violet-500/20 text-violet-300 font-medium">
                                title
                              </span>
                            )}
                          </div>
                          <span className="text-xs text-neutral-400">{Math.round(duration)}s</span>
                        </div>

                        {/* Thumbnail */}
                        {(scene.image_url || isGeneratingImg) && (
                          <div className="relative mb-2 rounded overflow-hidden aspect-video bg-neutral-800">
                            {scene.image_url && (
                              <img
                                src={assetUrl(scene.image_url)}
                                alt=""
                                className="w-full h-full object-cover"
                              />
                            )}
                            {isGeneratingImg && (
                              <div className="absolute inset-0 flex items-center justify-center bg-neutral-900/60">
                                <div className="w-5 h-5 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
                              </div>
                            )}
                          </div>
                        )}

                        {/* Narration preview */}
                        <p className="text-xs text-neutral-300 line-clamp-2 mb-2">
                          {scene.narration}
                        </p>

                        {/* Status dots */}
                        <div className="flex items-center gap-1.5">
                          {scene.audio_url && (
                            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" title="Audio" />
                          )}
                          {scene.fx && (
                            <span className="w-1.5 h-1.5 rounded-full bg-violet-500" title="FX" />
                          )}
                          {scene.eli_overlay && (
                            <span className="w-1.5 h-1.5 rounded-full bg-cyan-500" title="Eli" />
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}

              {/* Inline PropertiesPanel — renders below this segment's cards when a scene in this segment is selected */}
              {!isCollapsed && selectedSegmentIdx === segIdx && selectedScene && (
                <div className="mt-4 border-t border-neutral-800/60 pt-4">
                  <PropertiesPanel
                    scene={selectedScene}
                    segmentIdx={segIdx}
                    segmentName={seg.name}
                    scriptId={scriptId}
                    onUpdate={(updates) => onUpdateScene(selectedScene.id, updates)}
                    onGenerateImage={() => onGenerateImage(selectedScene.id)}
                    isGenerating={generatingSceneIds.has(selectedScene.id)}
                    onGenerateAudio={() => onGenerateAudio(selectedScene.id)}
                    isGeneratingAudio={generatingAudioSceneIds.has(selectedScene.id)}
                    microTimelineRef={microTimelineRef}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify the file compiles**

Run: `cd frontend && npx tsc --noEmit --skipLibCheck 2>&1 | head -20`
Expected: No errors from SegmentsTab.tsx (may have unrelated errors elsewhere)

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/timeline/SegmentsTab.tsx
git commit -m "Add SegmentsTab component with sidebar and card grid"
```

---

### Task 2: Wire SegmentsTab into TimelinePage

**Files:**
- Modify: `frontend/src/components/timeline/TimelinePage.tsx` (lines 221, 1212-1237, 1240-1315)

- [ ] **Step 1: Import SegmentsTab**

At the top of TimelinePage.tsx, add after the `import MediaSourcesTab` line (line 13):

```tsx
import SegmentsTab from "./SegmentsTab";
```

- [ ] **Step 2: Update activeTab state type**

Change line 221 from:
```tsx
const [activeTab, setActiveTab] = useState<"timeline" | "media-sources">("timeline");
```
to:
```tsx
const [activeTab, setActiveTab] = useState<"timeline" | "media-sources" | "segments">("timeline");
```

- [ ] **Step 3: Add the third tab button**

After the "Media Sources" button (around line 1235, before the closing `</div>` of the tab bar), add:

```tsx
          <button
            onClick={() => setActiveTab("segments")}
            className={`px-4 py-1.5 text-xs font-medium rounded-lg transition-all duration-200 ${
              activeTab === "segments"
                ? "bg-neutral-700/80 text-white shadow-sm"
                : "text-neutral-400 hover:text-neutral-200"
            }`}
          >
            Segments
          </button>
```

- [ ] **Step 4: Add conditional render for SegmentsTab**

The current tab content section (lines 1240-1315) has the shape:
```tsx
{activeTab === "media-sources" ? (
  <MediaSourcesTab ... />
) : (
  /* timeline content */
)}
```

Change it to handle three tabs:
```tsx
      {activeTab === "media-sources" ? (
        <MediaSourcesTab
          scriptId={scriptId}
          content={state.content}
          mediaAssignments={media.mediaAssignments}
          mediaAnalyzing={media.mediaAnalyzing}
          mediaReviewDismissed={media.mediaReviewDismissed}
          onAnalyzeMedia={media.handleAnalyzeMedia}
          onApproved={() => {
            media.setMediaReviewDismissed(true);
            state.generateAllImages();
            setActiveTab("timeline");
          }}
        />
      ) : activeTab === "segments" ? (
        <SegmentsTab
          content={state.content}
          scriptId={scriptId}
          selectedSceneId={state.selectedSceneId}
          onSelectScene={(id) => id ? state.selectScene(id) : state.selectScene("")}
          onUpdateScene={(id, updates) => state.updateScene(id, updates)}
          onGenerateImage={(id) => state.generateImage(id)}
          onGenerateAudio={(id) => tryGenerateAudio(id)}
          generatingSceneIds={state.generatingSceneIds}
          generatingAudioSceneIds={state.generatingAudioSceneIds}
        />
      ) : (
      /* existing timeline content unchanged */
      <div className="flex flex-col flex-1 overflow-hidden">
        ...
      </div>
      )}
```

Note: The `onSelectScene` prop accepts `string | null`. The existing `state.selectScene` takes a `string`. For deselection (passing `null`), pass an empty string which the useTimelineState hook will treat as "no selection". Check how `selectScene` handles empty string — if it doesn't deselect, we'll need to adjust.

- [ ] **Step 5: Verify selectScene behavior with empty string or null**

Check how `selectScene` is defined in `useTimelineState.ts`. If it doesn't handle deselection cleanly, adjust the `onSelectScene` callback to call the appropriate deselection method. The hook likely has `selectScene(id: string)` that sets `selectedSceneId` — passing empty string should work as deselection since no scene has an empty ID.

Run: `grep -n "selectScene" frontend/src/components/timeline/useTimelineState.ts | head -5`

If it sets state directly, empty string will work. If it guards against invalid IDs, we may need to add a `deselectScene` or use `setSelectedSceneId(null)` if exposed.

- [ ] **Step 6: Verify compilation and test in browser**

Run: `cd frontend && npx tsc --noEmit --skipLibCheck 2>&1 | head -20`

Then start the dev server (`npm run dev`) and verify:
1. The "Segments" tab button appears in the tab bar
2. Clicking it shows the segments view with sidebar + card grid
3. Clicking a card selects it (violet ring)
4. PropertiesPanel appears inline below the segment
5. Clicking another card in a different segment moves the panel
6. Clicking the selected card again deselects
7. Sidebar highlights update when scrolling
8. Clicking sidebar items scrolls to the segment

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/timeline/TimelinePage.tsx
git commit -m "Wire SegmentsTab as third tab in timeline page"
```

---

### Task 3: Polish and edge cases

**Files:**
- Modify: `frontend/src/components/timeline/SegmentsTab.tsx`

- [ ] **Step 1: Handle empty state**

If a script has no segments (shouldn't happen in practice but good defensive UI), add a fallback below the sidebar in the main area:

```tsx
{content.segments.length === 0 && (
  <div className="flex items-center justify-center h-full">
    <p className="text-sm text-neutral-600">No segments in this script</p>
  </div>
)}
```

- [ ] **Step 2: Ensure segmentRefs array stays in sync**

The `segmentRefs.current` array length should match `content.segments.length`. Add at the top of the component:

```tsx
segmentRefs.current = segmentRefs.current.slice(0, content.segments.length);
```

This ensures refs don't go stale if segments change (e.g., script regeneration).

- [ ] **Step 3: Verify the intersection observer cleans up properly**

The `useEffect` with the observer depends on `content.segments.length`. When segments change, it disconnects old observer and creates a new one. Confirm this works by checking the dependency array includes `content.segments.length`.

- [ ] **Step 4: Test in browser**

Verify:
1. Collapsing a segment with a selected scene deselects it
2. The sidebar "active" highlight tracks scrolling correctly
3. Cards with no image show no thumbnail area (no empty space)
4. Cards with generating images show the spinner
5. Status dots appear correctly for scenes with audio/FX/Eli

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/timeline/SegmentsTab.tsx
git commit -m "Add edge case handling for SegmentsTab"
```
