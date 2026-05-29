import type { ColdOpenResult, ColdOpenVariant } from "../../types/script";

interface Props {
  result: ColdOpenResult;
  onSelect: (variant: ColdOpenVariant) => void;
}

function ScoreBar({ label, value, color }: { label: string; value: number; color: string }) {
  return (
    <div className="space-y-0.5">
      <div className="flex justify-between text-xs">
        <span className="text-neutral-500">{label}</span>
        <span className="text-neutral-400">{value}</span>
      </div>
      <div className="h-1.5 bg-neutral-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${color}`}
          style={{ width: `${value}%` }}
        />
      </div>
    </div>
  );
}

export default function ColdOpenSelector({ result, onSelect }: Props) {
  const labels = {
    tension: result.score_labels?.tension ?? "Tension",
    specificity: result.score_labels?.specificity ?? "Specificity",
    drop_rate_risk: result.score_labels?.drop_rate_risk ?? "Drop Risk",
  };

  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-neutral-100">
          {result.heading ?? "Choose Your Cold Open"}
        </h3>
        <p className="text-sm text-neutral-500">
          {result.description ?? "3 hook styles scored on tension, specificity, and drop-rate risk. Pick the one that fits your video."}
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {result.variants.map((variant) => {
          const isWinner = variant.id === result.winner_id;
          return (
            <div
              key={variant.id}
              className={`rounded-lg border p-4 space-y-3 cursor-pointer transition-all hover:border-violet-500/60 ${
                isWinner
                  ? "border-violet-500/50 ring-1 ring-violet-500/20 bg-neutral-900"
                  : "border-neutral-800 bg-neutral-900 hover:bg-neutral-900/80"
              }`}
              onClick={() => onSelect(variant)}
            >
              {/* Style label */}
              <div className="flex items-center gap-2">
                <span className="text-xs font-medium bg-violet-500/20 text-violet-300 px-2 py-0.5 rounded-full">
                  {variant.style}
                </span>
                {isWinner && (
                  <span className="text-xs font-medium bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded-full">
                    Recommended
                  </span>
                )}
              </div>

              {/* Hook text */}
              <p className="text-neutral-200 italic text-sm leading-relaxed">
                &ldquo;{variant.intro_hook}&rdquo;
              </p>

              {/* Opening narration */}
              <p className="text-neutral-400 text-sm leading-relaxed">
                {variant.opening_narration}
              </p>

              {/* Score bars */}
              <div className="space-y-2 pt-1">
                <ScoreBar label={labels.tension} value={variant.scores.tension} color="bg-emerald-500" />
                <ScoreBar label={labels.specificity} value={variant.scores.specificity} color="bg-sky-500" />
                <ScoreBar label={labels.drop_rate_risk} value={variant.scores.drop_rate_risk} color="bg-red-500" />
              </div>

              {/* Overall score */}
              <div className="flex items-baseline gap-1.5 pt-1">
                <span className="text-2xl font-bold text-neutral-100">
                  {variant.scores.overall.toFixed(0)}
                </span>
                <span className="text-xs text-neutral-500">overall</span>
              </div>

              {/* Reasoning */}
              <p className="text-xs italic text-neutral-500 leading-relaxed">
                {variant.scores.reasoning}
              </p>

              {/* Select button */}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onSelect(variant);
                }}
                className={`w-full py-2 rounded-lg text-sm font-medium transition-colors ${
                  isWinner
                    ? "bg-violet-600 hover:bg-violet-500 text-white"
                    : "bg-neutral-800 hover:bg-neutral-700 text-neutral-300 border border-neutral-700"
                }`}
              >
                Use This Opening
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
