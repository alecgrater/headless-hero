import { useEffect, useRef, useState } from "react";

interface Props {
  estimatedSeconds: number | null;
  active: boolean;
}

export default function MiniProgressBar({ estimatedSeconds, active }: Props) {
  const [progress, setProgress] = useState(0);
  const [visible, setVisible] = useState(false);
  const startTime = useRef<number | null>(null);
  const rafId = useRef<number>(0);

  useEffect(() => {
    if (active) {
      setProgress(0);
      setVisible(true);
      startTime.current = Date.now();

      if (estimatedSeconds && estimatedSeconds > 0) {
        const tick = () => {
          if (!startTime.current) return;
          const elapsed = (Date.now() - startTime.current) / 1000;
          const ratio = elapsed / estimatedSeconds;
          const eased = Math.min(0.95, Math.pow(ratio, 2));
          setProgress(Math.max(0, eased));
          rafId.current = requestAnimationFrame(tick);
        };
        rafId.current = requestAnimationFrame(tick);
      }

      return () => cancelAnimationFrame(rafId.current);
    } else if (visible) {
      cancelAnimationFrame(rafId.current);
      setProgress(1);
      const timeout = setTimeout(() => {
        setVisible(false);
        setProgress(0);
      }, 400);
      return () => clearTimeout(timeout);
    }
  }, [active, estimatedSeconds, visible]);

  if (!visible) return null;

  const isDeterminate = estimatedSeconds !== null && estimatedSeconds > 0;

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
