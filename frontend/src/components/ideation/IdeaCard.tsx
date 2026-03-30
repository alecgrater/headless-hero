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

export default function IdeaCard({
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
              <svg
                className="w-4.5 h-4.5 text-amber-400"
                fill="currentColor"
                viewBox="0 0 20 20"
              >
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
              </svg>
            ) : (
              <svg
                className="w-4.5 h-4.5 text-neutral-600 hover:text-neutral-400"
                fill="none"
                stroke="currentColor"
                strokeWidth={1.5}
                viewBox="0 0 20 20"
              >
                <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
              </svg>
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
