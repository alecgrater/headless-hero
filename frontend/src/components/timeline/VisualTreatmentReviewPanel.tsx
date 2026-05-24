import { useEffect, useMemo, useState } from "react";
import type { VisualTreatmentAssignment } from "../../api";
import type { Scene, VisualTreatment } from "../../types/script";

interface Props {
  assignments: VisualTreatmentAssignment[];
  scenes: Record<string, Scene>;
  onApply: (assignments: VisualTreatmentAssignment[]) => void;
  onReanalyze: () => void;
  canAnalyze: boolean;
  analyzeBlockedReason?: string;
}

const TREATMENT_LABELS: Record<VisualTreatment, { label: string; blurb: string }> = {
  full_frame: {
    label: "Full frame",
    blurb: "A normal scene image or video fills the whole frame and covers the canvas.",
  },
  popup_sequence: {
    label: "Popup sequence",
    blurb: "Two to four small illustrated panels appear on narration beats, usually left to right.",
  },
  flipflop: {
    label: "Flipflop",
    blurb: "Two complementary visuals alternate every half second for a simple animated feel.",
  },
};

const TREATMENT_OPTIONS: VisualTreatment[] = ["full_frame", "popup_sequence", "flipflop"];

export default function VisualTreatmentReviewPanel({
  assignments,
  scenes,
  onApply,
  onReanalyze,
  canAnalyze,
  analyzeBlockedReason,
}: Props) {
  const [draft, setDraft] = useState<VisualTreatmentAssignment[]>(assignments);
  const summary = useMemo(() => {
    return draft.reduce<Record<VisualTreatment, number>>(
      (acc, assignment) => {
        acc[assignment.visual_treatment] += 1;
        return acc;
      },
      { full_frame: 0, popup_sequence: 0, flipflop: 0 },
    );
  }, [draft]);
  const hasInvalidLayerlessTreatment = draft.some(
    (assignment) => assignment.visual_treatment !== "full_frame" && assignment.visual_layers.length === 0,
  );

  useEffect(() => {
    setDraft(assignments);
  }, [assignments]);

  const handleTreatmentChange = (sceneId: string, visualTreatment: VisualTreatment) => {
    setDraft((prev) =>
      prev.map((assignment) =>
        assignment.scene_id === sceneId
          ? {
              ...assignment,
              visual_treatment: visualTreatment,
              visual_layers: visualTreatment === "full_frame" ? [] : assignment.visual_layers,
            }
          : assignment,
      ),
    );
  };

  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900 overflow-hidden">
      <div className="border-b border-neutral-800 px-4 py-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-neutral-100">Animation Type Review</h3>
            <p className="max-w-3xl text-xs leading-5 text-neutral-400">
              Animation type controls how a scene is staged. Media source chooses where assets come from; animation type chooses how they appear on the canvas.
            </p>
            <p className="text-xs text-neutral-500">
              {summary.full_frame} full frame, {summary.popup_sequence} popup sequence, {summary.flipflop} flipflop
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <button
              type="button"
              onClick={onReanalyze}
              disabled={!canAnalyze}
              title={!canAnalyze ? analyzeBlockedReason : undefined}
              className="rounded-lg bg-neutral-800 px-3 py-1.5 text-xs text-neutral-300 transition-colors hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-neutral-800"
            >
              Re-analyze
            </button>
            <button
              type="button"
              onClick={() => onApply(draft)}
              disabled={hasInvalidLayerlessTreatment}
              title={hasInvalidLayerlessTreatment ? "Re-analyze before applying layer-based animation types." : undefined}
              className="rounded-lg bg-violet-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-violet-600"
            >
              Apply
            </button>
          </div>
        </div>
        {hasInvalidLayerlessTreatment && (
          <p className="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
            Re-analyze before applying popup sequence or flipflop animation types to scenes with no generated layers.
          </p>
        )}

        <div className="mt-3 grid gap-2 md:grid-cols-3">
          {TREATMENT_OPTIONS.map((treatment) => (
            <div key={treatment} className="rounded-lg border border-neutral-800 bg-neutral-950/50 px-3 py-2">
              <p className="text-xs font-semibold text-neutral-200">{TREATMENT_LABELS[treatment].label}</p>
              <p className="mt-1 text-xs leading-4 text-neutral-500">{TREATMENT_LABELS[treatment].blurb}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="divide-y divide-neutral-800">
        {draft.map((assignment, idx) => {
          const scene = scenes[assignment.scene_id];
          const hasLayers = assignment.visual_layers.length > 0;
          return (
            <div key={assignment.scene_id} className="flex items-start gap-3 px-4 py-3 text-sm">
              <span className="w-6 shrink-0 pt-1 text-right text-neutral-500">{idx + 1}</span>
              <div className="w-48 shrink-0">
                <select
                  value={assignment.visual_treatment}
                  onChange={(e) => handleTreatmentChange(assignment.scene_id, e.target.value as VisualTreatment)}
                  title={!hasLayers ? "Re-analyze to generate layers before choosing popup sequence or flipflop." : undefined}
                  className="w-full rounded border border-neutral-700 bg-neutral-800 px-2 py-1 text-xs text-neutral-200 transition-colors hover:border-neutral-600"
                >
                  {TREATMENT_OPTIONS.map((treatment) => (
                    <option key={treatment} value={treatment} disabled={treatment !== "full_frame" && !hasLayers}>
                      {TREATMENT_LABELS[treatment].label}
                    </option>
                  ))}
                </select>
                {hasLayers ? (
                  <p className="mt-1 text-xs text-neutral-500">
                    {assignment.visual_layers.length} layer{assignment.visual_layers.length === 1 ? "" : "s"}
                  </p>
                ) : (
                  <p className="mt-1 text-xs text-neutral-500">
                    Layer-based options need analysis output.
                  </p>
                )}
              </div>
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex items-center gap-2 text-xs text-neutral-500">
                  {scene?.is_title_card && <span>Title card</span>}
                  <span>{TREATMENT_LABELS[assignment.visual_treatment].label}</span>
                </div>
                <p className="truncate text-sm text-neutral-200" title={scene?.narration || ""}>
                  {scene?.narration || "No narration for this scene."}
                </p>
                <p className="text-xs leading-5 text-neutral-500">
                  {assignment.reasoning || TREATMENT_LABELS[assignment.visual_treatment].blurb}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
