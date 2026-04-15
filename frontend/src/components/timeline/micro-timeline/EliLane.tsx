import { useCallback, useEffect, useRef, useState } from "react";
import type { EliKeyframe, WordTimestamp } from "../../../types/script";
import {
  type LaneProps,
  secondsToPx,
  pxToSeconds,
  clamp,
  snapToWordBoundary,
  FPS,
} from "./shared";

interface Props extends LaneProps {
  keyframes: EliKeyframe[];
  wordTimestamps?: WordTimestamp[] | null;
  onChange: (keyframes: EliKeyframe[]) => void;
  selectedMarker: number | null;
  onSelectMarker: (index: number | null) => void;
  shiftHeld: boolean;
}

const MARKER_WIDTH = 10;

export default function EliLane({
  durationSeconds,
  widthPx,
  isSelected,
  onSelect,
  keyframes,
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

  // Drag the boundary between keyframe[idx-1] and keyframe[idx]
  const handleBoundaryMouseDown = useCallback(
    (idx: number) => (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (idx === 0) return; // First keyframe start is always frame 0
      setDraggingIdx(idx);
      onSelectMarker(idx);

      const onMouseMove = (me: MouseEvent) => {
        if (!laneRef.current) return;
        const rect = laneRef.current.getBoundingClientRect();
        const px = me.clientX - rect.left;
        let sec = pxToSeconds(px, durationSeconds, widthPx);

        if (!shiftHeldRef.current) {
          sec = snapToWordBoundary(sec, wordTimestamps);
        }

        const newFrame = Math.round(sec * FPS);
        // Clamp: must be after prev keyframe start + 1 frame, before next keyframe end - 1 frame
        const minFrame = (keyframes[idx - 1]?.start_frame ?? 0) + 1;
        const maxFrame = (keyframes[idx]?.end_frame ?? Math.round(durationSeconds * FPS)) - 1;
        const clampedFrame = clamp(newFrame, minFrame, maxFrame);

        const updated = keyframes.map((kf, i) => {
          if (i === idx - 1) return { ...kf, end_frame: clampedFrame };
          if (i === idx) return { ...kf, start_frame: clampedFrame };
          return kf;
        });
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
    [durationSeconds, widthPx, keyframes, wordTimestamps, onChange, onSelectMarker],
  );

  return (
    <div
      ref={laneRef}
      className={`relative h-6 cursor-pointer rounded-sm ${
        isSelected ? "bg-neutral-800" : "bg-neutral-900 hover:bg-neutral-850"
      }`}
      onClick={onSelect}
      title="Eli"
    >
      {/* Label */}
      <span className="absolute left-1 top-0.5 text-[9px] text-neutral-600 select-none z-10">
        Eli
      </span>

      {/* Keyframe region backgrounds */}
      {keyframes.map((kf, i) => {
        const startPx = secondsToPx(kf.start_frame / FPS, durationSeconds, widthPx);
        const endPx = secondsToPx(kf.end_frame / FPS, durationSeconds, widthPx);
        const colors = ["bg-emerald-500/15", "bg-teal-500/15", "bg-cyan-500/15", "bg-lime-500/15"];
        // Truncate frame_id for label
        const label = kf.frame_id.replace(/_/g, " ").split(" ").slice(0, 2).join(" ");
        return (
          <div key={i} className="absolute top-1 bottom-1" style={{ left: startPx, width: Math.max(0, endPx - startPx) }}>
            <div className={`w-full h-full ${colors[i % colors.length]} rounded-sm`} />
            <span className="absolute inset-0 flex items-center justify-center text-[8px] text-neutral-500 truncate px-1 select-none">
              {label}
            </span>
          </div>
        );
      })}

      {/* Boundary markers (skip first — always at frame 0) */}
      {keyframes.slice(1).map((kf, rawIdx) => {
        const idx = rawIdx + 1;
        const px = secondsToPx(kf.start_frame / FPS, durationSeconds, widthPx);
        const isActive = selectedMarker === idx || draggingIdx === idx;
        return (
          <div
            key={idx}
            className="absolute top-0 h-full cursor-col-resize z-20 group"
            style={{ left: px - MARKER_WIDTH / 2, width: MARKER_WIDTH }}
            onMouseDown={handleBoundaryMouseDown(idx)}
            onClick={(e) => { e.stopPropagation(); onSelectMarker(idx); }}
          >
            <div
              className={`w-0.5 h-full mx-auto transition-opacity ${
                isActive ? "bg-emerald-400 opacity-100" : "bg-emerald-400/60 group-hover:opacity-100"
              }`}
            />
          </div>
        );
      })}
    </div>
  );
}
