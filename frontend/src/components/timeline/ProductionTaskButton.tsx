import { useEffect, useRef, useState } from "react";
import { compactProgressText } from "./timelineProduction";

export function ProductionTaskButton({
  stepNumber,
  label,
  done,
  busy,
  missingCount,
  progress,
  disabled,
  onRunAll,
  onRunMissing,
  missingLabel,
  allTitle,
}: {
  stepNumber: number;
  label: string;
  done: boolean;
  busy: boolean;
  missingCount: number;
  progress: number | null;
  disabled: boolean;
  onRunAll: () => void;
  onRunMissing: () => void;
  missingLabel: string;
  allTitle: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const buttonStateClass = busy
    ? "bg-neutral-800/80 border-violet-500/40 text-neutral-200 shadow-[0_0_8px_rgba(139,92,246,0.15)]"
    : done
      ? "bg-emerald-500/8 border-emerald-500/25 text-emerald-400 hover:bg-emerald-500/15"
      : "bg-neutral-800/80 border-neutral-700/60 text-neutral-300 hover:bg-neutral-700/80 hover:border-neutral-600";
  const stepClass = busy
    ? "border-violet-400 bg-violet-500/10 text-violet-300 shadow-[0_0_6px_rgba(139,92,246,0.4)] animate-[pulseDot_2s_ease-in-out_infinite]"
    : done
      ? "border-emerald-400 bg-emerald-500/10 text-emerald-300 shadow-[0_0_6px_rgba(52,211,153,0.3)]"
      : "border-neutral-600 text-neutral-500";

  return (
    <div ref={ref} className="relative flex items-center gap-1.5 min-w-0">
      <span className={`w-[20px] h-[20px] rounded-full border text-[11px] font-bold flex items-center justify-center shrink-0 tabular-nums ${stepClass}`}>
        {stepNumber}
      </span>
      <div className="flex items-stretch flex-1 min-w-0">
        <button
          type="button"
          onClick={onRunAll}
          disabled={busy || disabled}
          className={`text-xs pl-3 pr-2 py-2 border border-r-0 rounded-l-lg font-medium transition-all flex items-center justify-center gap-1.5 flex-1 whitespace-nowrap disabled:opacity-50 ${buttonStateClass}`}
          title={allTitle}
        >
          {busy ? (
            <>
              <span className="w-3.5 h-3.5 border-2 border-violet-400/60 border-t-transparent rounded-full animate-spin" />
              {compactProgressText(progress) || "Running"}
            </>
          ) : done ? (
            `${label} ✓`
          ) : (
            label
          )}
        </button>
        <button
          type="button"
          onClick={() => setOpen((show) => !show)}
          disabled={busy || disabled}
          className="text-xs px-1.5 bg-neutral-800/80 border border-l-0 border-neutral-700/60 text-neutral-400 hover:bg-neutral-700/80 hover:text-neutral-200 rounded-r-lg transition-all flex items-center disabled:opacity-50"
          title={`${label} options`}
        >
          <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none">
            <path d="M3 5L6 8L9 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </div>
      {open && (
        <div className="absolute top-full left-7 mt-1.5 w-56 bg-neutral-800/90 border border-neutral-700/60 rounded-xl shadow-2xl z-50 py-1.5">
          <button
            onClick={() => {
              setOpen(false);
              onRunMissing();
            }}
            disabled={missingCount === 0}
            className="w-full text-left px-3 py-1.5 text-sm text-neutral-300 hover:bg-neutral-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {missingLabel} ({missingCount})
          </button>
        </div>
      )}
    </div>
  );
}
