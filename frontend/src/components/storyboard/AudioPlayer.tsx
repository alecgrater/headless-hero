import { useCallback, useEffect, useRef, useState } from "react";

interface Props {
  src: string;
  duration?: number;
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

export default function AudioPlayer({ src, duration: propDuration }: Props) {
  const audioRef = useRef<HTMLAudioElement>(null);
  const progressRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number>(0);

  const [playing, setPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(propDuration ?? 0);

  // Reset state when src changes
  useEffect(() => {
    setPlaying(false);
    setCurrentTime(0);
    if (propDuration) setDuration(propDuration);
  }, [src, propDuration]);

  const updateProgress = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    setCurrentTime(audio.currentTime);
    if (!audio.paused) {
      rafRef.current = requestAnimationFrame(updateProgress);
    }
  }, []);

  const togglePlay = useCallback(() => {
    const audio = audioRef.current;
    if (!audio) return;
    if (audio.paused) {
      audio.play();
      setPlaying(true);
      rafRef.current = requestAnimationFrame(updateProgress);
    } else {
      audio.pause();
      setPlaying(false);
      cancelAnimationFrame(rafRef.current);
    }
  }, [updateProgress]);

  const handleSeek = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const audio = audioRef.current;
    const bar = progressRef.current;
    if (!audio || !bar) return;
    const rect = bar.getBoundingClientRect();
    const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    audio.currentTime = pct * (audio.duration || duration);
    setCurrentTime(audio.currentTime);
  }, [duration]);

  useEffect(() => {
    return () => cancelAnimationFrame(rafRef.current);
  }, []);

  const handleLoadedMetadata = useCallback(() => {
    const audio = audioRef.current;
    if (audio && audio.duration && isFinite(audio.duration)) {
      setDuration(audio.duration);
    }
  }, []);

  const handleEnded = useCallback(() => {
    setPlaying(false);
    setCurrentTime(0);
    cancelAnimationFrame(rafRef.current);
  }, []);

  const pct = duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div className="flex items-center gap-2.5 bg-neutral-800 rounded-lg px-3 py-2">
      <audio
        ref={audioRef}
        src={src}
        preload="metadata"
        onLoadedMetadata={handleLoadedMetadata}
        onEnded={handleEnded}
      />

      {/* Play/Pause */}
      <button
        onClick={togglePlay}
        className="w-7 h-7 flex items-center justify-center rounded-full bg-violet-500 hover:bg-violet-400 transition-colors shrink-0"
      >
        {playing ? (
          <svg width="10" height="12" viewBox="0 0 10 12" fill="white">
            <rect x="0" y="0" width="3" height="12" rx="1" />
            <rect x="7" y="0" width="3" height="12" rx="1" />
          </svg>
        ) : (
          <svg width="10" height="12" viewBox="0 0 10 12" fill="white">
            <polygon points="0,0 10,6 0,12" />
          </svg>
        )}
      </button>

      {/* Progress bar */}
      <div
        ref={progressRef}
        onClick={handleSeek}
        className="flex-1 h-1.5 bg-neutral-700 rounded-full cursor-pointer group relative"
      >
        <div
          className="h-full bg-violet-500 rounded-full transition-[width] duration-75"
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Timestamp */}
      <span className="text-[11px] text-neutral-400 tabular-nums shrink-0">
        {formatTime(currentTime)} / {formatTime(duration)}
      </span>
    </div>
  );
}
