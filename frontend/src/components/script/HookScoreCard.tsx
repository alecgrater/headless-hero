import type { HookScore } from "../../types/script";

interface Props {
  hookScore: HookScore | null;
  loading: boolean;
  error: string | null;
  onRescore: () => void;
  score?: HookScore | null;
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

function overallColor(score: number): string {
  if (score >= 80) return "text-emerald-400";
  if (score >= 50) return "text-amber-400";
  return "text-red-400";
}

export default function HookScoreCard({ hookScore, loading, error, onRescore, score }: Props) {
  // Direct score display (no loading/error/re-score button)
  if (score) {
    return (
      <div className="rounded-lg border border-neutral-800 bg-neutral-900 px-5 py-4 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-neutral-200 uppercase tracking-wider">
            Hook Retention Score
          </h3>
          <span className={`text-3xl font-bold tabular-nums ${overallColor(score.overall)}`}>
            {score.overall}
          </span>
        </div>

        {/* Dimension bars */}
        <div className="space-y-2">
          <ScoreBar label="Promise" value={score.promise.score} color="bg-violet-500" />
          <ScoreBar label="Tension" value={score.tension.score} color="bg-emerald-500" />
          <ScoreBar label="Payoff Hint" value={score.payoff_hint.score} color="bg-sky-500" />
        </div>

        {/* Dimension reasoning */}
        <div className="space-y-1.5 text-xs text-neutral-500">
          <p><span className="text-violet-400 font-medium">Promise:</span> {score.promise.reasoning}</p>
          <p><span className="text-emerald-400 font-medium">Tension:</span> {score.tension.reasoning}</p>
          <p><span className="text-sky-400 font-medium">Payoff Hint:</span> {score.payoff_hint.reasoning}</p>
        </div>

        {/* Suggestions */}
        {score.suggestions.length > 0 && (
          <div>
            <p className="text-xs font-medium text-neutral-400 mb-1">Suggestions</p>
            <ul className="space-y-1 text-xs text-neutral-500 list-disc list-inside">
              {score.suggestions.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    );
  }

  // Loading state
  if (loading) {
    return (
      <div className="rounded-lg border border-neutral-800 bg-neutral-900 px-5 py-4 space-y-3">
        <h3 className="text-sm font-semibold text-neutral-200 uppercase tracking-wider">
          Hook Retention Score
        </h3>
        <div className="flex items-center gap-3">
          <div className="w-5 h-5 border-2 border-violet-500 border-t-transparent rounded-full animate-spin shrink-0" />
          <span className="text-sm text-neutral-400">Analyzing your hook for retention...</span>
        </div>
        <div className="space-y-2.5 animate-pulse">
          <div className="h-1.5 bg-neutral-800 rounded-full w-3/4" />
          <div className="h-1.5 bg-neutral-800 rounded-full w-2/3" />
          <div className="h-1.5 bg-neutral-800 rounded-full w-4/5" />
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-5 py-4 space-y-2">
        <h3 className="text-sm font-semibold text-neutral-200 uppercase tracking-wider">
          Hook Retention Score
        </h3>
        <p className="text-sm text-red-300">{error}</p>
        <button
          onClick={onRescore}
          className="text-xs px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 rounded-md transition-colors text-neutral-300 border border-neutral-700"
        >
          Retry
        </button>
      </div>
    );
  }

  // No score yet (hasn't started)
  if (!hookScore) return null;

  // Scored state
  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900 px-5 py-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-neutral-200 uppercase tracking-wider">
          Hook Retention Score
        </h3>
        <span className={`text-3xl font-bold tabular-nums ${overallColor(hookScore.overall)}`}>
          {hookScore.overall}
        </span>
      </div>

      {/* Dimension bars */}
      <div className="space-y-2">
        <ScoreBar label="Promise" value={hookScore.promise.score} color="bg-violet-500" />
        <ScoreBar label="Tension" value={hookScore.tension.score} color="bg-emerald-500" />
        <ScoreBar label="Payoff Hint" value={hookScore.payoff_hint.score} color="bg-sky-500" />
      </div>

      {/* Dimension reasoning */}
      <div className="space-y-1.5 text-xs text-neutral-500">
        <p><span className="text-violet-400 font-medium">Promise:</span> {hookScore.promise.reasoning}</p>
        <p><span className="text-emerald-400 font-medium">Tension:</span> {hookScore.tension.reasoning}</p>
        <p><span className="text-sky-400 font-medium">Payoff Hint:</span> {hookScore.payoff_hint.reasoning}</p>
      </div>

      {/* Suggestions */}
      {hookScore.suggestions.length > 0 && (
        <div>
          <p className="text-xs font-medium text-neutral-400 mb-1">Suggestions</p>
          <ul className="space-y-1 text-xs text-neutral-500 list-disc list-inside">
            {hookScore.suggestions.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Re-score button */}
      <button
        onClick={onRescore}
        className="text-xs px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 rounded-md transition-colors text-neutral-300 border border-neutral-700"
      >
        Re-score
      </button>
    </div>
  );
}
