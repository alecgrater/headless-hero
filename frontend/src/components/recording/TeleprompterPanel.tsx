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

interface NeedlePos {
  x: number;
  y: number;
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
  const [needle, setNeedle] = useState<NeedlePos | null>(null);

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

  const setWordRef = useCallback((el: HTMLSpanElement | null, index: number) => {
    wordRefs.current[index] = el;
  }, []);

  // Reset needle to far-left resting position whenever scene changes
  useEffect(() => {
    if (wordTimings.length === 0) {
      setNeedle(null);
      return;
    }
    // Set x=0 immediately; refine Y after a frame once refs are painted
    setNeedle({ x: 0, y: 50 });
    const rafId = requestAnimationFrame(() => {
      if (!containerRef.current || !wordRefs.current[0]) return;
      const containerRect = containerRef.current.getBoundingClientRect();
      const firstEl = wordRefs.current[0];
      const rect = firstEl.getBoundingClientRect();
      const y = rect.bottom - containerRect.top + containerRef.current.scrollTop + 4;
      setNeedle({ x: 0, y });
    });
    return () => cancelAnimationFrame(rafId);
  }, [scene?.id, wordTimings.length]);

  // Update needle position based on elapsed time during recording
  useEffect(() => {
    if (!isRecording || !containerRef.current || wordTimings.length === 0) return;

    // While in countdown or at time 0, stay at resting (far left)
    if (elapsedMs === 0) {
      const firstEl = wordRefs.current[0];
      if (firstEl) {
        const containerRect = containerRef.current.getBoundingClientRect();
        const rect = firstEl.getBoundingClientRect();
        const y = rect.bottom - containerRect.top + containerRef.current.scrollTop + 4;
        setNeedle({ x: 0, y });
      }
      return;
    }

    const containerRect = containerRef.current.getBoundingClientRect();
    const containerScrollTop = containerRef.current.scrollTop;

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

    // Before first word starts — interpolate from left edge to first word
    if (activeIdx === -1 && elapsedMs < wordTimings[0].startMs) {
      const firstEl = wordRefs.current[0];
      if (firstEl) {
        const rect = firstEl.getBoundingClientRect();
        const y = rect.bottom - containerRect.top + containerScrollTop + 4;
        const targetX = rect.left + rect.width / 2 - containerRect.left;
        const leadProgress = wordTimings[0].startMs > 0 ? elapsedMs / wordTimings[0].startMs : 0;
        const x = leadProgress * targetX;
        setNeedle({ x, y });
      }
      return;
    }

    // After last word — stay at end
    if (activeIdx === -1) {
      const lastEl = wordRefs.current[wordTimings.length - 1];
      if (lastEl) {
        const rect = lastEl.getBoundingClientRect();
        const x = rect.right - containerRect.left;
        const y = rect.bottom - containerRect.top + containerScrollTop + 4;
        setNeedle({ x, y });
      }
      return;
    }

    const currentEl = wordRefs.current[activeIdx];
    if (!currentEl) return;

    const currentRect = currentEl.getBoundingClientRect();
    const y = currentRect.bottom - containerRect.top + containerScrollTop + 4;
    const nextEl = wordRefs.current[activeIdx + 1];

    let x: number;
    if (nextEl) {
      const nextRect = nextEl.getBoundingClientRect();
      // If same line, interpolate smoothly
      if (Math.abs(nextRect.top - currentRect.top) < 10) {
        const startX = currentRect.left + currentRect.width / 2 - containerRect.left;
        const endX = nextRect.left + nextRect.width / 2 - containerRect.left;
        x = startX + (endX - startX) * progress;
      } else {
        x = currentRect.left + currentRect.width * progress - containerRect.left;
      }
    } else {
      x = currentRect.left + currentRect.width * progress - containerRect.left;
    }

    setNeedle({ x, y });
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
        {countdown !== null && (
          <div className="absolute inset-0 bg-black/70 flex items-center justify-center">
            <span className="text-7xl font-bold text-white animate-pulse">{countdown}</span>
          </div>
        )}
        {isRecording && countdown === null && (
          <div className="absolute top-3 left-3 flex items-center gap-2 bg-black/60 px-3 py-1.5 rounded-full">
            <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse" />
            <span className="text-xs text-white font-mono tabular-nums">{formatTime(elapsedMs)}</span>
          </div>
        )}
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
          <p className="text-2xl leading-[2.5] font-medium text-center">
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

        {/* Timing needle — full-width line under the active text line with spike */}
        {needle && (
          <div
            className="absolute left-0 right-0 pointer-events-none transition-[top] duration-100"
            style={{ top: `${needle.y}px` }}
          >
            <div className="absolute left-4 right-4 top-0 h-[2px] bg-neutral-700/80" />
            <div
              className="absolute transition-[left] duration-75"
              style={{ left: `${needle.x + 16}px`, top: "-16px" }}
            >
              <svg width="10" height="18" viewBox="0 0 10 18">
                <path d="M5 0 L9 10 L6 10 L6 18 L4 18 L4 10 L1 10 Z" fill="#a78bfa" />
              </svg>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
