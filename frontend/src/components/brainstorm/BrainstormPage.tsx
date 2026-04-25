import { useState } from "react";
import { generateBrainstormRecommendations } from "../../api";
import type { BrainstormRecommendation } from "../../types/brainstorm";
import BrainstormCard from "./BrainstormCard";

interface Props {
  onGenerateIdeas: (niche: string) => void;
}

export default function BrainstormPage({ onGenerateIdeas }: Props) {
  const [recommendations, setRecommendations] = useState<BrainstormRecommendation[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<{ script_count: number; topic_count: number } | null>(null);

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await generateBrainstormRecommendations();
      const sorted = [...data.recommendations].sort((a, b) => b.confidence - a.confidence);
      setRecommendations(sorted);
      setStats(data.stats);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate recommendations");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
      <div>
        <h2 className="text-2xl font-bold mb-1">Brainstorm</h2>
        <p className="text-neutral-400 text-sm">
          AI-powered recommendations based on your past videos and trending topics.
        </p>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={handleGenerate}
          disabled={loading}
          className="text-sm px-5 py-2.5 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-50 disabled:cursor-not-allowed text-white font-medium transition-colors"
        >
          {loading ? "Generating..." : "Generate Recommendations"}
        </button>
        {stats && (
          <span className="text-xs text-neutral-500">
            Based on {stats.script_count} past video{stats.script_count !== 1 ? "s" : ""} and {stats.topic_count} trending topic{stats.topic_count !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {recommendations.length > 0 && (
        <div className="space-y-3">
          {recommendations.map((rec, i) => (
            <BrainstormCard
              key={`${rec.title}-${i}`}
              recommendation={rec}
              onGenerateIdeas={onGenerateIdeas}
            />
          ))}
        </div>
      )}

      {!loading && recommendations.length === 0 && !error && (
        <div className="text-center py-20 space-y-3">
          <div className="flex justify-center">
            <svg className="w-12 h-12 text-violet-500/40" fill="none" viewBox="0 0 24 24" strokeWidth={1.2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
            </svg>
          </div>
          <p className="text-lg font-medium text-neutral-300">
            Ready to brainstorm?
          </p>
          <p className="text-sm text-neutral-500">
            Click "Generate Recommendations" to get AI-powered niche suggestions based on your content history and trending data.
          </p>
        </div>
      )}
    </div>
  );
}
