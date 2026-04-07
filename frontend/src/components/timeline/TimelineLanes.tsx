import { useRef } from "react";
import TimelineRuler from "./TimelineRuler";
import TimelineBlock from "./TimelineBlock";
import { SEGMENT_COLORS } from "./constants";
import type { ScriptContent, Scene } from "../../types/script";

interface Props {
  content: ScriptContent;
  selectedSceneId: string | null;
  onSelectScene: (sceneId: string) => void;
  pixelsPerSecond: number;
}

const LANE_TYPES = ["images", "voiceover", "fx"] as const;
const LANE_LABELS: Record<(typeof LANE_TYPES)[number], string> = {
  images: "Images",
  voiceover: "Voiceover",
  fx: "FX",
};

export default function TimelineLanes({
  content,
  selectedSceneId,
  onSelectScene,
  pixelsPerSecond,
}: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);

  // Calculate total duration
  let totalDuration = 0;
  for (const segment of content.segments) {
    for (const scene of segment.scenes) {
      totalDuration += scene.audio_duration_seconds || scene.duration_estimate_seconds;
    }
  }

  const totalWidth = totalDuration * pixelsPerSecond;

  // Flatten scenes with segment info for rendering
  const flatScenes: { scene: Scene; segmentIdx: number }[] = [];
  for (let si = 0; si < content.segments.length; si++) {
    for (const scene of content.segments[si].scenes) {
      flatScenes.push({ scene, segmentIdx: si });
    }
  }

  // Calculate segment boundary positions for dividers
  const segmentBoundaries: { x: number; segmentIdx: number }[] = [];
  let cumTime = 0;
  for (let si = 0; si < content.segments.length; si++) {
    if (si > 0) {
      segmentBoundaries.push({ x: cumTime * pixelsPerSecond, segmentIdx: si });
    }
    for (const scene of content.segments[si].scenes) {
      cumTime += scene.audio_duration_seconds || scene.duration_estimate_seconds;
    }
  }

  return (
    <div className="flex flex-col bg-neutral-900 rounded-xl border border-neutral-800 overflow-hidden">
      {/* Scrollable area with label gutter */}
      <div className="flex">
        {/* Fixed label column */}
        <div className="shrink-0 w-20 bg-neutral-900 border-r border-neutral-800 z-10">
          {/* Ruler label spacer */}
          <div className="h-7 border-b border-neutral-800" />
          {LANE_TYPES.map((lane) => (
            <div
              key={lane}
              className="h-10 flex items-center px-3 text-[11px] text-neutral-400 font-medium border-b border-neutral-800/50"
            >
              {LANE_LABELS[lane]}
            </div>
          ))}
        </div>

        {/* Scrollable content */}
        <div ref={scrollRef} className="overflow-x-auto flex-1">
          <div style={{ width: `${Math.max(totalWidth, 200)}px` }}>
            {/* Ruler */}
            <TimelineRuler
              totalDuration={totalDuration}
              pixelsPerSecond={pixelsPerSecond}
              segments={content.segments}
            />

            {/* Lanes */}
            {LANE_TYPES.map((laneType) => (
              <div
                key={laneType}
                className="relative h-10 flex items-center gap-0.5 border-b border-neutral-800/50"
              >
                {/* Scene blocks */}
                {flatScenes.map(({ scene, segmentIdx }) => (
                  <TimelineBlock
                    key={`${laneType}-${scene.id}`}
                    scene={scene}
                    laneType={laneType}
                    pixelsPerSecond={pixelsPerSecond}
                    segmentIdx={segmentIdx}
                    isSelected={scene.id === selectedSceneId}
                    onClick={() => onSelectScene(scene.id)}
                  />
                ))}

                {/* Segment dividers */}
                {segmentBoundaries.map(({ x, segmentIdx }) => (
                  <div
                    key={`div-${laneType}-${segmentIdx}`}
                    className={`absolute top-0 bottom-0 w-px ${
                      SEGMENT_COLORS[segmentIdx % SEGMENT_COLORS.length]
                    } opacity-30`}
                    style={{ left: `${x}px` }}
                  />
                ))}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
