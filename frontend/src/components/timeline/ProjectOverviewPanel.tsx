import { type LucideIcon, Check } from "lucide-react";

export type OverviewStep = {
  key: string;
  label: string;
  Icon: LucideIcon;
  description: string;
  cta: string;
  done: boolean;
  missingCount: number;
  busy: boolean;
  onRun: () => void;
};

function Spinner({ className = "h-3.5 w-3.5" }: { className?: string }) {
  return (
    <span className={`${className} rounded-full border-2 border-current border-t-transparent animate-spin`} />
  );
}

function StatusPill({ done, missingCount, busy }: { done: boolean; missingCount: number; busy: boolean }) {
  if (busy) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-300">
        <Spinner className="h-3 w-3" />
        Working
      </span>
    );
  }
  if (done) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-300">
        <Check className="h-3 w-3" />
        Done
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded-full bg-neutral-800 px-2 py-0.5 text-[11px] font-medium text-neutral-400">
      {missingCount > 0 ? `${missingCount} left` : "Not started"}
    </span>
  );
}

/**
 * Idle preview panel shown below the timeline when no scene is selected.
 * Replaces the bare "Select a scene to preview" empty state with a project
 * overview: production progress, the next actionable step, a status checklist,
 * and a hint to select a scene. Purely presentational — all step state and
 * handlers are assembled by TimelineEditor and passed in.
 */
export default function ProjectOverviewPanel({
  steps,
  segmentCount,
  sceneCount,
  durationStr,
  totalWords,
  onOpenUploadSuite,
}: {
  steps: OverviewStep[];
  segmentCount: number;
  sceneCount: number;
  durationStr: string;
  totalWords: number;
  onOpenUploadSuite: () => void;
}) {
  const total = steps.length;
  const completedCount = steps.filter((step) => step.done).length;
  const nextStep = steps.find((step) => !step.done) ?? null;
  const allDone = total > 0 && nextStep === null;
  const pct = total > 0 ? (completedCount / total) * 100 : 0;

  return (
    <div className="flex-1 min-h-0 overflow-y-auto border-t border-neutral-800/60 px-6 py-6">
      <div className="mx-auto w-full max-w-2xl space-y-5">
        {/* Progress header */}
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">Project Overview</p>
          <div className="mt-1 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <h3 className="text-lg font-semibold tracking-tight text-neutral-100">
              {allDone ? "Production complete" : `${completedCount} of ${total} steps complete`}
            </h3>
            <span className="text-xs tabular-nums text-neutral-500">
              {segmentCount.toLocaleString()} segments · {sceneCount.toLocaleString()} scenes · {durationStr} · {totalWords.toLocaleString()} words
            </span>
          </div>
          <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-neutral-800">
            <div
              className={`h-full rounded-full transition-all duration-500 ${allDone ? "bg-emerald-500" : "bg-violet-500"}`}
              style={{ width: `${pct}%` }}
            />
          </div>
        </div>

        {/* Next step / completion card */}
        {allDone ? (
          <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-emerald-500/40 bg-emerald-500/5 px-5 py-4">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-emerald-200">Production complete — ready to upload</p>
              <p className="mt-0.5 text-xs text-neutral-400">Every step is done. Open the upload suite to publish.</p>
            </div>
            <button
              type="button"
              onClick={onOpenUploadSuite}
              className="shrink-0 rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-emerald-500"
            >
              Upload suite
            </button>
          </div>
        ) : nextStep ? (
          <div className="rounded-2xl border border-violet-500/40 bg-violet-500/5 px-5 py-4">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex min-w-0 items-start gap-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-violet-500/15 text-violet-200">
                  <nextStep.Icon className="h-5 w-5" />
                </span>
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-violet-300/80">Next step</p>
                  <p className="text-sm font-semibold text-neutral-100">{nextStep.label}</p>
                  <p className="mt-0.5 text-xs text-neutral-400">{nextStep.description}</p>
                </div>
              </div>
              <button
                type="button"
                onClick={nextStep.onRun}
                disabled={nextStep.busy}
                className="inline-flex shrink-0 items-center gap-2 rounded-lg bg-violet-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-violet-500 disabled:cursor-wait disabled:opacity-60"
              >
                {nextStep.busy ? (
                  <>
                    <Spinner />
                    Working…
                  </>
                ) : (
                  nextStep.cta
                )}
              </button>
            </div>
          </div>
        ) : null}

        {/* Step checklist */}
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {steps.map((step) => (
            <div
              key={step.key}
              className="flex items-center justify-between gap-3 rounded-xl border border-neutral-800 bg-neutral-950/40 px-3.5 py-2.5"
            >
              <span className="flex min-w-0 items-center gap-2.5">
                <step.Icon className="h-4 w-4 shrink-0 text-neutral-500" />
                <span className="truncate text-sm text-neutral-300">{step.label}</span>
              </span>
              <StatusPill done={step.done} missingCount={step.missingCount} busy={step.busy} />
            </div>
          ))}
        </div>

        {/* Selection hint */}
        <p className="pt-1 text-center text-xs text-neutral-500">
          Select any scene in the timeline above to edit its visuals, voice, and timing
          <span className="ml-2 inline-flex items-center gap-1 rounded-md border border-neutral-800 bg-neutral-900/60 px-1.5 py-0.5 align-middle font-mono text-[10px] text-neutral-400">
            ← →
          </span>
        </p>
      </div>
    </div>
  );
}
