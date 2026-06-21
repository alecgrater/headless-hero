import { Check, Eye, RefreshCw, X } from "lucide-react";

import { assetUrl } from "../../api";
import type { BlinkReviewSummary, BlinkReviewStatus } from "../../types/blinkReview";

interface Props {
  summary: BlinkReviewSummary | null;
  loading: boolean;
  updatingSceneId: string | null;
  onRefresh: () => void;
  onDecision: (sceneId: string, status: "enabled" | "disabled") => void;
}

function statusLabel(status: BlinkReviewStatus) {
  if (status === "unreviewed") return "Needs review";
  if (status === "enabled") return "Enabled";
  if (status === "disabled") return "Disabled";
  return "Rejected";
}

function BlinkPreview({ imageUrl, blink }: { imageUrl: string; blink: boolean }) {
  return (
    <div className="relative min-h-0 overflow-hidden bg-neutral-950">
      <img
        src={assetUrl(imageUrl)}
        alt=""
        className="aspect-video h-auto w-full object-cover"
      />
      {blink && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-neutral-950/0">
          <div className="rounded-full border border-neutral-950/20 bg-neutral-950/70 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-neutral-100">
            Blink preview
          </div>
        </div>
      )}
      <span className="absolute left-2 top-2 rounded bg-neutral-950/70 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-neutral-200">
        {blink ? "Blink" : "Still"}
      </span>
    </div>
  );
}

export default function BlinkReviewTab({
  summary,
  loading,
  updatingSceneId,
  onRefresh,
  onDecision,
}: Props) {
  const eligible = summary?.candidates.filter((candidate) => candidate.eligible) ?? [];

  return (
    <div className="flex-1 overflow-y-auto p-5">
      <div className="mb-4 rounded-lg border border-neutral-800 bg-neutral-900/60 p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2">
              <Eye className="h-4 w-4 text-violet-300" />
              <h2 className="text-sm font-semibold text-neutral-100">Blink Review</h2>
            </div>
            <p className="mt-1 text-xs text-neutral-400">
              Review eligible full-frame blinks before rendering or exporting.
            </p>
            {summary?.review_enabled === false && (
              <p className="mt-2 text-xs font-medium text-amber-300">
                Full-frame Blink Review is disabled in Settings. Render/export will stay static and skip this review.
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={onRefresh}
            disabled={loading}
            className="inline-flex items-center gap-1.5 rounded-md border border-neutral-700 bg-neutral-800 px-3 py-2 text-xs font-medium text-neutral-200 transition-colors hover:bg-neutral-700 disabled:cursor-wait disabled:opacity-60"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-4">
          {[
            ["Eligible", summary?.eligible_count ?? 0, "text-emerald-300"],
            ["Needs review", summary?.unreviewed_count ?? 0, "text-amber-300"],
            ["Enabled", summary?.enabled_count ?? 0, "text-violet-300"],
            ["Disabled", summary?.disabled_count ?? 0, "text-neutral-300"],
          ].map(([label, value, tone]) => (
            <div key={label} className="rounded-md border border-neutral-800 bg-neutral-950/50 px-3 py-2">
              <div className="text-[11px] uppercase tracking-wide text-neutral-500">{label}</div>
              <div className={`mt-1 text-lg font-semibold tabular-nums ${tone}`}>{value}</div>
            </div>
          ))}
        </div>
      </div>

      {loading && !summary ? (
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-8 text-center text-sm text-neutral-400">
          Loading Blink Review...
        </div>
      ) : eligible.length === 0 ? (
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-8 text-center text-sm text-neutral-400">
          No safe blink candidates were found. Blink Review is complete.
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {eligible.map((candidate) => {
            const updating = updatingSceneId === candidate.scene_id;
            return (
              <div key={candidate.scene_id} className="overflow-hidden rounded-lg border border-neutral-800 bg-neutral-900">
                <div className="grid grid-cols-2">
                  <BlinkPreview imageUrl={candidate.image_url} blink={false} />
                  <BlinkPreview imageUrl={candidate.image_url} blink />
                </div>
                <div className="p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h3 className="font-mono text-sm font-semibold text-neutral-100">{candidate.scene_id}</h3>
                      <p className="mt-1 line-clamp-2 text-xs text-neutral-500">{candidate.scene_label}</p>
                    </div>
                    <span className={`rounded-full px-2 py-1 text-xs font-semibold ${
                      candidate.review_status === "enabled"
                        ? "bg-emerald-500/15 text-emerald-300"
                        : candidate.review_status === "disabled"
                          ? "bg-neutral-700 text-neutral-300"
                          : "bg-amber-500/15 text-amber-300"
                    }`}>
                      {statusLabel(candidate.review_status)}
                    </span>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => onDecision(candidate.scene_id, "enabled")}
                      disabled={updating || candidate.review_status === "enabled"}
                      className="inline-flex items-center gap-1.5 rounded-md bg-emerald-600 px-3 py-2 text-xs font-semibold text-white transition-colors hover:bg-emerald-500 disabled:cursor-wait disabled:opacity-50"
                    >
                      <Check className="h-3.5 w-3.5" />
                      Enable blink
                    </button>
                    <button
                      type="button"
                      onClick={() => onDecision(candidate.scene_id, "disabled")}
                      disabled={updating || candidate.review_status === "disabled"}
                      className="inline-flex items-center gap-1.5 rounded-md border border-neutral-700 bg-neutral-800 px-3 py-2 text-xs font-semibold text-neutral-200 transition-colors hover:bg-neutral-700 disabled:cursor-wait disabled:opacity-50"
                    >
                      <X className="h-3.5 w-3.5" />
                      Disable blink
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
