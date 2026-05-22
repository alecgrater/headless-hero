import { clampProgress, YOLO_PROGRESS_STEPS } from "./timelineProduction";

export function YoloProgressStrip({
  step,
  subProgress,
  detail,
}: {
  step: string | null;
  subProgress: number | null;
  detail?: string | null;
}) {
  const rawStepIndex = YOLO_PROGRESS_STEPS.findIndex((item) => item === step);
  const stepIndex = rawStepIndex >= 0 ? rawStepIndex : 0;
  const stepNumber = stepIndex + 1;
  const stepCount = YOLO_PROGRESS_STEPS.length;
  const currentStep = step ?? "Starting";
  const boundedSubProgress = clampProgress(subProgress);
  const totalProgress = rawStepIndex >= 0 ? (stepIndex + boundedSubProgress) / stepCount : 0.03;
  const percent = Math.round(clampProgress(totalProgress) * 100);
  const visibleBarPercent = Math.max(3, percent);

  return (
    <div className="px-5 py-2 border-t border-b border-sky-500/15 shrink-0 bg-sky-500/10">
      <div className="flex items-center gap-3 text-xs">
        <span className="w-3 h-3 shrink-0 rounded-full border-2 border-sky-300 border-t-transparent animate-spin" />
        <span className="shrink-0 font-semibold text-sky-200 tabular-nums">
          YOLO Step {stepNumber}/{stepCount}
        </span>
        <span className="min-w-0 truncate text-neutral-200">
          {currentStep}
          {detail && <span className="text-neutral-400"> · {detail}</span>}
        </span>
        <div className="h-1.5 min-w-[10rem] flex-1 overflow-hidden rounded-full bg-neutral-800">
          <div
            className="h-full rounded-full bg-sky-400 transition-all duration-500"
            style={{ width: `${visibleBarPercent}%` }}
          />
        </div>
        <span className="shrink-0 text-neutral-400 tabular-nums">{percent}%</span>
      </div>
    </div>
  );
}
