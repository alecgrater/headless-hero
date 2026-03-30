import { useMemo } from "react";
import type { ScriptContent } from "../../types/script";
import { SEGMENT_COLORS } from "./constants";

interface Props {
  content: ScriptContent;
  activeSegmentIdx: number | null;
  onSegmentClick: (segmentIdx: number) => void;
  collapsed?: boolean;
  onToggle?: () => void;
  onRegenerateSegmentImages?: (segmentIdx: number) => void;
  onRegenerateSegmentAudio?: (segmentIdx: number) => void;
}

export default function SegmentList({
  content,
  activeSegmentIdx,
  onSegmentClick,
  collapsed = false,
  onToggle,
  onRegenerateSegmentImages,
  onRegenerateSegmentAudio,
}: Props) {
  const totalDuration = useMemo(
    () =>
      content.segments.reduce(
        (sum, seg) =>
          sum +
          seg.scenes.reduce((s, sc) => s + sc.duration_estimate_seconds, 0),
        0,
      ),
    [content.segments],
  );

  // Completion stats
  const completionStats = useMemo(() => {
    let totalScenes = 0;
    let withImage = 0;
    let withAudio = 0;
    for (const seg of content.segments) {
      for (const sc of seg.scenes) {
        totalScenes++;
        if (sc.image_url || sc.video_clip_url) withImage++;
        if (sc.audio_url) withAudio++;
      }
    }
    const complete = Math.min(withImage, withAudio);
    return { totalScenes, withImage, withAudio, complete };
  }, [content.segments]);

  const completionPct = completionStats.totalScenes > 0
    ? completionStats.complete / completionStats.totalScenes
    : 0;

  if (collapsed) {
    return (
      <aside className="w-12 shrink-0 border-r border-neutral-800/60 flex flex-col items-center py-3 gap-2 transition-all duration-300">
        <button
          onClick={onToggle}
          className="text-neutral-500 hover:text-neutral-300 text-sm mb-2 transition-colors"
          title="Expand segments"
        >
          &#x203A;
        </button>
        {content.segments.map((seg, idx) => {
          const isActive = activeSegmentIdx === idx;
          return (
            <button
              key={idx}
              onClick={() => onSegmentClick(idx)}
              className={`w-6 h-6 rounded-full shrink-0 transition-all ${SEGMENT_COLORS[idx % SEGMENT_COLORS.length]} ${
                isActive ? "ring-2 ring-white/30 scale-110" : "opacity-60 hover:opacity-100"
              }`}
              title={seg.name}
            />
          );
        })}
      </aside>
    );
  }

  return (
    <aside className="w-[220px] shrink-0 border-r border-neutral-800/60 overflow-y-auto p-3 space-y-1 transition-all duration-300 flex flex-col">
      <div className="flex items-center justify-between mb-2 px-2">
        <div className="text-[11px] text-neutral-600 uppercase tracking-widest font-medium">
          Segments
        </div>
        {onToggle && (
          <button
            onClick={onToggle}
            className="text-neutral-500 hover:text-neutral-300 text-sm transition-colors"
            title="Collapse segments"
          >
            &#x2039;
          </button>
        )}
      </div>
      {content.segments.map((seg, idx) => {
        const segDuration = seg.scenes.reduce(
          (s, sc) => s + sc.duration_estimate_seconds,
          0,
        );
        const isActive = activeSegmentIdx === idx;
        return (
          <div key={idx} className="group relative">
            <button
              onClick={() => onSegmentClick(idx)}
              className={`w-full text-left px-3 py-2 rounded-lg transition-colors ${
                isActive
                  ? "bg-neutral-800 text-neutral-100"
                  : "text-neutral-400 hover:bg-neutral-800/50 hover:text-neutral-200"
              }`}
            >
              <div className="flex items-center gap-2">
                <span
                  className={`w-2.5 h-2.5 rounded-full shrink-0 ${SEGMENT_COLORS[idx % SEGMENT_COLORS.length]}`}
                />
                <span className="text-sm font-medium truncate" title={seg.name}>{seg.name}</span>
              </div>
              <div className="text-xs text-neutral-500 ml-[18px] mt-0.5">
                {seg.scenes.length} scene{seg.scenes.length !== 1 ? "s" : ""} &middot;{" "}
                {Math.round(segDuration)}s
              </div>
            </button>
            {/* Overflow menu */}
            {(onRegenerateSegmentImages || onRegenerateSegmentAudio) && (
              <SegmentOverflowMenu
                idx={idx}
                onRegenerateImages={onRegenerateSegmentImages ? () => onRegenerateSegmentImages(idx) : undefined}
                onRegenerateAudio={onRegenerateSegmentAudio ? () => onRegenerateSegmentAudio(idx) : undefined}
              />
            )}
          </div>
        );
      })}

      {/* Footer: total duration + completion bar */}
      <div className="mt-auto pt-2 border-t border-neutral-800 px-2 space-y-2">
        <div className="text-xs text-neutral-500">
          Total: ~{Math.round(totalDuration / 60)} min
        </div>
        <div className="space-y-1">
          <div className="flex items-center justify-between text-[10px] text-neutral-500">
            <span>Completion</span>
            <span>{completionStats.complete}/{completionStats.totalScenes}</span>
          </div>
          <div className="h-1 bg-neutral-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-emerald-500 rounded-full transition-all duration-300"
              style={{ width: `${completionPct * 100}%` }}
            />
          </div>
        </div>
      </div>
    </aside>
  );
}

function SegmentOverflowMenu({
  idx: _idx,
  onRegenerateImages,
  onRegenerateAudio,
}: {
  idx: number;
  onRegenerateImages?: () => void;
  onRegenerateAudio?: () => void;
}) {
  return (
    <div className="absolute right-1 top-1.5 opacity-0 group-hover:opacity-100 transition-opacity">
      <div className="relative group/menu">
        <button className="text-neutral-600 hover:text-neutral-300 text-sm px-1 rounded transition-colors">
          &middot;&middot;&middot;
        </button>
        <div className="hidden group-hover/menu:block absolute right-0 top-full mt-1 bg-neutral-800 border border-neutral-700 rounded-lg shadow-xl z-20 py-1 min-w-[180px]">
          {onRegenerateImages && (
            <button
              onClick={(e) => { e.stopPropagation(); onRegenerateImages(); }}
              className="w-full text-left px-3 py-1.5 text-xs text-neutral-300 hover:bg-neutral-700 transition-colors"
            >
              Regenerate All Images
            </button>
          )}
          {onRegenerateAudio && (
            <button
              onClick={(e) => { e.stopPropagation(); onRegenerateAudio(); }}
              className="w-full text-left px-3 py-1.5 text-xs text-neutral-300 hover:bg-neutral-700 transition-colors"
            >
              Regenerate All Audio
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

export { SEGMENT_COLORS };
