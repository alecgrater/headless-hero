import {
  DndContext,
  DragOverlay,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { useRef, useState } from "react";
import type { Scene, ScriptContent } from "../../types/script";
import SceneCard from "./SceneCard";
import { SEGMENT_COLORS } from "./constants";

interface Props {
  content: ScriptContent;
  selectedSceneId: string | null;
  segmentRefs: React.MutableRefObject<Map<number, HTMLDivElement>>;
  onSelectScene: (sceneId: string) => void;
  onNarrationChange: (sceneId: string, narration: string) => void;
  onMoveScene: (
    sceneId: string,
    fromSegIdx: number,
    toSegIdx: number,
    newIndex: number,
  ) => void;
  onGenerateImage?: (sceneId: string) => void;
  generatingSceneIds?: Set<string>;
  onGenerateAudio?: (sceneId: string) => void;
  generatingAudioSceneIds?: Set<string>;
  batchImageStatuses?: Map<string, "idle" | "pending" | "generating" | "done" | "failed">;
  onRetryImage?: (sceneId: string) => void;
  onBulkGenerateImages?: (ids: string[]) => void;
  onBulkGenerateAudio?: (ids: string[]) => void;
}

export default function SceneGrid({
  content,
  selectedSceneId,
  segmentRefs,
  onSelectScene,
  onNarrationChange,
  onMoveScene,
  onGenerateImage,
  generatingSceneIds,
  onGenerateAudio,
  generatingAudioSceneIds,
  batchImageStatuses,
  onRetryImage,
  onBulkGenerateImages,
  onBulkGenerateAudio,
}: Props) {
  const [activeScene, setActiveScene] = useState<{
    scene: Scene;
    segIdx: number;
  } | null>(null);

  const [bulkMode, setBulkMode] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [collapsedSegments, setCollapsedSegments] = useState<Set<number>>(new Set());

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
  );

  // Map scene IDs to their segment index for cross-segment detection
  const sceneSegmentMap = useRef(new Map<string, number>());
  sceneSegmentMap.current.clear();
  content.segments.forEach((seg, si) => {
    seg.scenes.forEach((sc) => {
      sceneSegmentMap.current.set(sc.id, si);
    });
  });

  const handleDragStart = (event: DragStartEvent) => {
    if (bulkMode) return;
    const id = event.active.id as string;
    const segIdx = sceneSegmentMap.current.get(id);
    if (segIdx === undefined) return;
    const scene = content.segments[segIdx].scenes.find((sc) => sc.id === id);
    if (scene) setActiveScene({ scene, segIdx });
  };

  const handleDragEnd = (event: DragEndEvent) => {
    setActiveScene(null);
    if (bulkMode) return;
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const activeId = active.id as string;
    const overId = over.id as string;

    const fromSegIdx = sceneSegmentMap.current.get(activeId);
    let toSegIdx = sceneSegmentMap.current.get(overId);

    if (fromSegIdx === undefined) return;

    // Check if dropping on a segment drop zone
    if (toSegIdx === undefined) {
      const match = overId.match(/^segment-dropzone-(\d+)$/);
      if (match) {
        toSegIdx = parseInt(match[1], 10);
        onMoveScene(
          activeId,
          fromSegIdx,
          toSegIdx,
          content.segments[toSegIdx].scenes.length,
        );
        return;
      }
      return;
    }

    const toScenes = content.segments[toSegIdx].scenes;
    const newIndex = toScenes.findIndex((sc) => sc.id === overId);

    onMoveScene(activeId, fromSegIdx, toSegIdx, newIndex >= 0 ? newIndex : 0);
  };

  const toggleSegmentCollapse = (segIdx: number) => {
    setCollapsedSegments((prev) => {
      const next = new Set(prev);
      if (next.has(segIdx)) next.delete(segIdx);
      else next.add(segIdx);
      return next;
    });
  };

  const toggleBulkCheck = (sceneId: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(sceneId)) next.delete(sceneId);
      else next.add(sceneId);
      return next;
    });
  };

  const selectAllInSegment = (segIdx: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      for (const sc of content.segments[segIdx].scenes) {
        next.add(sc.id);
      }
      return next;
    });
  };

  const exitBulkMode = () => {
    setBulkMode(false);
    setSelectedIds(new Set());
  };

  return (
    <div className="flex-1 overflow-y-auto p-5 flex flex-col">
      {/* Bulk mode toggle */}
      <div className="flex items-center gap-2 mb-4">
        <button
          onClick={() => bulkMode ? exitBulkMode() : setBulkMode(true)}
          className={`text-xs px-3 py-1.5 rounded-lg border transition-colors font-medium ${
            bulkMode
              ? "bg-violet-500/20 border-violet-500/30 text-violet-300"
              : "bg-neutral-800/50 border-neutral-700/50 text-neutral-500 hover:text-neutral-300 hover:border-neutral-600"
          }`}
        >
          {bulkMode ? "Cancel Select" : "Select"}
        </button>
        {bulkMode && selectedIds.size > 0 && (
          <span className="text-xs text-neutral-400">{selectedIds.size} selected</span>
        )}
      </div>

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <div className="space-y-8 flex-1">
          {content.segments.map((seg, si) => {
            // Compute scene number offset for this segment
            let sceneOffset = 0;
            for (let i = 0; i < si; i++) {
              sceneOffset += content.segments[i].scenes.length;
            }
            const isCollapsed = collapsedSegments.has(si);
            return (
            <div
              key={si}
              ref={(el) => {
                if (el) segmentRefs.current.set(si, el);
              }}
            >
              <div className="flex items-center gap-2 mb-4">
                <button
                  onClick={() => toggleSegmentCollapse(si)}
                  className="text-neutral-500 hover:text-neutral-300 text-xs transition-colors"
                >
                  {isCollapsed ? "▶" : "▼"}
                </button>
                <span
                  className={`w-2.5 h-2.5 rounded-full ${SEGMENT_COLORS[si % SEGMENT_COLORS.length]}`}
                />
                <h3 className="text-sm font-medium tracking-wide text-neutral-300">
                  {si + 1}. {seg.name}
                </h3>
                <span className="text-[11px] text-neutral-600 bg-neutral-800/60 px-2 py-0.5 rounded-full">
                  {seg.scenes.length} scene
                  {seg.scenes.length !== 1 ? "s" : ""}
                </span>
                {bulkMode && (
                  <button
                    onClick={() => selectAllInSegment(si)}
                    className="text-[10px] text-neutral-500 hover:text-neutral-300 transition-colors"
                  >
                    Select All
                  </button>
                )}
                <div className="flex-1 h-px bg-neutral-800/60 ml-2" />
              </div>
              <div
                className={`overflow-hidden transition-all duration-300 ${
                  isCollapsed ? "max-h-0" : "max-h-[4000px]"
                }`}
              >
                <SortableContext
                  items={seg.scenes.map((sc) => sc.id)}
                  strategy={verticalListSortingStrategy}
                >
                  <div className="grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-4">
                    {seg.scenes.map((scene, scIdx) => (
                      <SceneCard
                        key={scene.id}
                        scene={scene}
                        segmentIdx={si}
                        sceneNumber={sceneOffset + scIdx + 1}
                        isSelected={selectedSceneId === scene.id}
                        onClick={() => onSelectScene(scene.id)}
                        onNarrationChange={(narr) =>
                          onNarrationChange(scene.id, narr)
                        }
                        onGenerateImage={
                          onGenerateImage
                            ? () => onGenerateImage(scene.id)
                            : undefined
                        }
                        isGenerating={generatingSceneIds?.has(scene.id)}
                        onGenerateAudio={
                          onGenerateAudio
                            ? () => onGenerateAudio(scene.id)
                            : undefined
                        }
                        isGeneratingAudio={generatingAudioSceneIds?.has(scene.id)}
                        batchImageStatus={batchImageStatuses?.get(scene.id)}
                        onRetryImage={
                          onRetryImage
                            ? () => onRetryImage(scene.id)
                            : undefined
                        }
                        bulkMode={bulkMode}
                        isChecked={selectedIds.has(scene.id)}
                        onToggleCheck={() => toggleBulkCheck(scene.id)}
                      />
                    ))}
                    {/* Empty segment drop zone */}
                    {seg.scenes.length === 0 && (
                      <div className="border-2 border-dashed border-neutral-700 rounded-lg h-32 flex items-center justify-center text-neutral-600 text-sm">
                        Drop scenes here
                      </div>
                    )}
                  </div>
                </SortableContext>
              </div>
            </div>
          );
          })}
        </div>

        <DragOverlay>
          {activeScene && (
            <div className="rounded-lg border border-violet-500 bg-neutral-900 px-3 py-2.5 shadow-xl shadow-violet-500/10 opacity-90 w-[220px]">
              <div className="text-[10px] font-mono text-neutral-500 mb-1">
                {activeScene.scene.id}
              </div>
              <p className="text-xs text-neutral-400 line-clamp-3">
                {activeScene.scene.narration}
              </p>
            </div>
          )}
        </DragOverlay>
      </DndContext>

      {/* Bulk action bar */}
      {bulkMode && selectedIds.size > 0 && (
        <div className="sticky bottom-0 mt-4 bg-neutral-900/95 border border-neutral-700/60 rounded-xl p-3 flex items-center gap-3 backdrop-blur-sm shadow-xl shadow-black/30">
          <span className="text-sm text-neutral-300 font-medium">
            {selectedIds.size} selected
          </span>
          <div className="flex-1" />
          {onBulkGenerateImages && (
            <button
              onClick={() => onBulkGenerateImages(Array.from(selectedIds))}
              className="text-xs px-3 py-1.5 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 hover:bg-emerald-500/20 rounded-lg transition-colors font-medium"
            >
              Regenerate Images
            </button>
          )}
          {onBulkGenerateAudio && (
            <button
              onClick={() => onBulkGenerateAudio(Array.from(selectedIds))}
              className="text-xs px-3 py-1.5 bg-sky-500/10 border border-sky-500/20 text-sky-400 hover:bg-sky-500/20 rounded-lg transition-colors font-medium"
            >
              Regenerate Audio
            </button>
          )}
          <button
            onClick={exitBulkMode}
            className="text-xs px-3 py-1.5 bg-neutral-800 text-neutral-400 hover:text-neutral-200 rounded-lg transition-colors"
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}
