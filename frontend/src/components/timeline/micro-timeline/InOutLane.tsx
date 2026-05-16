import { useCallback, useRef, useState } from "react";
import { type LaneProps, secondsToPx, pxToSeconds, clamp } from "./shared";

interface Props extends LaneProps {
  visualInSeconds: number;
  visualOutSeconds: number;
  onChangeIn: (seconds: number) => void;
  onChangeOut: (seconds: number) => void;
}

const HANDLE_WIDTH = 8;
const MIN_VISIBLE_SECONDS = 0.5;

export default function InOutLane({
  durationSeconds,
  widthPx,
  isSelected,
  onSelect,
  visualInSeconds,
  visualOutSeconds,
  onChangeIn,
  onChangeOut,
}: Props) {
  const laneRef = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState<"in" | "out" | null>(null);

  const inPx = secondsToPx(visualInSeconds, durationSeconds, widthPx);
  const outPx = secondsToPx(durationSeconds - visualOutSeconds, durationSeconds, widthPx);

  const handleMouseDown = useCallback(
    (handle: "in" | "out") => (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragging(handle);

      const onMouseMove = (me: MouseEvent) => {
        if (!laneRef.current) return;
        const rect = laneRef.current.getBoundingClientRect();
        const px = me.clientX - rect.left;
        const sec = pxToSeconds(px, durationSeconds, widthPx);

        if (handle === "in") {
          const maxIn = durationSeconds - visualOutSeconds - MIN_VISIBLE_SECONDS;
          onChangeIn(clamp(sec, 0, Math.max(0, maxIn)));
        } else {
          const rawOut = durationSeconds - sec;
          const maxOut = durationSeconds - visualInSeconds - MIN_VISIBLE_SECONDS;
          onChangeOut(clamp(rawOut, 0, Math.max(0, maxOut)));
        }
      };

      const onMouseUp = () => {
        setDragging(null);
        window.removeEventListener("mousemove", onMouseMove);
        window.removeEventListener("mouseup", onMouseUp);
      };

      window.addEventListener("mousemove", onMouseMove);
      window.addEventListener("mouseup", onMouseUp);
    },
    [durationSeconds, widthPx, visualInSeconds, visualOutSeconds, onChangeIn, onChangeOut],
  );

  const handleDoubleClick = useCallback(
    (handle: "in" | "out") => () => {
      if (handle === "in") onChangeIn(0);
      else onChangeOut(0);
    },
    [onChangeIn, onChangeOut],
  );

  return (
    <div
      ref={laneRef}
      className={`relative h-6 cursor-pointer rounded-sm ${
        isSelected ? "bg-neutral-800" : "bg-neutral-900 hover:bg-neutral-850"
      }`}
      onClick={onSelect}
      title="In/Out"
    >
      {/* Label */}
      <span className="absolute left-1 top-0.5 text-[9px] text-neutral-600 select-none z-10">
        In/Out
      </span>

      {/* Dark overlay for in-region (before visual starts) */}
      {visualInSeconds > 0 && (
        <div
          className="absolute top-0 left-0 h-full bg-black/50 rounded-l-sm"
          style={{ width: inPx }}
        />
      )}

      {/* Dark overlay for out-region (after visual ends) */}
      {visualOutSeconds > 0 && (
        <div
          className="absolute top-0 right-0 h-full bg-black/50 rounded-r-sm"
          style={{ width: widthPx - outPx }}
        />
      )}

      {/* Active region bar */}
      <div
        className="absolute top-1 bottom-1 bg-violet-500/30 border border-violet-500/50 rounded-sm"
        style={{ left: inPx, width: Math.max(0, outPx - inPx) }}
      />

      {/* In handle */}
      <div
        className={`absolute top-0 h-full cursor-col-resize z-20 group ${
          dragging === "in" ? "opacity-100" : ""
        }`}
        style={{ left: inPx - HANDLE_WIDTH / 2, width: HANDLE_WIDTH }}
        onMouseDown={handleMouseDown("in")}
        onDoubleClick={handleDoubleClick("in")}
      >
        <div className="w-0.5 h-full bg-violet-400 mx-auto opacity-60 group-hover:opacity-100 transition-opacity" />
      </div>

      {/* Out handle */}
      <div
        className={`absolute top-0 h-full cursor-col-resize z-20 group ${
          dragging === "out" ? "opacity-100" : ""
        }`}
        style={{ left: outPx - HANDLE_WIDTH / 2, width: HANDLE_WIDTH }}
        onMouseDown={handleMouseDown("out")}
        onDoubleClick={handleDoubleClick("out")}
      >
        <div className="w-0.5 h-full bg-violet-400 mx-auto opacity-60 group-hover:opacity-100 transition-opacity" />
      </div>
    </div>
  );
}
