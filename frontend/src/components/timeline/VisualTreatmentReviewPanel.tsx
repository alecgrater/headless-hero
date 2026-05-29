import { useEffect, useMemo, useState } from "react";
import type { VisualTreatmentAssignment } from "../../api";
import type { Scene, VisualMode } from "../../types/script";

interface Props {
  assignments: VisualTreatmentAssignment[];
  scenes: Record<string, Scene>;
  onApply: (assignments: VisualTreatmentAssignment[]) => void;
  onReanalyze: () => void;
  canAnalyze: boolean;
  analyzeBlockedReason?: string;
}

const MODE_LABELS: Record<VisualMode, { label: string; blurb: string }> = {
  video: {
    label: "Video",
    blurb: "An AI-generated clip owns the scene and renders full-frame.",
  },
  full_frame: {
    label: "Full frame",
    blurb: "A normal scene image or video fills the whole frame and covers the canvas.",
  },
  multi_frame: {
    label: "Multi-frame",
    blurb: "Several independent images share one narration scene and cut between examples or comparisons.",
  },
  continuous: {
    label: "Continuous",
    blurb: "Related frames keep reference continuity so one action or transformation unfolds over time.",
  },
  popup_sequence: {
    label: "Popup sequence",
    blurb: "Two to four small illustrated panels appear on narration beats, usually left to right.",
  },
  flipflop: {
    label: "Flipflop",
    blurb: "Two adjacent A/B scenes alternate rapidly for a simple animated feel.",
  },
  captions: {
    label: "Captions",
    blurb: "Large editorial text lands on narration beats with red emphasis.",
  },
};

const MODE_OPTIONS: VisualMode[] = ["full_frame", "multi_frame", "continuous", "popup_sequence", "flipflop"];
const modeForAssignment = (assignment: VisualTreatmentAssignment): VisualMode =>
  assignment.visual_mode ?? "full_frame";
const isLayeredMode = (mode: VisualMode): mode is Extract<VisualMode, "popup_sequence" | "flipflop"> =>
  mode === "popup_sequence" || mode === "flipflop";

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
    return draft.reduce<Record<VisualMode, number>>(
      (acc, assignment) => {
        acc[modeForAssignment(assignment)] += 1;
        return acc;
      },
      { video: 0, full_frame: 0, multi_frame: 0, continuous: 0, popup_sequence: 0, flipflop: 0, captions: 0 },
    );
  }, [draft]);
  const hasInvalidLayerlessTreatment = draft.some(
    (assignment) => {
      const mode = modeForAssignment(assignment);
      return isLayeredMode(mode) && assignment.visual_layers.length === 0;
    },
  );

  useEffect(() => {
    setDraft(assignments);
  }, [assignments]);

  const handleModeChange = (sceneId: string, visualMode: VisualMode) => {
    const isLayered = isLayeredMode(visualMode);
    setDraft((prev) =>
      prev.map((assignment) => {
        const shouldPreserveVisualLayers = isLayered && visualMode === modeForAssignment(assignment);
        return assignment.scene_id === sceneId
          ? {
              ...assignment,
              visual_mode: visualMode,
              visual_layers: shouldPreserveVisualLayers ? assignment.visual_layers : [],
            }
          : assignment;
      }),
    );
  };

  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900 overflow-hidden">
      <div className="border-b border-neutral-800 px-4 py-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="space-y-1">
            <h3 className="text-sm font-semibold text-neutral-100">Visual Mode Review</h3>
            <p className="max-w-3xl text-xs leading-5 text-neutral-400">
              Visual mode controls the scene route and the assets it owns: video clip, full-frame image, popup cutouts, or flip-flop panels.
            </p>
            <p className="text-xs text-neutral-500">
              {summary.video} video, {summary.full_frame} full frame, {summary.multi_frame} multi-frame,{" "}
              {summary.continuous} continuous, {summary.popup_sequence} popup sequence, {summary.flipflop} flipflop,{" "}
              {summary.captions} captions
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
              title={hasInvalidLayerlessTreatment ? "Re-analyze before applying layer-based visual modes." : undefined}
              className="rounded-lg bg-violet-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-violet-600"
            >
              Apply
            </button>
          </div>
        </div>
        {hasInvalidLayerlessTreatment && (
          <p className="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
            Re-analyze before applying popup sequence or flip-flop modes to scenes with no generated layers.
          </p>
        )}

        <div className="mt-3 grid gap-2 md:grid-cols-3">
          {MODE_OPTIONS.map((mode) => (
            <div key={mode} className="rounded-lg border border-neutral-800 bg-neutral-950/50 px-3 py-2">
              <p className="text-xs font-semibold text-neutral-200">{MODE_LABELS[mode].label}</p>
              <p className="mt-1 text-xs leading-4 text-neutral-500">{MODE_LABELS[mode].blurb}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="divide-y divide-neutral-800">
        {draft.map((assignment, idx) => {
          const scene = scenes[assignment.scene_id];
          const mode = modeForAssignment(assignment);
          const hasLayers = assignment.visual_layers.length > 0;
          return (
            <div key={assignment.scene_id} className="flex items-start gap-3 px-4 py-3 text-sm">
              <span className="w-6 shrink-0 pt-1 text-right text-neutral-500">{idx + 1}</span>
              <div className="w-48 shrink-0">
                <select
                  value={mode}
                  onChange={(e) => handleModeChange(assignment.scene_id, e.target.value as VisualMode)}
                  title={!hasLayers ? "Re-analyze to generate layers before choosing popup sequence or flipflop." : undefined}
                  className="w-full rounded border border-neutral-700 bg-neutral-800 px-2 py-1 text-xs text-neutral-200 transition-colors hover:border-neutral-600"
                >
                  {MODE_OPTIONS.map((optionMode) => (
                    <option key={optionMode} value={optionMode} disabled={isLayeredMode(optionMode) && !hasLayers}>
                      {MODE_LABELS[optionMode].label}
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
                  <span>{MODE_LABELS[mode].label}</span>
                </div>
                <p className="truncate text-sm text-neutral-200" title={scene?.narration || ""}>
                  {scene?.narration || "No narration for this scene."}
                </p>
                <p className="text-xs leading-5 text-neutral-500">
                  {assignment.reasoning || MODE_LABELS[mode].blurb}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
