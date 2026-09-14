import { useEffect, useMemo, useState } from "react";

import type { YoloRunRecord, YoloRunStatus, YoloStageRecord } from "../../types/yolo";
import { formatElapsed } from "./timelineProduction";
import { runElapsedSeconds, stageElapsedSeconds, unresolvedStages } from "./yoloRun";

const RUN_STATUS_COPY: Record<YoloRunStatus, { label: string; tone: string }> = {
  // A stored run still marked "running" never got to close itself — Stop quits
  // the app, and a crash or an OS kill leaves the same trace.
  running: { label: "Interrupted", tone: "border-amber-500/30 bg-amber-500/10 text-amber-200" },
  completed: { label: "Completed", tone: "border-emerald-500/30 bg-emerald-500/10 text-emerald-200" },
  completed_with_failures: {
    label: "Finished with unresolved tasks",
    tone: "border-amber-500/30 bg-amber-500/10 text-amber-200",
  },
  halted: { label: "Halted", tone: "border-red-500/30 bg-red-500/10 text-red-200" },
  cancelled: { label: "Stopped", tone: "border-neutral-700 bg-neutral-900 text-neutral-300" },
};

const STAGE_STATUS_COPY: Record<YoloStageRecord["status"], string> = {
  pending: "not reached",
  running: "interrupted",
  done: "done",
  skipped: "already done",
  failed: "failed",
  cancelled: "stopped",
};

/**
 * What the last YOLO run did, shown once the run is over.
 *
 * A full generation runs for an hour or more, so the operator is nearly always
 * away when something goes wrong and the error toast is long gone by the time
 * they look. This reads the persisted run log, so the answer survives an AFK
 * return, a reload, and an app restart.
 */
export function YoloRunSummary({
  run,
  onDismiss,
}: {
  run: YoloRunRecord;
  onDismiss: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const unresolved = useMemo(() => unresolvedStages(run), [run]);
  const status = RUN_STATUS_COPY[run.status] ?? RUN_STATUS_COPY.completed;
  const endedMs = run.ended_at ? Date.parse(run.ended_at) : Date.now();
  const total = runElapsedSeconds(run, endedMs);

  useEffect(() => {
    setExpanded(false);
  }, [run.run_id]);

  const finishedAt = run.ended_at ? new Date(run.ended_at) : null;

  return (
    <div className="px-5 pb-2">
      <div className={`rounded-xl border px-3 py-2 text-xs ${status.tone}`}>
        <div className="flex items-center gap-3">
          <span className="shrink-0 font-semibold">Last YOLO run · {status.label}</span>
          <span className="shrink-0 tabular-nums opacity-80">{formatElapsed(total)}</span>
          {finishedAt && (
            <span className="shrink-0 opacity-70">
              finished {finishedAt.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}
            </span>
          )}
          <span className="min-w-0 flex-1 truncate opacity-90">
            {unresolved.length > 0
              ? `Unresolved: ${unresolved.map((stage) => stage.label).join(", ")}`
              : "Every task completed."}
          </span>
          <button
            onClick={() => setExpanded((prev) => !prev)}
            className="shrink-0 rounded-md border border-current/30 px-2 py-0.5 text-[10px] font-semibold transition-colors hover:bg-white/10"
          >
            {expanded ? "Hide timings" : "Show timings"}
          </button>
          <button
            onClick={onDismiss}
            className="shrink-0 rounded-md px-1.5 py-0.5 text-[11px] opacity-60 transition-colors hover:bg-white/10 hover:opacity-100"
            title="Dismiss"
          >
            ✕
          </button>
        </div>

        {expanded && (
          <ul className="mt-2 divide-y divide-white/5 border-t border-white/10 pt-1 text-[11px]">
            {run.stages.map((stage) => {
              const elapsed = stageElapsedSeconds(stage, endedMs);
              return (
                <li key={stage.key} className="flex items-start gap-2 py-1">
                  <span className="min-w-0 flex-1 truncate opacity-90">
                    {stage.label}
                    {stage.attempts > 1 && <span className="ml-1.5 opacity-70">· {stage.attempts} attempts</span>}
                    {stage.status === "failed" && stage.error && (
                      <span className="ml-1.5 text-red-300">· {stage.error}</span>
                    )}
                  </span>
                  <span className="w-24 shrink-0 text-right text-[10px] uppercase tracking-wide opacity-60">
                    {STAGE_STATUS_COPY[stage.status]}
                  </span>
                  <span className="w-14 shrink-0 text-right tabular-nums opacity-80">
                    {stage.status === "pending" || stage.status === "skipped" ? "—" : formatElapsed(elapsed)}
                  </span>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </div>
  );
}
