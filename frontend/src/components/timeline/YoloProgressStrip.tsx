import { useEffect, useMemo, useRef, useState } from "react";

import type { YoloRunRecord, YoloStageRecord } from "../../types/yolo";
import { clampProgress, formatElapsed, YOLO_STAGES } from "./timelineProduction";
import { runElapsedSeconds, stageElapsedSeconds } from "./yoloRun";

const STATUS_STYLES: Record<YoloStageRecord["status"], { dot: string; text: string; label: string }> = {
  pending: { dot: "bg-neutral-700", text: "text-neutral-500", label: "Waiting" },
  running: { dot: "bg-sky-400 animate-pulse", text: "text-sky-200", label: "Running" },
  done: { dot: "bg-emerald-400", text: "text-neutral-300", label: "Done" },
  skipped: { dot: "bg-neutral-600", text: "text-neutral-500", label: "Already done" },
  failed: { dot: "bg-red-400", text: "text-red-300", label: "Failed" },
  cancelled: { dot: "bg-amber-400", text: "text-amber-300", label: "Stopped" },
};

/** Re-render once a second so elapsed timers tick without a rAF loop. */
function useSecondTicker(active: boolean) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    setNow(Date.now());
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [active]);
  return now;
}

function StageRow({ stage, now }: { stage: YoloStageRecord; now: number }) {
  const style = STATUS_STYLES[stage.status];
  const elapsed = stageElapsedSeconds(stage, now);
  return (
    <li className="flex items-start gap-2.5 py-1">
      <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${style.dot}`} />
      <span className={`min-w-0 flex-1 truncate ${style.text}`}>
        {stage.label}
        {stage.attempts > 1 && (
          <span className="ml-1.5 text-[10px] text-amber-300/80">· {stage.attempts} attempts</span>
        )}
        {stage.error && stage.status === "failed" && (
          <span className="ml-1.5 text-[10px] text-red-400/90">· {stage.error}</span>
        )}
      </span>
      <span className="shrink-0 text-[10px] text-neutral-500">{style.label}</span>
      <span className="w-12 shrink-0 text-right tabular-nums text-neutral-400">
        {stage.status === "pending" || stage.status === "skipped" ? "—" : formatElapsed(elapsed)}
      </span>
    </li>
  );
}

export function YoloProgressStrip({
  run,
  subProgress,
  detail,
}: {
  run: YoloRunRecord | null;
  subProgress: number | null;
  detail?: string | null;
}) {
  const [expanded, setExpanded] = useState(false);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const active = run?.status === "running";
  const now = useSecondTicker(active || expanded);

  useEffect(() => {
    if (!expanded) return;
    const onPointerDown = (event: MouseEvent) => {
      if (panelRef.current && !panelRef.current.contains(event.target as Node)) setExpanded(false);
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [expanded]);

  const stages = run?.stages ?? [];
  const currentStage = stages.find((stage) => stage.status === "running") ?? null;
  const stepCount = stages.length || YOLO_STAGES.length;
  const currentIndex = currentStage ? stages.indexOf(currentStage) : -1;

  const { percent, settledCount } = useMemo(() => {
    const settled = stages.filter(
      (stage) => stage.status === "done" || stage.status === "skipped" || stage.status === "failed",
    ).length;
    const withinStage = currentStage ? clampProgress(subProgress) : 0;
    const total = stepCount > 0 ? (settled + withinStage) / stepCount : 0;
    return { percent: Math.round(clampProgress(total) * 100), settledCount: settled };
  }, [currentStage, stages, stepCount, subProgress]);

  const stepNumber = currentIndex >= 0 ? currentIndex + 1 : Math.min(settledCount + 1, stepCount);
  const stageElapsed = currentStage ? stageElapsedSeconds(currentStage, now) : null;
  const totalElapsed = runElapsedSeconds(run, now);
  const failedCount = stages.filter((stage) => stage.status === "failed").length;

  return (
    <div className="relative shrink-0 border-t border-b border-sky-500/15 bg-sky-500/10 px-5 py-2">
      <div className="flex items-center gap-3 text-xs">
        <span className="h-3 w-3 shrink-0 animate-spin rounded-full border-2 border-sky-300 border-t-transparent" />
        <span className="shrink-0 font-semibold text-sky-200 tabular-nums">
          YOLO Step {stepNumber}/{stepCount}
        </span>
        <span className="min-w-0 truncate text-neutral-200">
          {currentStage?.label ?? "Starting"}
          {detail && <span className="text-neutral-400"> · {detail}</span>}
        </span>
        {stageElapsed != null && (
          <span
            className="shrink-0 tabular-nums text-sky-200/90"
            title="Time spent on the current task"
          >
            {formatElapsed(stageElapsed)}
          </span>
        )}
        <div className="h-1.5 min-w-[8rem] flex-1 overflow-hidden rounded-full bg-neutral-800">
          <div
            className="h-full rounded-full bg-sky-400 transition-all duration-500"
            style={{ width: `${Math.max(3, percent)}%` }}
          />
        </div>
        <span className="shrink-0 tabular-nums text-neutral-400">{percent}%</span>
        {failedCount > 0 && (
          <span className="shrink-0 rounded-full bg-red-500/15 px-2 py-0.5 text-[10px] font-semibold text-red-300">
            {failedCount} unresolved
          </span>
        )}
        <button
          onClick={() => setExpanded((prev) => !prev)}
          className="shrink-0 rounded-md border border-sky-500/30 px-2 py-0.5 text-[10px] font-semibold text-sky-200 transition-colors hover:border-sky-400/60 hover:bg-sky-500/15"
          title="Show how long each task has taken"
        >
          {formatElapsed(totalElapsed)} total {expanded ? "▲" : "▼"}
        </button>
      </div>

      {expanded && (
        <div
          ref={panelRef}
          className="absolute right-5 z-30 mt-2 w-[30rem] rounded-xl border border-neutral-800 bg-neutral-950/95 p-3 shadow-[0_18px_42px_rgba(0,0,0,0.5)] backdrop-blur"
        >
          <div className="mb-2 flex items-baseline justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wide text-neutral-400">
              Time per task
            </span>
            <span className="text-[11px] tabular-nums text-neutral-500">{formatElapsed(totalElapsed)} total</span>
          </div>
          <ul className="max-h-80 overflow-y-auto text-[11px]">
            {stages.map((stage) => (
              <StageRow key={stage.key} stage={stage} now={now} />
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
