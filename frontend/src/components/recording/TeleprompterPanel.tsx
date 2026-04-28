import { useEffect, useMemo, useRef } from "react";
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

      {/* Teleprompter text */}
      <div ref={containerRef} className="flex-1 overflow-y-auto px-8 py-6">
        {words.length === 0 ? (
          <div className="text-center text-neutral-600 text-sm py-12">Select a scene to begin</div>
        ) : (
          <p className="text-2xl leading-relaxed font-medium text-center">
            {wordTimings.map((wt, i) => {
              const isActive = isRecording && elapsedMs >= wt.startMs && elapsedMs < wt.endMs;
              const isPast = isRecording && elapsedMs >= wt.endMs;
              const isUpcoming = isRecording && elapsedMs >= wt.startMs - 500 && elapsedMs < wt.startMs;
              return (
                <span
                  key={i}
                  data-active={isActive}
                  className={`inline-block mr-[0.3em] transition-all duration-200 ${
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
      </div>
    </div>
  );
}
