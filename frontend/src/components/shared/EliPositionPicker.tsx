import { useCallback, useRef, useState } from "react";
import type { EliPosition } from "../../types/brand";

interface Props {
  value: EliPosition;
  onChange: (pos: EliPosition) => void;
}

const VIDEO_W = 1920;
const VIDEO_H = 1080;
const OVERLAY_W = 480;
const OVERLAY_H = 270;

// Preview dimensions
const PREVIEW_W = 320;
const PREVIEW_H = 180;

const SCALE = PREVIEW_W / VIDEO_W;
const THUMB_W = OVERLAY_W * SCALE;
const THUMB_H = OVERLAY_H * SCALE;

const PRESETS: { label: string; x: number; y: number }[] = [
  { label: "TL", x: 30, y: 30 },
  { label: "TR", x: VIDEO_W - OVERLAY_W - 30, y: 30 },
  { label: "BL", x: 30, y: VIDEO_H - OVERLAY_H - 90 },
  { label: "BR", x: VIDEO_W - OVERLAY_W - 30, y: VIDEO_H - OVERLAY_H - 90 },
];

function clamp(val: number, min: number, max: number) {
  return Math.max(min, Math.min(max, val));
}

export default function EliPositionPicker({ value, onChange }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState(false);

  const toVideoCoords = useCallback((clientX: number, clientY: number): EliPosition => {
    const rect = containerRef.current!.getBoundingClientRect();
    const px = clientX - rect.left - THUMB_W / 2;
    const py = clientY - rect.top - THUMB_H / 2;
    return {
      x: clamp(Math.round(px / SCALE), 0, VIDEO_W - OVERLAY_W),
      y: clamp(Math.round(py / SCALE), 0, VIDEO_H - OVERLAY_H),
    };
  }, []);

  const handlePointerDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    setDragging(true);
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    onChange(toVideoCoords(e.clientX, e.clientY));
  }, [onChange, toVideoCoords]);

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (!dragging) return;
    onChange(toVideoCoords(e.clientX, e.clientY));
  }, [dragging, onChange, toVideoCoords]);

  const handlePointerUp = useCallback(() => {
    setDragging(false);
  }, []);

  const thumbLeft = value.x * SCALE;
  const thumbTop = value.y * SCALE;

  return (
    <div className="space-y-2">
      {/* Preview frame */}
      <div
        ref={containerRef}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        className="relative bg-neutral-800 rounded-lg border border-neutral-700 cursor-crosshair select-none touch-none"
        style={{ width: PREVIEW_W, height: PREVIEW_H }}
      >
        {/* Overlay rectangle */}
        <div
          className="absolute rounded border-2 border-teal-400/70 bg-teal-400/15 transition-[left,top] pointer-events-none"
          style={{
            width: THUMB_W,
            height: THUMB_H,
            left: thumbLeft,
            top: thumbTop,
            transitionDuration: dragging ? "0ms" : "150ms",
          }}
        >
          <span className="absolute inset-0 flex items-center justify-center text-[9px] text-teal-300/70 font-medium">
            Eli
          </span>
        </div>
      </div>

      {/* Preset buttons */}
      <div className="flex gap-1.5">
        {PRESETS.map((p) => (
          <button
            key={p.label}
            onClick={() => onChange({ x: p.x, y: p.y })}
            className={`text-[10px] px-2 py-1 rounded border transition-colors ${
              value.x === p.x && value.y === p.y
                ? "border-teal-500/50 bg-teal-500/15 text-teal-300"
                : "border-neutral-700 bg-neutral-800 text-neutral-400 hover:bg-neutral-700 hover:text-neutral-300"
            }`}
          >
            {p.label}
          </button>
        ))}
        <span className="text-[10px] text-neutral-500 ml-auto self-center">
          {value.x}, {value.y}
        </span>
      </div>
    </div>
  );
}
