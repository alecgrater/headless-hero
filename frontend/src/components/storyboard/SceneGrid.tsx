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
import { SEGMENT_COLORS } from "./SegmentList";

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
}: Props) {
  const [activeScene, setActiveScene] = useState<{
    scene: Scene;
    segIdx: number;
  } | null>(null);

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
    const id = event.active.id as string;
    const segIdx = sceneSegmentMap.current.get(id);
    if (segIdx === undefined) return;
    const scene = content.segments[segIdx].scenes.find((sc) => sc.id === id);
    if (scene) setActiveScene({ scene, segIdx });
  };

  const handleDragEnd = (event: DragEndEvent) => {
    setActiveScene(null);
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

  return (
    <div className="flex-1 overflow-y-auto p-4">
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <div className="space-y-6">
          {content.segments.map((seg, si) => (
            <div
              key={si}
              ref={(el) => {
                if (el) segmentRefs.current.set(si, el);
              }}
            >
              <div className="flex items-center gap-2 mb-3">
                <span
                  className={`w-3 h-3 rounded-full ${SEGMENT_COLORS[si % SEGMENT_COLORS.length]}`}
                />
                <h3 className="text-sm font-semibold text-neutral-300">
                  {si + 1}. {seg.name}
                </h3>
                <span className="text-xs text-neutral-600">
                  {seg.scenes.length} scene
                  {seg.scenes.length !== 1 ? "s" : ""}
                </span>
              </div>
              <SortableContext
                items={seg.scenes.map((sc) => sc.id)}
                strategy={verticalListSortingStrategy}
              >
                <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-3">
                  {seg.scenes.map((scene) => (
                    <SceneCard
                      key={scene.id}
                      scene={scene}
                      segmentIdx={si}
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
          ))}
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
    </div>
  );
}
