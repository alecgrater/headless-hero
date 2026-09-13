import { useEffect, useRef, useState } from "react";

interface Props {
  estimatedSeconds: number | null;
  active: boolean;
}

/** One tick a second — see GenerationProgressBar for why not rAF. */
const TICK_MS = 1000;

export default function MiniProgressBar({ estimatedSeconds, active }: Props) {
  const [elapsed, setElapsed] = useState(0);
  const [visible, setVisible] = useState(false);
  const [done, setDone] = useState(false);
  const startTime = useRef<number | null>(null);

  useEffect(() => {
    if (active) {
      setElapsed(0);
      setDone(false);
      setVisible(true);
      startTime.current = Date.now();
      // Nothing reads `elapsed` without an estimate, so an indeterminate run
      // should not re-render once a second for its whole duration.
      if (!estimatedSeconds || estimatedSeconds <= 0) return;
      const id = setInterval(() => {
        if (startTime.current) setElapsed((Date.now() - startTime.current) / 1000);
      }, TICK_MS);
      return () => clearInterval(id);
    }
    if (visible) {
      setDone(true);
      const timeout = setTimeout(() => {
        setVisible(false);
        setDone(false);
        setElapsed(0);
      }, 600);
      return () => clearTimeout(timeout);
    }
  }, [active, visible, estimatedSeconds]);

  if (!visible) return null;

  const isDeterminate = estimatedSeconds !== null && estimatedSeconds > 0;
  // Linear, matching GenerationProgressBar: an ease-in reads as stalled on the
  // hour-plus runs Local Mode produces.
  const progress = done ? 1 : isDeterminate ? Math.min(0.95, elapsed / estimatedSeconds) : 0;

  return (
    <div className="w-full h-1 rounded-full bg-neutral-800 overflow-hidden mt-1">
      {isDeterminate ? (
        <div
          className="h-full rounded-full bg-violet-500 transition-all duration-300 ease-out"
          style={{ width: `${progress * 100}%` }}
        />
      ) : (
        <div className="h-full rounded-full bg-violet-500 animate-pulse w-full opacity-50" />
      )}
    </div>
  );
}
