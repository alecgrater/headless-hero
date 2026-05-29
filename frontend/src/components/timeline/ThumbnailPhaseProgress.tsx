export type ThumbnailPhaseStatus = "pending" | "running" | "done" | "skipped" | "failed";

export interface ThumbnailPhaseItem {
  key: string;
  label: string;
  status: ThumbnailPhaseStatus;
  detail?: string;
}

const STATUS_LABELS: Record<ThumbnailPhaseStatus, string> = {
  pending: "Pending",
  running: "Running",
  done: "Done",
  skipped: "Skipped",
  failed: "Failed",
};

const STATUS_CLASSES: Record<ThumbnailPhaseStatus, string> = {
  pending: "border-neutral-700 text-neutral-500",
  running: "border-violet-500/50 bg-violet-500/10 text-violet-300",
  done: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  skipped: "border-neutral-800 text-neutral-600",
  failed: "border-red-500/50 bg-red-500/10 text-red-300",
};

function StatusDot({ status }: { status: ThumbnailPhaseStatus }) {
  const active = status === "running";
  return (
    <span
      className={`mt-1 h-2 w-2 rounded-full shrink-0 ${
        status === "done"
          ? "bg-emerald-400"
          : status === "running"
            ? "bg-violet-400"
            : status === "failed"
              ? "bg-red-400"
              : "bg-neutral-700"
      } ${active ? "animate-pulse" : ""}`}
    />
  );
}

export default function ThumbnailPhaseProgress({ phases }: { phases: ThumbnailPhaseItem[] }) {
  if (phases.length === 0) return null;

  return (
    <div className="mt-2 grid gap-1.5 rounded-lg border border-neutral-800 bg-neutral-950/80 p-2">
      {phases.map((phase) => (
        <div key={phase.key} className="flex items-start gap-2 text-[11px]">
          <StatusDot status={phase.status} />
          <div className="min-w-0 flex-1">
            <div className="flex items-center justify-between gap-2">
              <span className="truncate font-medium text-neutral-300">{phase.label}</span>
              <span className={`rounded border px-1.5 py-0.5 tabular-nums ${STATUS_CLASSES[phase.status]}`}>
                {STATUS_LABELS[phase.status]}
              </span>
            </div>
            {phase.detail && <p className="mt-0.5 truncate text-neutral-600">{phase.detail}</p>}
          </div>
        </div>
      ))}
    </div>
  );
}
