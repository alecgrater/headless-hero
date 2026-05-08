import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { assetUrl } from "../../api";
import type { Scene } from "../../types/script";

interface WordTimestamp {
  word: string;
  start_ms: number;
  end_ms: number;
}

interface EnergyZone {
  start: number;
  end: number;
  level: "calm" | "building" | "peak" | "reflective";
}

export interface DeliveryAnnotations {
  emphasis_words: number[];
  question_ranges: number[][];
  energy_zones: EnergyZone[];
}

interface Props {
  scene: Scene | null;
  isRecording: boolean;
  elapsedMs: number;
  audioLevel: number;
  countdown: number | null;
  timingOffsetMs: number;
  previewTimestamps?: WordTimestamp[] | null;
  annotations?: DeliveryAnnotations | null;
  freeMode?: boolean;
  rehearseMode?: boolean;
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

const ENERGY_COLORS: Record<string, string> = {
  calm: "rgba(96, 165, 250, 0.08)",
  building: "rgba(251, 191, 36, 0.08)",
  peak: "rgba(167, 139, 250, 0.08)",
  reflective: "rgba(52, 211, 153, 0.08)",
};

export default function TeleprompterPanel({ scene, isRecording, elapsedMs, audioLevel, countdown, timingOffsetMs, previewTimestamps, annotations, freeMode, rehearseMode }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const textRef = useRef<HTMLParagraphElement>(null);
  const wordRefs = useRef<(HTMLSpanElement | null)[]>([]);
  const [needle, setNeedle] = useState<NeedlePos | null>(null);
  const [lineYs, setLineYs] = useState<number[]>([]);
  const [fontSize, setFontSize] = useState(18);

  const words = useMemo(() => {
    if (!scene?.narration) return [];
    return scene.narration.split(/\s+/).filter(Boolean);
  }, [scene?.narration]);

  // Detect breath/pause points from punctuation in the original narration
  const breathMarkers = useMemo(() => {
    if (!scene?.narration) return new Map<number, "light" | "medium" | "heavy">();
    const markers = new Map<number, "light" | "medium" | "heavy">();
    const rawWords = scene.narration.split(/\s+/).filter(Boolean);

    for (let i = 0; i < rawWords.length - 1; i++) {
      const w = rawWords[i];
      const lastChar = w[w.length - 1];
      if (lastChar === "." || lastChar === "!" || lastChar === "?") {
        markers.set(i, "medium");
      } else if (lastChar === "," || lastChar === ";") {
        markers.set(i, "light");
      }
    }

    // Detect paragraph breaks from original narration
    const parts = scene.narration.split(/\n\n+/);
    if (parts.length > 1) {
      let wordIdx = 0;
      for (let p = 0; p < parts.length - 1; p++) {
        const partWords = parts[p].split(/\s+/).filter(Boolean);
        wordIdx += partWords.length;
        if (wordIdx > 0) markers.set(wordIdx - 1, "heavy");
      }
    }

    return markers;
  }, [scene?.narration]);

  const wordTimings = useMemo(() => {
    if (!words.length) return [];

    // Use previewTimestamps if available (from align-take), otherwise scene.word_timestamps
    const timestamps = previewTimestamps || scene?.word_timestamps;

    if (timestamps?.length) {
      return timestamps.map((wt) => ({
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
  }, [words, scene?.word_timestamps, previewTimestamps, timingOffsetMs]);

  const trackingActive = !freeMode;

  // WPM calculation during recording (disabled in free mode)
  const currentWpm = useMemo(() => {
    if (!trackingActive || !isRecording || !wordTimings.length || elapsedMs < 2000) return null;
    let wordsSpoken = 0;
    for (const wt of wordTimings) {
      if (elapsedMs >= wt.endMs) wordsSpoken++;
      else break;
    }
    if (wordsSpoken < 1) return null;
    return Math.round((wordsSpoken / elapsedMs) * 60000);
  }, [trackingActive, isRecording, elapsedMs, wordTimings]);

  const wpmColor = useMemo(() => {
    if (currentWpm === null) return "";
    if (currentWpm < 100) return "text-sky-400";
    if (currentWpm < 130) return "text-neutral-400";
    if (currentWpm <= 160) return "text-emerald-400";
    if (currentWpm <= 180) return "text-amber-400";
    return "text-red-400";
  }, [currentWpm]);

  const setWordRef = useCallback((el: HTMLSpanElement | null, index: number) => {
    wordRefs.current[index] = el;
  }, []);

  // Reset font size when scene changes
  useEffect(() => {
    setFontSize(18);
  }, [scene?.id]);

  // Shrink font size until text fits, then detect visual lines
  useLayoutEffect(() => {
    if (!containerRef.current || !textRef.current || wordRefs.current.length === 0) {
      setLineYs([]);
      return;
    }
    const container = containerRef.current;
    if (textRef.current.scrollHeight > container.clientHeight && fontSize > 14) {
      setFontSize((prev) => prev - 1);
      return;
    }
    const containerRect = container.getBoundingClientRect();
    const scrollTop = container.scrollTop;
    const seen = new Set<number>();
    const ys: number[] = [];
    for (const el of wordRefs.current) {
      if (!el) continue;
      const rect = el.getBoundingClientRect();
      const y = Math.round(rect.bottom - containerRect.top + scrollTop + 4);
      const rounded = Math.round(y / 5) * 5;
      if (!seen.has(rounded)) {
        seen.add(rounded);
        ys.push(y);
      }
    }
    setLineYs(ys);
  }, [words, scene?.id, fontSize]);

  // Reset needle to far-left resting position when not recording/counting down
  useEffect(() => {
    if (freeMode) {
      setNeedle(null);
      return;
    }
    if (wordTimings.length === 0) {
      setNeedle(null);
      return;
    }
    if (isRecording || countdown !== null) return;
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
  }, [scene?.id, wordTimings.length, isRecording, countdown, freeMode]);

  // Animate needle from left toward first word during 3-2-1 countdown
  const countdownStartRef = useRef<number | null>(null);
  useEffect(() => {
    if (freeMode || countdown === null || !containerRef.current || wordTimings.length === 0) {
      countdownStartRef.current = null;
      return;
    }
    if (countdownStartRef.current === null) {
      countdownStartRef.current = performance.now();
    }
    const startTime = countdownStartRef.current;
    const totalMs = 3000;
    let rafId: number;

    const animate = () => {
      const elapsed = performance.now() - startTime;
      const progress = Math.min(1, elapsed / totalMs);
      const firstEl = wordRefs.current[0];
      if (firstEl && containerRef.current) {
        const containerRect = containerRef.current.getBoundingClientRect();
        const rect = firstEl.getBoundingClientRect();
        const y = rect.bottom - containerRect.top + containerRef.current.scrollTop + 4;
        const targetX = rect.left + rect.width / 2 - containerRect.left;
        setNeedle({ x: progress * targetX, y });
      }
      if (progress < 1) {
        rafId = requestAnimationFrame(animate);
      }
    };
    rafId = requestAnimationFrame(animate);
    return () => cancelAnimationFrame(rafId);
  }, [countdown, wordTimings.length]);

  // Update needle position based on elapsed time during recording
  useEffect(() => {
    if (freeMode || !isRecording || !containerRef.current || wordTimings.length === 0) return;

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

  // Determine energy zone background for a word index
  const getEnergyBg = useCallback((idx: number): string | undefined => {
    if (!annotations?.energy_zones) return undefined;
    for (const zone of annotations.energy_zones) {
      if (idx >= zone.start && idx <= zone.end) {
        return ENERGY_COLORS[zone.level];
      }
    }
    return undefined;
  }, [annotations]);

  const isEmphasis = useCallback((idx: number): boolean => {
    return annotations?.emphasis_words?.includes(idx) ?? false;
  }, [annotations]);

  const isQuestionEnd = useCallback((idx: number): boolean => {
    if (!annotations?.question_ranges) return false;
    return annotations.question_ranges.some(([, end]) => end === idx);
  }, [annotations]);

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
        {/* WPM counter pill */}
        {isRecording && currentWpm !== null && (
          <div className="absolute top-3 right-3 bg-black/60 px-2.5 py-1 rounded-full">
            <span className={`text-xs font-mono tabular-nums ${wpmColor}`}>{currentWpm} wpm</span>
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

      {/* Recording state indicator */}
      {isRecording && countdown === null ? (
        <div className="shrink-0 mx-4 mt-2 flex items-center justify-center gap-2 py-1.5 bg-red-500/10 border border-red-500/25 rounded-lg">
          <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse" />
          <span className="text-xs font-medium text-red-400 font-mono tabular-nums">{formatTime(elapsedMs)}</span>
          <span className="text-xs text-red-400/60 ml-1">Recording — Space to stop</span>
        </div>
      ) : countdown !== null ? null : (
        <div className="shrink-0 mx-4 mt-2 flex items-center justify-center py-1.5 bg-neutral-800/50 border border-neutral-700/50 rounded-lg">
          <span className="text-xs text-neutral-500">
            {rehearseMode ? "Press Space to rehearse" : freeMode ? "Press Space to record (no countdown)" : "Press Space to record"}
          </span>
        </div>
      )}

      {/* Teleprompter text with needle */}
      <div ref={containerRef} className="relative flex-1 overflow-hidden px-8 py-6">
        {words.length === 0 ? (
          <div className="text-center text-neutral-600 text-sm py-12">Select a scene to begin</div>
        ) : (
          <p ref={textRef} className="leading-[2.2] font-medium text-center" style={{ fontSize: `${fontSize}px` }}>
            {wordTimings.map((wt, i) => {
              const isActive = trackingActive && isRecording && elapsedMs >= wt.startMs && elapsedMs < wt.endMs;
              const isPast = trackingActive && isRecording && elapsedMs >= wt.endMs;
              const isUpcoming = trackingActive && isRecording && elapsedMs >= wt.startMs - 500 && elapsedMs < wt.startMs;
              const energyBg = getEnergyBg(i);
              const emphasized = isEmphasis(i);
              const qEnd = isQuestionEnd(i);
              const breathAfter = breathMarkers.get(i);

              return (
                <span key={i} className="inline">
                  <span
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
                    } ${emphasized && !isRecording ? "underline decoration-violet-400/50 decoration-1 underline-offset-4 font-semibold" : ""}`}
                    style={energyBg && !isRecording ? { backgroundColor: energyBg, borderRadius: "2px", padding: "0 1px" } : undefined}
                  >
                    {wt.word}{qEnd && <span className="text-[10px] text-violet-400 ml-0.5">↑</span>}
                  </span>
                  {/* Breath marker */}
                  {breathAfter && (
                    <span
                      className={`inline-block align-middle mx-[0.1em] rounded-full ${
                        breathAfter === "heavy"
                          ? "w-[3px] h-3 bg-violet-400/60"
                          : breathAfter === "medium"
                            ? "w-[2px] h-2.5 bg-neutral-500/60"
                            : "w-[1px] h-2 bg-neutral-600/50"
                      }`}
                    />
                  )}
                </span>
              );
            })}
          </p>
        )}

        {/* Static underlines beneath each visual row of text */}
        {lineYs.map((y, i) => (
          <div
            key={i}
            className="absolute left-8 right-8 h-[2px] bg-neutral-700/60 pointer-events-none"
            style={{ top: `${y}px` }}
          />
        ))}

        {/* Timing needle arrow on active line */}
        {needle && (
          <div
            className="absolute pointer-events-none transition-[left,top] duration-75"
            style={{ left: `${needle.x + 16}px`, top: `${needle.y - 16}px` }}
          >
            <svg width="10" height="18" viewBox="0 0 10 18">
              <path d="M5 0 L9 10 L6 10 L6 18 L4 18 L4 10 L1 10 Z" fill="#a78bfa" />
            </svg>
          </div>
        )}
      </div>
    </div>
  );
}
