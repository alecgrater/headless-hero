import { useEffect, useRef, useState } from "react";

interface Props {
  estimatedSeconds: number | null;
  active: boolean;
}

export default function GenerationProgressBar({ estimatedSeconds, active }: Props) {
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
          // Ease-out: slows down as it approaches 95%
          const eased = Math.min(0.95, 1 - Math.pow(1 - ratio, 2));
          setProgress(Math.max(0, eased));
          rafId.current = requestAnimationFrame(tick);
        };
        rafId.current = requestAnimationFrame(tick);
      }

      return () => cancelAnimationFrame(rafId.current);
    } else if (visible) {
      // Generation finished — jump to 100% then hide
      cancelAnimationFrame(rafId.current);
      setProgress(1);
      const timeout = setTimeout(() => {
        setVisible(false);
        setProgress(0);
      }, 600);
      return () => clearTimeout(timeout);
    }
  }, [active, estimatedSeconds, visible]);

  if (!visible) return null;

  const remaining = estimatedSeconds && startTime.current
    ? Math.max(0, Math.round(estimatedSeconds - (Date.now() - startTime.current) / 1000))
    : null;

  const remainingText = remaining !== null && remaining > 0 && active
    ? remaining >= 60
      ? `~${Math.ceil(remaining / 60)}m remaining`
      : `~${remaining}s remaining`
    : null;

  const isDeterminate = estimatedSeconds !== null && estimatedSeconds > 0;

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
      {remainingText && (
        <p className="text-xs text-neutral-500 text-center">{remainingText}</p>
      )}
    </div>
  );
}
