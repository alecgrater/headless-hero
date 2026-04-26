/**
 * WaveformSplitter — displays audio waveform with split-at-word-boundary functionality.
 * Uses wavesurfer.js to render the waveform and snap split markers to word boundaries.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import WaveSurfer from "wavesurfer.js";
import type { WordTimestamp } from "../../types/script";

interface Props {
  audioUrl: string;
  wordTimestamps?: WordTimestamp[];
  onSplit: (splitTimeMs: number) => void;
}

export default function WaveformSplitter({ audioUrl, wordTimestamps, onSplit }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wavesurferRef = useRef<unknown>(null);
  const [splitTimeMs, setSplitTimeMs] = useState<number | null>(null);
  const [ready, setReady] = useState(false);
  const audioUrlRef = useRef(audioUrl);

  useEffect(() => {
    if (!containerRef.current) return;

    let cancelled = false;

    const ws = WaveSurfer.create({
      container: containerRef.current,
      waveColor: "#525252", // neutral-600
      progressColor: "#7c3aed", // violet-600
      cursorColor: "#a78bfa", // violet-400
      cursorWidth: 2,
      height: "auto",
      barWidth: 2,
      barGap: 1,
      barRadius: 2,
      normalize: true,
      interact: true,
    });

    ws.load(audioUrl);
    audioUrlRef.current = audioUrl;

    ws.on("ready", () => {
      if (!cancelled) setReady(true);
    });

    ws.on("click", (relativeX: number) => {
      const duration = ws.getDuration();
      const clickTimeMs = Math.round(relativeX * duration * 1000);
      const snapped = snapToWordBoundary(clickTimeMs, wordTimestamps);
      setSplitTimeMs(snapped);
    });

    wavesurferRef.current = ws;

    return () => {
      cancelled = true;
      if (wavesurferRef.current) {
        (wavesurferRef.current as { destroy: () => void }).destroy();
        wavesurferRef.current = null;
      }
      setReady(false);
      setSplitTimeMs(null);
    };
  }, [audioUrl, wordTimestamps]);

  const handleSplit = useCallback(() => {
    if (splitTimeMs !== null) {
      onSplit(splitTimeMs);
      setSplitTimeMs(null);
    }
  }, [splitTimeMs, onSplit]);

  const handleCancel = useCallback(() => {
    setSplitTimeMs(null);
  }, []);

  const formatTime = (ms: number) => {
    const s = ms / 1000;
    const m = Math.floor(s / 60);
    const sec = Math.floor(s % 60);
    return `${m}:${String(sec).padStart(2, "0")}`;
  };

  return (
    <div className="flex flex-col h-full gap-2">
      <div className="flex items-center justify-between shrink-0">
        <span className="text-xs font-medium text-neutral-400">Waveform</span>
        {wordTimestamps && wordTimestamps.length > 0 && (
          <span className="text-[10px] text-neutral-600">
            {wordTimestamps.length} words &middot; click to set split point
          </span>
        )}
      </div>

      {/* Waveform container */}
      <div
        ref={containerRef}
        className="flex-1 min-h-0 rounded-lg border border-neutral-800 bg-neutral-900/60 overflow-hidden cursor-crosshair"
      />

      {!ready && (
        <div className="flex items-center gap-2 text-xs text-neutral-500">
          <span className="w-3 h-3 border-2 border-neutral-500 border-t-transparent rounded-full animate-spin" />
          Loading waveform...
        </div>
      )}

      {/* Split controls */}
      {splitTimeMs !== null && (
        <div className="flex items-center gap-3 shrink-0">
          <span className="text-xs text-neutral-400">
            Split at <span className="font-mono text-violet-400">{formatTime(splitTimeMs)}</span>
          </span>
          <div className="flex-1" />
          <button
            onClick={handleCancel}
            className="text-xs px-2.5 py-1 text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 rounded-md transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
          >
            Cancel
          </button>
          <button
            onClick={handleSplit}
            className="text-xs px-3 py-1 bg-violet-600 hover:bg-violet-500 text-white rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950"
          >
            Split Here
          </button>
        </div>
      )}
    </div>
  );
}

/**
 * Snap a timestamp to the nearest word boundary.
 * If no word timestamps available, returns the raw time.
 */
function snapToWordBoundary(
  timeMs: number,
  wordTimestamps?: WordTimestamp[],
): number {
  if (!wordTimestamps || wordTimestamps.length < 2) return timeMs;

  let bestMs = timeMs;
  let bestDist = Infinity;

  for (const wt of wordTimestamps) {
    const dist = Math.abs(wt.end_ms - timeMs);
    if (dist < bestDist) {
      bestDist = dist;
      bestMs = wt.end_ms;
    }
  }

  // Don't snap to first or last word boundary (would produce empty halves)
  const firstEnd = wordTimestamps[0].end_ms;
  const lastStart = wordTimestamps[wordTimestamps.length - 1].start_ms;
  if (bestMs <= firstEnd) bestMs = wordTimestamps[1]?.end_ms ?? firstEnd;
  if (bestMs >= lastStart) bestMs = wordTimestamps[wordTimestamps.length - 2]?.end_ms ?? lastStart;

  return bestMs;
}
