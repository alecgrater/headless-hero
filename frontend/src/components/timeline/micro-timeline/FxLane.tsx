import { useCallback, useRef, useState } from "react";
import type { WordTimestamp } from "../../../types/script";
import {
  type LaneProps,
  secondsToPx,
  pxToSeconds,
  clamp,
  snapToWordBoundary,
  FPS,
} from "./shared";

interface Props extends LaneProps {
  /** Zoom punch trigger frame number. */
  triggerFrame: number;
  wordTimestamps?: WordTimestamp[] | null;
  onChange: (triggerFrame: number) => void;
  isMarkerSelected: boolean;
  onSelectMarker: (selected: boolean) => void;
  shiftHeld: boolean;
}

const MARKER_WIDTH = 12;

export default function FxLane({
  durationSeconds,
  widthPx,
  isSelected,
  onSelect,
  triggerFrame,
  wordTimestamps,
  onChange,
  isMarkerSelected,
  onSelectMarker,
  shiftHeld,
}: Props) {
  const laneRef = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState(false);

  const triggerSeconds = triggerFrame / FPS;
  const triggerPx = secondsToPx(triggerSeconds, durationSeconds, widthPx);

  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragging(true);
      onSelectMarker(true);

      const onMouseMove = (me: MouseEvent) => {
        if (!laneRef.current) return;
        const rect = laneRef.current.getBoundingClientRect();
        const px = me.clientX - rect.left;
        let sec = pxToSeconds(px, durationSeconds, widthPx);

        if (!shiftHeld) {
          sec = snapToWordBoundary(sec, wordTimestamps);
        }

        sec = clamp(sec, 0, durationSeconds);
        onChange(Math.round(sec * FPS));
      };

      const onMouseUp = () => {
        setDragging(false);
        window.removeEventListener("mousemove", onMouseMove);
        window.removeEventListener("mouseup", onMouseUp);
      };

      window.addEventListener("mousemove", onMouseMove);
      window.addEventListener("mouseup", onMouseUp);
    },
    [durationSeconds, widthPx, wordTimestamps, onChange, onSelectMarker, shiftHeld],
  );

  const isActive = isMarkerSelected || dragging;

  return (
    <div
      ref={laneRef}
      className={`relative h-6 cursor-pointer rounded-sm ${
        isSelected ? "bg-neutral-800" : "bg-neutral-900 hover:bg-neutral-850"
      }`}
      onClick={onSelect}
      title="FX"
    >
      {/* Label */}
      <span className="absolute left-1 top-0.5 text-[9px] text-neutral-600 select-none z-10">
        FX
      </span>

      {/* Zoom punch marker */}
      <div
        className="absolute top-0 h-full cursor-col-resize z-20 group"
        style={{ left: triggerPx - MARKER_WIDTH / 2, width: MARKER_WIDTH }}
        onMouseDown={handleMouseDown}
        onClick={(e) => { e.stopPropagation(); onSelectMarker(true); }}
      >
        <div
          className={`w-0.5 h-full mx-auto transition-opacity ${
            isActive ? "bg-amber-400 opacity-100" : "bg-amber-400/60 group-hover:opacity-100"
          }`}
        />
        {/* Lightning bolt icon */}
        <div
          className={`absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 text-[10px] ${
            isActive ? "text-amber-400" : "text-amber-400/70"
          }`}
        >
          ⚡
        </div>
      </div>
    </div>
  );
}
