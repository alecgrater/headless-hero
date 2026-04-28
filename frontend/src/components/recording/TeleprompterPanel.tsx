import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { assetUrl } from "../../api";
import type { Scene } from "../../types/script";

interface Props {
  scene: Scene | null;
  isRecording: boolean;
  elapsedMs: number;
  audioLevel: number;
  countdown: number | null;
  timingOffsetMs: number;
}

function formatTime(ms: number): string {
  const secs = Math.floor(ms / 1000);
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function TeleprompterPanel({ scene, isRecording, elapsedMs, audioLevel, countdown, timingOffsetMs }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wordRefs = useRef<(HTMLSpanElement | null)[]>([]);
  const [needleX, setNeedleX] = useState<number | null>(null);

  const words = useMemo(() => {
    if (!scene?.narration) return [];
    return scene.narration.split(/\s+/).filter(Boolean);
  }, [scene?.narration]);

  const wordTimings = useMemo(() => {
    if (!words.length) return [];
    if (scene?.word_timestamps?.length) {
      return scene.word_timestamps.map((wt) => ({
        word: wt.word,
        startMs: wt.start_ms + timingOffsetMs,
        endMs: wt.end_ms + timingOffsetMs,
      }));
    }
    const wpm = 140;
    const msPerWord = 60000 / wpm;
    return words.map((w, i) => ({
      word: w,
      startMs: Math.round(i * msPerWord) + timingOffsetMs,
      endMs: Math.round((i + 1) * msPerWord) + timingOffsetMs,
    }));
  }, [words, scene?.word_timestamps, timingOffsetMs]);

  // Reset word refs when words change
  useEffect(() => {
    wordRefs.current = new Array(wordTimings.length).fill(null);
  }, [wordTimings.length]);

  const setWordRef = useCallback((el: HTMLSpanElement | null, index: number) => {
    wordRefs.current[index] = el;
  }, []);

  // Update needle position based on elapsed time
  useEffect(() => {
    if (!isRecording || !containerRef.current || wordTimings.length === 0) {
      setNeedleX(null);
      return;
    }

    if (elapsedMs === 0) {
      setNeedleX(16);
      return;
    }

    const containerRect = containerRef.current.getBoundingClientRect();

    // Find active word index and interpolate position
    let activeIdx = -1;
    let progress = 0;
    for (let i = 0; i < wordTimings.length; i++) {
      const wt = wordTimings[i];
      if (elapsedMs >= wt.startMs && elapsedMs < wt.endMs) {
        activeIdx = i;
        progress = (elapsedMs - wt.startMs) / (wt.endMs - wt.startMs);
        break;
      }
    }

    // Before first word — start at left edge of container
    if (activeIdx === -1 && elapsedMs < wordTimings[0].startMs) {
      setNeedleX(16);
      return;
    }

    // After last word
    if (activeIdx === -1) {
      const lastEl = wordRefs.current[wordTimings.length - 1];
      if (lastEl) {
        const rect = lastEl.getBoundingClientRect();
        setNeedleX(rect.left + rect.width - containerRect.left);
      }
      return;
    }

    const currentEl = wordRefs.current[activeIdx];
    if (!currentEl) return;

    const currentRect = currentEl.getBoundingClientRect();
    const nextEl = wordRefs.current[activeIdx + 1];

    let x: number;
    if (nextEl) {
      const nextRect = nextEl.getBoundingClientRect();
      // If same line, interpolate smoothly between current center and next center
      if (Math.abs(nextRect.top - currentRect.top) < 10) {
        const startX = currentRect.left + currentRect.width / 2;
        const endX = nextRect.left + nextRect.width / 2;
        x = startX + (endX - startX) * progress;
      } else {
        // Wrapping to next line — stay at current word center
        x = currentRect.left + currentRect.width * progress;
      }
    } else {
      x = currentRect.left + currentRect.width * progress;
    }

    setNeedleX(x - containerRect.left);
  }, [isRecording, elapsedMs, wordTimings]);

  // Auto-scroll to keep active word visible
  useEffect(() => {
    if (!isRecording || !containerRef.current) return;
    const activeWord = containerRef.current.querySelector("[data-active='true']");
    if (activeWord) {
      activeWord.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }, [isRecording, elapsedMs]);

  const imageUrl = scene?.image_url ? assetUrl(scene.image_url) : null;

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Video preview area */}
      <div className="relative aspect-video bg-neutral-900 rounded-lg overflow-hidden border border-neutral-800 mx-4 mt-4 shrink-0">
        {imageUrl ? (
          <img src={imageUrl} alt="" className="w-full h-full object-cover" />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-neutral-600 text-sm">
            No image generated
          </div>
        )}
        {/* Countdown overlay */}
        {countdown !== null && (
          <div className="absolute inset-0 bg-black/70 flex items-center justify-center">
            <span className="text-7xl font-bold text-white animate-pulse">{countdown}</span>
          </div>
        )}
        {/* Recording indicator */}
        {isRecording && countdown === null && (
          <div className="absolute top-3 left-3 flex items-center gap-2 bg-black/60 px-3 py-1.5 rounded-full">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse" />
            <span className="text-xs text-white font-mono tabular-nums">{formatTime(elapsedMs)}</span>
          </div>
        )}
        {/* Audio level bar */}
        {isRecording && (
          <div className="absolute bottom-0 left-0 right-0 h-1 bg-neutral-900/80">
            <div
              className="h-full bg-emerald-400 transition-all duration-75"
              style={{ width: `${Math.min(100, audioLevel * 100)}%` }}
            />
          </div>
        )}
      </div>

      {/* Teleprompter text with needle */}
      <div ref={containerRef} className="relative flex-1 overflow-y-auto px-8 py-6">
        {words.length === 0 ? (
          <div className="text-center text-neutral-600 text-sm py-12">Select a scene to begin</div>
        ) : (
          <p className="text-2xl leading-relaxed font-medium text-center pb-10">
            {wordTimings.map((wt, i) => {
              const isActive = isRecording && elapsedMs >= wt.startMs && elapsedMs < wt.endMs;
              const isPast = isRecording && elapsedMs >= wt.endMs;
              const isUpcoming = isRecording && elapsedMs >= wt.startMs - 500 && elapsedMs < wt.startMs;
              return (
                <span
                  key={i}
                  ref={(el) => setWordRef(el, i)}
                  data-active={isActive}
                  className={`inline-block mr-[0.3em] transition-all duration-150 ${
                    isActive
                      ? "text-white scale-105 transform"
                      : isPast
                        ? "text-neutral-400"
                        : isUpcoming
                          ? "text-neutral-300"
                          : isRecording
                            ? "text-neutral-600 blur-[0.5px]"
                            : "text-neutral-300"
                  }`}
                >
                  {wt.word}
                </span>
              );
            })}
          </p>
        )}

        {/* Timing needle — horizontal line with spike */}
        {isRecording && needleX !== null && (
          <div className="sticky bottom-0 left-0 right-0 h-8 pointer-events-none">
            {/* Horizontal line */}
            <div className="absolute bottom-3 left-4 right-4 h-[1px] bg-neutral-700" />
            {/* Spike / needle */}
            <div
              className="absolute bottom-1 transition-[left] duration-75"
              style={{ left: `${needleX}px` }}
            >
              {/* Triangle spike pointing up */}
              <svg width="12" height="20" viewBox="0 0 12 20" className="relative -left-[6px]">
                <path d="M6 0 L12 14 L8 14 L8 20 L4 20 L4 14 L0 14 Z" fill="#a78bfa" />
              </svg>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
