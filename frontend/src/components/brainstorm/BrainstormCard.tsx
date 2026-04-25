import type { BrainstormRecommendation } from "../../types/brainstorm";

interface Props {
  recommendation: BrainstormRecommendation;
  onGenerateIdeas: (niche: string) => void;
}

export default function BrainstormCard({ recommendation, onGenerateIdeas }: Props) {
  return (
    <div className="rounded-lg border border-neutral-700 bg-neutral-800/50 p-5 space-y-3 hover:border-neutral-600 transition-colors">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <span
            className={`text-xs font-bold px-2 py-0.5 rounded-full ${
              recommendation.confidence >= 75
                ? "bg-emerald-500/20 text-emerald-300"
                : recommendation.confidence >= 50
                  ? "bg-sky-500/20 text-sky-300"
                  : "bg-neutral-700 text-neutral-400"
            }`}
          >
            {recommendation.confidence}%
          </span>
          <h3 className="font-semibold text-neutral-100">{recommendation.title}</h3>
        </div>
        <button
          onClick={() => onGenerateIdeas(recommendation.prompt)}
          className="text-xs px-3 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 text-white font-medium transition-colors shrink-0"
        >
          Generate Ideas
        </button>
      </div>

      <p className="text-sm text-neutral-300 border-l-2 border-violet-500/30 pl-3 italic">
        {recommendation.prompt}
      </p>

      <p className="text-sm text-neutral-400">{recommendation.reasoning}</p>

      {recommendation.signals.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {recommendation.signals.map((signal, i) => (
            <span
              key={i}
              className="text-xs px-2 py-0.5 rounded-full bg-neutral-700/60 text-neutral-400"
            >
              {signal}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
