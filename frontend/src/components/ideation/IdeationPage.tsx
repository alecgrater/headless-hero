import { useState } from "react";
import api from "../../api";
import type { BrandProfile } from "../../types/brand";
import type { GenerateIdeasResponse, VideoIdea } from "../../types/idea";
import IdeaCard from "./IdeaCard";
import IdeationInput from "./IdeationInput";

interface Props {
  brand: BrandProfile;
  onUseIdea: (idea: VideoIdea) => void;
}

export default function IdeationPage({ brand, onUseIdea }: Props) {
  const [ideas, setIdeas] = useState<VideoIdea[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastNiche, setLastNiche] = useState("");

  const generate = async (niche: string) => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.post("/api/ideas/generate", {
        niche,
        count: 10,
        brand_id: brand.id,
      });
      if (res.ok) {
        const data = res.data as GenerateIdeasResponse;
        setIdeas(data.ideas);
        setLastNiche(niche);
      } else {
        const err = res.data as { detail?: string };
        setError(err.detail ?? "Failed to generate ideas");
      }
    } catch {
      setError("Could not reach the backend. Is it running?");
    } finally {
      setLoading(false);
    }
  };

  const handleMoreLikeThis = (idea: VideoIdea) => {
    generate(`${lastNiche} — more ideas similar to "${idea.title}"`);
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold mb-1">Generate Video Ideas</h2>
        <p className="text-neutral-400 text-sm">
          Using brand{" "}
          <span className="text-violet-400 font-medium">{brand.name}</span>.
          Enter a niche to brainstorm video topics.
        </p>
      </div>

      <IdeationInput onGenerate={generate} loading={loading} />

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {ideas.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold text-neutral-200">
              {ideas.length} Ideas
            </h3>
            <button
              onClick={() => generate(lastNiche)}
              disabled={loading}
              className="text-sm px-3 py-1.5 bg-neutral-700 hover:bg-neutral-600 disabled:opacity-50 rounded-lg font-medium transition-colors text-neutral-300"
            >
              Regenerate All
            </button>
          </div>

          <div className="grid gap-3">
            {ideas.map((idea, i) => (
              <IdeaCard
                key={`${idea.title}-${i}`}
                idea={idea}
                onMoreLikeThis={handleMoreLikeThis}
                onUseIdea={onUseIdea}
              />
            ))}
          </div>
        </div>
      )}

      {!loading && ideas.length === 0 && !error && (
        <div className="text-center py-16 text-neutral-500">
          <p className="text-lg">Enter a niche above to get started</p>
          <p className="text-sm mt-1">
            Try "psychology", "space", "history", "gaming", or anything else
          </p>
        </div>
      )}
    </div>
  );
}
