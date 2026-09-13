import { useEffect, useRef, useState } from "react";

import type { EstimateSource } from "../api";

interface Props {
  estimatedSeconds: number | null;
  active: boolean;
  /** Anything but "measured" is an approximation — see EstimateSource. */
  estimateSource?: EstimateSource;
}

/** Ticks once a second.
 *
 * Not requestAnimationFrame: a local-model generation runs for over an hour,
 * which at 60fps is a third of a million re-renders of a bar that moves a pixel
 * a minute. A second is finer than the bar can show.
 */
const TICK_MS = 1000;

export default function GenerationProgressBar({
  estimatedSeconds,
  active,
  estimateSource = "measured",
}: Props) {
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
  // Linear. A quadratic ease-in reads as stalled on a long run — half way
  // through a ninety-minute script it would show 25%.
  const progress = done ? 1 : isDeterminate ? Math.min(0.95, elapsed / estimatedSeconds) : 0;
  const remaining = isDeterminate ? Math.round(estimatedSeconds - elapsed) : null;

  const formatDuration = (seconds: number) =>
    seconds >= 60 ? `${Math.ceil(seconds / 60)}m` : `${seconds}s`;

  let caption: string | null = null;
  if (active && remaining !== null) {
    if (remaining > 0) {
      caption = `~${formatDuration(remaining)} remaining`;
      if (estimateSource !== "measured") caption += " (estimated — not measured on this machine yet)";
    } else {
      // Past the estimate the bar would otherwise sit at 95% saying nothing,
      // which on a long local run is indistinguishable from a hang.
      caption = `Taking longer than expected — still running (${formatDuration(Math.round(elapsed))} so far)`;
    }
  }

  return (
    <div className="w-full space-y-1.5">
      <div className="w-full h-1.5 rounded-full bg-neutral-800 overflow-hidden">
        {isDeterminate ? (
          <div
            className="h-full rounded-full bg-violet-500 transition-all duration-300 ease-out"
            style={{ width: `${progress * 100}%` }}
          />
        ) : (
          <div className="h-full rounded-full bg-violet-500 animate-pulse w-full opacity-50" />
        )}
      </div>
      {caption && <p className="text-xs text-neutral-500 text-center">{caption}</p>}
    </div>
  );
}
