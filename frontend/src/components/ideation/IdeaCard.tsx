import type { VideoIdea } from "../../types/idea";

interface Props {
  idea: VideoIdea;
  onMoreLikeThis: (idea: VideoIdea) => void;
  onUseIdea: (idea: VideoIdea) => void;
}

export default function IdeaCard({ idea, onMoreLikeThis, onUseIdea }: Props) {
  return (
    <div className="rounded-lg border border-neutral-700 bg-neutral-800/50 p-5 space-y-3 hover:border-neutral-600 transition-colors">
      <div className="flex items-start justify-between gap-3">
        <h3 className="font-semibold text-neutral-100 leading-snug">
          {idea.title}
        </h3>
        <span className="shrink-0 text-xs font-medium px-2 py-1 rounded bg-violet-600/20 text-violet-300">
          ~{idea.segments_est} segments
        </span>
      </div>

      <p className="text-sm text-neutral-400 leading-relaxed">
        {idea.description}
      </p>

      <div className="flex flex-wrap gap-1.5">
        {idea.keywords.map((kw) => (
          <span
            key={kw}
            className="text-xs px-2 py-0.5 rounded-full bg-neutral-700 text-neutral-300"
          >
            {kw}
          </span>
        ))}
      </div>

      <div className="flex gap-2 pt-1">
        <button
          onClick={() => onUseIdea(idea)}
          className="text-sm px-3 py-1.5 bg-violet-600 hover:bg-violet-500 rounded-lg font-medium transition-colors"
        >
          Use This Idea
        </button>
        <button
          onClick={() => onMoreLikeThis(idea)}
          className="text-sm px-3 py-1.5 bg-neutral-700 hover:bg-neutral-600 rounded-lg font-medium transition-colors text-neutral-300"
        >
          More Like This
        </button>
      </div>
    </div>
  );
}
