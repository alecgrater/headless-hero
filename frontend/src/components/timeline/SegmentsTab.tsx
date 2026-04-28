import { useEffect, useRef, useState } from "react";
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
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    segmentRefs.current = segmentRefs.current.slice(0, content.segments.length);
  }, [content.segments.length]);

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

  // Scroll PropertiesPanel into view when a scene is selected
  useEffect(() => {
    if (selectedSceneId && panelRef.current) {
      panelRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [selectedSceneId]);

  return (
    <div className="flex flex-1 overflow-hidden">
      {/* Sidebar */}
      <div className="w-[220px] shrink-0 border-r border-neutral-800/60 overflow-y-auto p-3">
        <p className="text-[10px] font-semibold uppercase tracking-wider text-neutral-500 mb-3 px-2">
          Segments
        </p>
        {content.segments.map((seg, idx) => {
          const totalDuration = seg.scenes.reduce(
            (sum, sc) => sum + (sc.audio_duration_seconds ?? sc.duration_estimate_seconds),
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
        {content.segments.length === 0 && (
          <div className="flex items-center justify-center h-full">
            <p className="text-sm text-neutral-600">No segments in this script</p>
          </div>
        )}
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
                    const duration = scene.audio_duration_seconds ?? scene.duration_estimate_seconds;
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

              {/* Inline PropertiesPanel */}
              {!isCollapsed && selectedSegmentIdx === segIdx && selectedScene && (
                <div ref={panelRef} className="mt-4 border-t border-neutral-800/60 pt-4">
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
