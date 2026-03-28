import { useMemo } from "react";
import type { ScriptContent } from "../../types/script";

const SEGMENT_COLORS = [
  "bg-violet-500",
  "bg-sky-500",
  "bg-emerald-500",
  "bg-amber-500",
  "bg-rose-500",
  "bg-cyan-500",
  "bg-fuchsia-500",
  "bg-lime-500",
];

interface Props {
  content: ScriptContent;
  activeSegmentIdx: number | null;
  onSegmentClick: (segmentIdx: number) => void;
}

export default function SegmentList({
  content,
  activeSegmentIdx,
  onSegmentClick,
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

  return (
    <aside className="w-[220px] shrink-0 border-r border-neutral-800/60 overflow-y-auto p-3 space-y-1">
      <div className="text-[11px] text-neutral-600 uppercase tracking-widest font-medium mb-2 px-2">
        Segments
      </div>
      {content.segments.map((seg, idx) => {
        const segDuration = seg.scenes.reduce(
          (s, sc) => s + sc.duration_estimate_seconds,
          0,
        );
        const isActive = activeSegmentIdx === idx;
        return (
          <button
            key={idx}
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
              <span className="text-sm font-medium truncate">{seg.name}</span>
            </div>
            <div className="text-xs text-neutral-500 ml-[18px] mt-0.5">
              {seg.scenes.length} scene{seg.scenes.length !== 1 ? "s" : ""} &middot;{" "}
              {Math.round(segDuration)}s
            </div>
          </button>
        );
      })}
      <div className="border-t border-neutral-800 pt-2 mt-2 px-2 text-xs text-neutral-500">
        Total: ~{Math.round(totalDuration / 60)} min
      </div>
    </aside>
  );
}

export { SEGMENT_COLORS };
