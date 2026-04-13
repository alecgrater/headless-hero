import { useRef } from "react";
import TimelineRuler from "./TimelineRuler";
import TimelineBlock from "./TimelineBlock";
import { SEGMENT_COLORS, SEGMENT_TEXT_COLORS, SEGMENT_BG_COLORS } from "./constants";
import type { ScriptContent, Scene } from "../../types/script";

interface Props {
  content: ScriptContent;
  selectedSceneId: string | null;
  onSelectScene: (sceneId: string) => void;
  pixelsPerSecond: number;
}

const LANE_TYPES = ["images", "voiceover", "fx", "eli"] as const;
const LANE_LABELS: Record<(typeof LANE_TYPES)[number], string> = {
  images: "Images",
  voiceover: "Voiceover",
  fx: "FX",
  eli: "Eli",
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

  // Calculate segment spans for header row
  const segmentSpans: { name: string; x: number; width: number; idx: number }[] = [];
  let spanTime = 0;
  for (let si = 0; si < content.segments.length; si++) {
    const seg = content.segments[si];
    const startX = spanTime * pixelsPerSecond;
    let segDuration = 0;
    for (const scene of seg.scenes) {
      segDuration += scene.audio_duration_seconds || scene.duration_estimate_seconds;
    }
    segmentSpans.push({ name: seg.name, x: startX, width: segDuration * pixelsPerSecond, idx: si });
    spanTime += segDuration;
  }

  return (
    <div className="flex flex-col bg-neutral-900 rounded-xl border border-neutral-800 overflow-hidden">
      {/* Scrollable area with label gutter */}
      <div className="flex">
        {/* Fixed label column */}
        <div className="shrink-0 w-20 bg-neutral-900 border-r border-neutral-800 z-10">
          {/* Ruler spacer */}
          <div className="h-7 border-b border-neutral-800 flex items-center justify-center gap-1 px-1">
            <span className="text-[10px] text-neutral-500 font-mono">{pixelsPerSecond}</span>
          </div>
          {/* Segment header label */}
          <div className="h-6 flex items-center px-3 text-[10px] text-neutral-500 font-medium border-b border-neutral-800/50">
            Segments
          </div>
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

            {/* Segment header row */}
            <div className="relative h-6 flex border-b border-neutral-800/50">
              {segmentSpans.map(({ name, x, width, idx }) => (
                <div
                  key={`seg-header-${idx}`}
                  className={`absolute top-0 h-full flex items-center overflow-hidden ${
                    SEGMENT_BG_COLORS[idx % SEGMENT_BG_COLORS.length]
                  }`}
                  style={{ left: `${x}px`, width: `${width}px` }}
                >
                  <span
                    className={`text-[10px] font-medium truncate px-2 ${
                      SEGMENT_TEXT_COLORS[idx % SEGMENT_TEXT_COLORS.length]
                    }`}
                  >
                    {name}
                  </span>
                </div>
              ))}
            </div>

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
