import { useRef } from "react";
import { Image, Mic, Sparkles, User, Timer, Subtitles } from "lucide-react";
import TimelineRuler from "./TimelineRuler";
import TimelineBlock from "./TimelineBlock";
import { SEGMENT_COLORS, SEGMENT_TEXT_COLORS, SEGMENT_BG_COLORS } from "./constants";
import type { ScriptContent, Scene } from "../../types/script";
import type { ProjectConfig } from "../../api";

interface Props {
  content: ScriptContent;
  selectedSceneId: string | null;
  onSelectScene: (sceneId: string) => void;
  pixelsPerSecond: number;
  // Project config (Task 18 will use this to hide EliLane when disabled)
  projectConfig?: ProjectConfig | null;
}

const LANE_TYPES = ["images", "voiceover", "fx", "eli", "timer", "subtitle"] as const;
const LANE_LABELS: Record<(typeof LANE_TYPES)[number], string> = {
  images: "Images",
  voiceover: "Voiceover",
  fx: "FX",
  eli: "Eli",
  timer: "Timer",
  subtitle: "Subtitle",
};

const LANE_ICONS: Record<(typeof LANE_TYPES)[number], typeof Image> = {
  images: Image,
  voiceover: Mic,
  fx: Sparkles,
  eli: User,
  timer: Timer,
  subtitle: Subtitles,
};

export default function TimelineLanes({
  content,
  selectedSceneId,
  onSelectScene,
  pixelsPerSecond,
}: Props) {
  const scrollRef = useRef<HTMLDivElement>(null);

  const GAP_PX = 2; // matches gap-0.5 on lane rows

  // Flatten scenes with segment info for rendering
  const flatScenes: { scene: Scene; segmentIdx: number }[] = [];
  for (let si = 0; si < content.segments.length; si++) {
    for (const scene of content.segments[si].scenes) {
      flatScenes.push({ scene, segmentIdx: si });
    }
  }

  // Calculate total width matching actual flexbox layout (min-width + gaps)
  let totalWidth = 0;
  for (const { scene } of flatScenes) {
    const dur = scene.audio_duration_seconds || scene.duration_estimate_seconds;
    totalWidth += Math.max(40, dur * pixelsPerSecond);
  }
  totalWidth += Math.max(0, flatScenes.length - 1) * GAP_PX;

  // Total duration still needed for ruler
  let totalDuration = 0;
  for (const { scene } of flatScenes) {
    totalDuration += scene.audio_duration_seconds || scene.duration_estimate_seconds;
  }

  // Calculate segment boundary positions and header spans together
  const segmentBoundaries: { x: number; segmentIdx: number }[] = [];
  const segmentSpans: { name: string; x: number; width: number; idx: number }[] = [];
  let offsetX = 0;
  for (let si = 0; si < content.segments.length; si++) {
    const seg = content.segments[si];
    if (si > 0) {
      segmentBoundaries.push({ x: offsetX, segmentIdx: si });
    }
    const startX = offsetX;
    let segWidth = 0;
    for (let i = 0; i < seg.scenes.length; i++) {
      const scene = seg.scenes[i];
      const dur = scene.audio_duration_seconds || scene.duration_estimate_seconds;
      segWidth += Math.max(40, dur * pixelsPerSecond);
      if (i < seg.scenes.length - 1) segWidth += GAP_PX;
    }
    segmentSpans.push({ name: seg.name, x: startX, width: segWidth, idx: si });
    offsetX += segWidth;
    if (si < content.segments.length - 1) {
      offsetX += GAP_PX; // gap before next segment's first block
    }
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
          {LANE_TYPES.map((lane) => {
            const Icon = LANE_ICONS[lane];
            return (
              <div
                key={lane}
                className="h-10 flex items-center gap-1.5 px-3 text-[11px] text-neutral-400 font-medium border-b border-neutral-800/50"
              >
                <Icon size={12} className="shrink-0 text-neutral-500" />
                {LANE_LABELS[lane]}
              </div>
            );
          })}
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
                    segmentTimerEnabled={content.segment_timer_enabled}
                    subtitleHighlightEnabled={content.subtitle_highlight_enabled}
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
