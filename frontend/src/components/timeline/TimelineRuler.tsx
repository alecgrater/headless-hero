import type { Segment } from "../../types/script";

interface Props {
  totalDuration: number;
  pixelsPerSecond: number;
  segments: Segment[];
}

function formatTimestamp(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function TimelineRuler({ totalDuration, pixelsPerSecond }: Props) {
  const totalWidth = totalDuration * pixelsPerSecond;
  const tickCount = Math.ceil(totalDuration);

  return (
    <div
      className="relative h-7 bg-neutral-900 border-b border-neutral-800 select-none shrink-0"
      style={{ width: `${totalWidth}px`, minWidth: "100%" }}
    >
      {/* Tick marks */}
      {Array.from({ length: tickCount + 1 }, (_, i) => {
        const x = i * pixelsPerSecond;
        const isMajor = i % 5 === 0;
        return (
          <div key={i} className="absolute top-0" style={{ left: `${x}px` }}>
            <div
              className={`w-px ${isMajor ? "h-3 bg-neutral-600" : "h-2 bg-neutral-700"}`}
            />
            {isMajor && (
              <span className="absolute top-3 -translate-x-1/2 text-[9px] text-neutral-400 tabular-nums whitespace-nowrap">
                {formatTimestamp(i)}
              </span>
            )}
          </div>
        );
      })}

    </div>
  );
}
