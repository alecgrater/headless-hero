import type { TrendingTopic } from "../../types/trending";

const SOURCE_COLORS: Record<string, { bg: string; text: string }> = {
  youtube: { bg: "bg-red-500/15", text: "text-red-400" },
  reddit: { bg: "bg-orange-500/15", text: "text-orange-400" },
  google_trends: { bg: "bg-sky-500/15", text: "text-sky-400" },
  news: { bg: "bg-neutral-500/15", text: "text-neutral-400" },
};

const SOURCE_LABELS: Record<string, string> = {
  youtube: "YouTube",
  reddit: "Reddit",
  google_trends: "Trends",
  news: "News",
};

interface Props {
  topic: TrendingTopic;
  index: number;
  onGenerateIdeas: (topic: TrendingTopic) => void;
  onDismiss: (topic: TrendingTopic) => void;
  loading?: boolean;
}

function ScoreBar({ breakdown }: { breakdown: TrendingTopic["score_breakdown"] }) {
  const segments = [
    { value: breakdown.search_velocity, color: "bg-sky-400", label: "Search" },
    { value: breakdown.competitor_view_rate, color: "bg-violet-400", label: "Competitor" },
    { value: breakdown.reddit_engagement, color: "bg-orange-400", label: "Reddit" },
    { value: breakdown.format_fit, color: "bg-emerald-400", label: "Fit" },
  ];
  const total = segments.reduce((sum, s) => sum + s.value, 0) || 1;

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 flex h-1.5 rounded-full overflow-hidden bg-neutral-700/50">
        {segments.map((seg) => (
          <div
            key={seg.label}
            className={`${seg.color} transition-all duration-500`}
            style={{ width: `${(seg.value / total) * 100}%` }}
            title={`${seg.label}: ${seg.value.toFixed(0)}`}
          />
        ))}
      </div>
      <div className="flex gap-1.5 text-[10px] text-neutral-500 shrink-0">
        {segments.map((seg) => (
          seg.value > 0 && (
            <span key={seg.label} className="flex items-center gap-0.5">
              <span className={`w-1.5 h-1.5 rounded-full ${seg.color}`} />
              {seg.value.toFixed(0)}
            </span>
          )
        ))}
      </div>
    </div>
  );
}

function ScoreBadge({ score }: { score: number }) {
  const color =
    score >= 80
      ? "from-emerald-500/20 to-emerald-500/5 text-emerald-400 border-emerald-500/30"
      : score >= 60
        ? "from-amber-500/20 to-amber-500/5 text-amber-400 border-amber-500/30"
        : "from-neutral-500/20 to-neutral-500/5 text-neutral-400 border-neutral-500/30";

  return (
    <div
      className={`flex items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-b border font-bold text-lg tabular-nums ${color}`}
    >
      {Math.round(score)}
    </div>
  );
}

export default function TopicCard({ topic, index, onGenerateIdeas, onDismiss, loading }: Props) {
  const sources = topic.source.split(",").filter(Boolean);

  return (
    <div
      className="group relative bg-neutral-800/50 border border-neutral-700/60 rounded-xl p-5 hover:border-neutral-600/80 hover:bg-neutral-800/70 transition-all duration-200"
      style={{
        animation: "fadeSlideUp 0.35s ease-out both",
        animationDelay: `${index * 60}ms`,
      }}
    >
      <div className="flex gap-4">
        {/* Score badge */}
        <div className="shrink-0 pt-0.5">
          <ScoreBadge score={topic.score} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0 space-y-2.5">
          {/* Title + badges */}
          <div className="flex items-start gap-2 flex-wrap">
            <h3 className="text-[15px] font-semibold text-neutral-100 leading-snug">
              {topic.title}
            </h3>
            {topic.is_first_mover && (
              <span className="shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded-md bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">
                First Mover
              </span>
            )}
            {topic.is_breakout && (
              <span className="shrink-0 text-[10px] font-medium px-1.5 py-0.5 rounded-md bg-amber-500/15 text-amber-400 border border-amber-500/20">
                Breakout
              </span>
            )}
          </div>

          {/* Score breakdown bar */}
          <ScoreBar breakdown={topic.score_breakdown} />

          {/* Source chips */}
          <div className="flex items-center gap-1.5">
            {sources.map((src) => {
              const style = SOURCE_COLORS[src] || SOURCE_COLORS.news;
              const label = SOURCE_LABELS[src] || src;
              return (
                <span
                  key={src}
                  className={`text-[10px] font-medium px-2 py-0.5 rounded-md ${style.bg} ${style.text}`}
                >
                  {label}
                </span>
              );
            })}
          </div>

          {/* Format fit rationale */}
          {topic.format_fit_rationale && (
            <p className="text-xs italic text-neutral-400 leading-relaxed">
              {topic.format_fit_rationale}
            </p>
          )}

          {/* Evidence snippet */}
          {topic.evidence_snippet && (
            <p className="text-[11px] text-neutral-500 leading-relaxed">
              {topic.evidence_snippet}
            </p>
          )}

          {/* Actions */}
          <div className="flex items-center gap-2 pt-1">
            <button
              onClick={() => onGenerateIdeas(topic)}
              disabled={loading}
              className="text-sm px-4 py-1.5 rounded-lg font-medium bg-violet-600 hover:bg-violet-500 disabled:opacity-50 disabled:cursor-not-allowed text-white transition-colors"
            >
              {loading ? "Generating..." : "Generate Ideas →"}
            </button>
            <button
              onClick={() => onDismiss(topic)}
              className="text-sm px-3 py-1.5 rounded-lg text-neutral-500 hover:text-neutral-300 hover:bg-neutral-700/50 transition-colors"
            >
              Dismiss
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
