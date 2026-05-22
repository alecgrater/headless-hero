import { Star } from "lucide-react";
import type { VideoIdea } from "../../types/idea";

interface Props {
  idea: VideoIdea;
  index: number;
  bookmarked: boolean;
  onToggleBookmark: () => void;
  onMoreLikeThis: (idea: VideoIdea) => void;
  onUseIdea: (idea: VideoIdea) => void;
  animationDelay?: number;
}

const MAX_KEYWORDS = 4;

export default function GeneratedIdeaCard({
  idea,
  index,
  bookmarked,
  onToggleBookmark,
  onMoreLikeThis,
  onUseIdea,
  animationDelay,
}: Props) {
  const displayIndex = String(index + 1).padStart(2, "0");
  const visibleKeywords = idea.keywords.slice(0, MAX_KEYWORDS);
  const overflowCount = idea.keywords.length - MAX_KEYWORDS;

  return (
    <div
      className="relative rounded-lg border border-neutral-700 bg-neutral-800/50 p-5 space-y-3 hover:border-neutral-600 transition-colors overflow-hidden"
      style={
        animationDelay !== undefined
          ? {
              animation: "fadeSlideUp 0.35s ease-out both",
              animationDelay: `${animationDelay}ms`,
            }
          : undefined
      }
    >
      {/* Ghost index number */}
      <span className="absolute top-3 left-4 text-3xl font-bold text-neutral-700/50 leading-none select-none pointer-events-none">
        {displayIndex}
      </span>

      <div className="flex items-start justify-between gap-3 pl-10">
        <h3 className="font-semibold text-neutral-100 leading-snug">
          {idea.title}
        </h3>
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={onToggleBookmark}
            className="p-1 transition-colors hover:scale-110 active:scale-95"
            title={bookmarked ? "Remove bookmark" : "Bookmark idea"}
          >
            {bookmarked ? (
              <Star
                className="w-4.5 h-4.5 text-amber-400"
                fill="currentColor"
                strokeWidth={0}
              />
            ) : (
              <Star
                className="w-4.5 h-4.5 text-neutral-600 hover:text-neutral-400"
                strokeWidth={1.5}
              />
            )}
          </button>
          <span className="text-xs font-medium px-2 py-1 rounded bg-neutral-700 text-neutral-200 border border-neutral-600">
            ~{idea.segments_est} segments
          </span>
        </div>
      </div>

      <p className="text-sm text-neutral-400 leading-relaxed pl-10">
        {idea.description}
      </p>

      <div className="flex flex-wrap gap-1.5 pl-10">
        {visibleKeywords.map((kw) => (
          <span
            key={kw}
            className="text-xs px-2 py-0.5 rounded-full bg-neutral-700 text-neutral-300"
          >
            {kw}
          </span>
        ))}
        {overflowCount > 0 && (
          <span className="text-xs px-2 py-0.5 rounded-full bg-neutral-700/50 text-neutral-500">
            +{overflowCount}
          </span>
        )}
      </div>

      <div className="flex items-center gap-3 pt-1 pl-10">
        <button
          onClick={() => onUseIdea(idea)}
          className="text-sm px-4 py-2 bg-violet-600 hover:bg-violet-500 rounded-lg font-medium transition-colors"
        >
          Use This Idea
        </button>
        <button
          onClick={() => onMoreLikeThis(idea)}
          className="text-sm px-2 py-2 text-neutral-400 hover:text-neutral-200 font-medium transition-colors"
        >
          More Like This →
        </button>
      </div>
    </div>
  );
}
