import { useState } from "react";
import type { SmartIdea } from "../../types/trending";

interface Props {
  idea: SmartIdea;
  index: number;
  onUseIdea: (idea: SmartIdea) => void;
  onDismiss: (idea: SmartIdea) => void;
}

function StyleMatchBadge({ score }: { score: number }) {
  const color =
    score >= 80
      ? "from-emerald-500/20 to-emerald-500/5 text-emerald-400 border-emerald-500/30"
      : score >= 60
        ? "from-amber-500/20 to-amber-500/5 text-amber-400 border-amber-500/30"
        : "from-neutral-500/20 to-neutral-500/5 text-neutral-400 border-neutral-500/30";

  return (
    <div
      className={`flex flex-col items-center justify-center w-12 h-12 rounded-xl bg-gradient-to-b border font-bold tabular-nums ${color}`}
    >
      <span className="text-lg leading-none">{Math.round(score)}</span>
      <span className="text-[8px] font-medium opacity-60 mt-0.5">match</span>
    </div>
  );
}

const SOURCE_CHIP_COLORS: Record<string, string> = {
  youtube: "bg-red-500/15 text-red-400",
  reddit: "bg-orange-500/15 text-orange-400",
  google_trends: "bg-sky-500/15 text-sky-400",
  news: "bg-neutral-500/15 text-neutral-400",
  hackernews: "bg-amber-500/15 text-amber-400",
  wikipedia: "bg-cyan-500/15 text-cyan-400",
  stackexchange: "bg-indigo-500/15 text-indigo-400",
};

function TrendingSourceChips({ source }: { source: string }) {
  // source may be comma-separated or a description
  const parts = source.split(",").map((s) => s.trim()).filter(Boolean);
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      <span className="text-[10px] text-neutral-500">Inspired by:</span>
      {parts.map((part) => {
        // Try to match known source keys
        const key = part.toLowerCase().replace(/\s+/g, "");
        const chipColor = SOURCE_CHIP_COLORS[key] || "bg-neutral-500/15 text-neutral-400";
        return (
          <span
            key={part}
            className={`text-[10px] font-medium px-1.5 py-0.5 rounded-md ${chipColor}`}
          >
            {part}
          </span>
        );
      })}
    </div>
  );
}

export default function SmartIdeaCard({ idea, index, onUseIdea, onDismiss }: Props) {
  const [expanded, setExpanded] = useState(false);
  const hasDetails = idea.keywords.length > 0 || idea.trending_source || idea.reasoning || idea.angle;

  return (
    <div
      className="group relative bg-neutral-800/50 border border-neutral-700/60 rounded-xl p-3 hover:border-neutral-600/80 hover:bg-neutral-800/70 transition-all duration-200"
      style={{
        animation: "fadeSlideUp 0.35s ease-out both",
        animationDelay: `${index * 60}ms`,
      }}
    >
      <div
        className={`flex gap-3 ${hasDetails ? "cursor-pointer" : ""}`}
        onClick={() => hasDetails && setExpanded(!expanded)}
      >
        {/* Style match badge */}
        <div className="shrink-0">
          <StyleMatchBadge score={idea.style_match_score} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0 space-y-1">
          {/* Title row with inline actions */}
          <div className="flex items-start gap-2">
            <h3 className="flex-1 text-[15px] font-semibold text-neutral-100 leading-snug">
              {idea.title}
              {hasDetails && (
                <svg
                  className={`inline-block ml-1.5 w-3.5 h-3.5 text-neutral-500 transition-transform duration-200 ${expanded ? "rotate-180" : ""}`}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              )}
            </h3>
            <div className="flex items-center gap-1.5 shrink-0">
              <button
                onClick={(e) => { e.stopPropagation(); onUseIdea(idea); }}
                className="text-xs px-3 py-1 rounded-lg font-medium bg-violet-600 hover:bg-violet-500 text-white transition-colors"
              >
                Use Idea →
              </button>
              <button
                onClick={(e) => { e.stopPropagation(); onDismiss(idea); }}
                className="text-xs px-2 py-1 rounded-lg text-neutral-500 hover:text-neutral-300 hover:bg-neutral-700/50 transition-colors"
              >
                ×
              </button>
            </div>
          </div>

          {/* Description — truncated when collapsed */}
          <p className={`text-xs text-neutral-300 leading-relaxed ${!expanded ? "line-clamp-2" : ""}`}>
            {idea.description}
          </p>

          {/* Expanded details */}
          {expanded && (
            <div className="space-y-1.5 pt-1">
              {idea.keywords.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {idea.keywords.map((kw) => (
                    <span
                      key={kw}
                      className="text-[10px] px-2 py-0.5 rounded-md bg-neutral-700/50 text-neutral-400"
                    >
                      {kw}
                    </span>
                  ))}
                </div>
              )}

              {idea.trending_source && (
                <TrendingSourceChips source={idea.trending_source} />
              )}

              {idea.reasoning && (
                <p className="text-xs italic text-neutral-400 leading-relaxed">
                  {idea.reasoning}
                </p>
              )}

              {idea.angle && (
                <p className="text-[11px] text-neutral-500">
                  <span className="font-medium text-neutral-400">Angle:</span> {idea.angle}
                </p>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
