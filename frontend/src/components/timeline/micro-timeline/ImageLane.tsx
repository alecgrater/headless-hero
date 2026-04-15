import { useCallback, useEffect, useRef, useState } from "react";
import type { WordTimestamp } from "../../../types/script";
import {
  type LaneProps,
  secondsToPx,
  pxToSeconds,
  clamp,
  snapToWordBoundary,
} from "./shared";

interface Props extends LaneProps {
  /** Seconds into scene when each frame starts. */
  frameTimings: number[];
  /** Number of frames (images) in the scene. */
  frameCount: number;
  wordTimestamps?: WordTimestamp[] | null;
  /** Called with updated full frameTimings array. */
  onChange: (timings: number[]) => void;
  /** Index of the currently selected marker, or null. */
  selectedMarker: number | null;
  onSelectMarker: (index: number | null) => void;
  /** Whether shift is held (disables word snap). */
  shiftHeld: boolean;
}

const MARKER_WIDTH = 10;

export default function ImageLane({
  durationSeconds,
  widthPx,
  isSelected,
  onSelect,
  frameTimings,
  frameCount,
  wordTimestamps,
  onChange,
  selectedMarker,
  onSelectMarker,
  shiftHeld,
}: Props) {
  const laneRef = useRef<HTMLDivElement>(null);
  const [draggingIdx, setDraggingIdx] = useState<number | null>(null);
  const shiftHeldRef = useRef(shiftHeld);
  useEffect(() => { shiftHeldRef.current = shiftHeld; }, [shiftHeld]);

  const handleMarkerMouseDown = useCallback(
    (idx: number) => (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (idx === 0) return; // First marker is always at 0
      setDraggingIdx(idx);
      onSelectMarker(idx);

      const onMouseMove = (me: MouseEvent) => {
        if (!laneRef.current) return;
        const rect = laneRef.current.getBoundingClientRect();
        const px = me.clientX - rect.left;
        let sec = pxToSeconds(px, durationSeconds, widthPx);

        // Snap to word boundary unless shift held
        if (!shiftHeldRef.current) {
          sec = snapToWordBoundary(sec, wordTimestamps);
        }

        // Clamp between previous marker + 0.1s and next marker - 0.1s
        const minSec = (frameTimings[idx - 1] ?? 0) + 0.1;
        const maxSec = (frameTimings[idx + 1] ?? durationSeconds) - 0.1;
        sec = clamp(sec, minSec, maxSec);

        const updated = [...frameTimings];
        updated[idx] = Math.round(sec * 1000) / 1000;
        onChange(updated);
      };

      const onMouseUp = () => {
        setDraggingIdx(null);
        window.removeEventListener("mousemove", onMouseMove);
        window.removeEventListener("mouseup", onMouseUp);
      };

      window.addEventListener("mousemove", onMouseMove);
      window.addEventListener("mouseup", onMouseUp);
    },
    [durationSeconds, widthPx, frameTimings, wordTimestamps, onChange, onSelectMarker],
  );

  return (
    <div
      ref={laneRef}
      className={`relative h-6 cursor-pointer rounded-sm ${
        isSelected ? "bg-neutral-800" : "bg-neutral-900 hover:bg-neutral-850"
      }`}
      onClick={onSelect}
      title="Images"
    >
      {/* Label */}
      <span className="absolute left-1 top-0.5 text-[9px] text-neutral-600 select-none z-10">
        Images
      </span>

      {/* Frame region backgrounds */}
      {frameTimings.map((timing, i) => {
        const startPx = secondsToPx(timing, durationSeconds, widthPx);
        const endSec = frameTimings[i + 1] ?? durationSeconds;
        const endPx = secondsToPx(endSec, durationSeconds, widthPx);
        const colors = ["bg-sky-500/15", "bg-emerald-500/15", "bg-amber-500/15", "bg-rose-500/15"];
        return (
          <div
            key={i}
            className={`absolute top-1 bottom-1 ${colors[i % colors.length]} rounded-sm`}
            style={{ left: startPx, width: Math.max(0, endPx - startPx) }}
          />
        );
      })}

      {/* Crossfade markers (skip first — always at 0) */}
      {frameTimings.slice(1).map((timing, rawIdx) => {
        const idx = rawIdx + 1;
        const px = secondsToPx(timing, durationSeconds, widthPx);
        const isActive = selectedMarker === idx || draggingIdx === idx;
        return (
          <div
            key={idx}
            className={`absolute top-0 h-full cursor-col-resize z-20 group`}
            style={{ left: px - MARKER_WIDTH / 2, width: MARKER_WIDTH }}
            onMouseDown={handleMarkerMouseDown(idx)}
            onClick={(e) => { e.stopPropagation(); onSelectMarker(idx); }}
          >
            <div
              className={`w-0.5 h-full mx-auto transition-opacity ${
                isActive ? "bg-sky-400 opacity-100" : "bg-sky-400/60 group-hover:opacity-100"
              }`}
            />
            {/* Diamond marker */}
            <div
              className={`absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-2 h-2 rotate-45 ${
                isActive ? "bg-sky-400" : "bg-sky-400/70"
              }`}
            />
          </div>
        );
      })}
    </div>
  );
}
