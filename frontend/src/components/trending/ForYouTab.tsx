import { useEffect, useState } from "react";
import {
  getContentProfile,
  refreshContentProfile,
  generateSmartIdeas,
} from "../../api";
import type { VideoIdea } from "../../types/idea";
import type { ContentProfile, SmartIdea } from "../../types/trending";
import ContentProfileCard from "./ContentProfileCard";
import SmartIdeaCard from "./SmartIdeaCard";

interface Props {
  onGenerateIdeas: (ideas: VideoIdea[], niche: string) => void;
}

export default function ForYouTab({ onGenerateIdeas }: Props) {
  const [profile, setProfile] = useState<ContentProfile | null>(null);
  const [ideas, setIdeas] = useState<SmartIdea[]>([]);
  const [loadingProfile, setLoadingProfile] = useState(true);
  const [loadingIdeas, setLoadingIdeas] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getContentProfile()
      .then((p) => setProfile(p))
      .catch(() => {})
      .finally(() => setLoadingProfile(false));
  }, []);

  const handleRefreshProfile = async () => {
    setLoadingProfile(true);
    setError(null);
    try {
      const p = await refreshContentProfile();
      setProfile(p);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to refresh profile");
    } finally {
      setLoadingProfile(false);
    }
  };

  const handleGenerate = async () => {
    setLoadingIdeas(true);
    setError(null);
    try {
      const result = await generateSmartIdeas(10);
      setIdeas(result.ideas);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate ideas");
    } finally {
      setLoadingIdeas(false);
    }
  };

  const handleUseIdea = (idea: SmartIdea) => {
    const videoIdea: VideoIdea = {
      title: idea.title,
      description: idea.description,
      segments_est: idea.segments_est,
      keywords: idea.keywords,
    };
    onGenerateIdeas([videoIdea], idea.title);
  };

  const handleDismiss = (idea: SmartIdea) => {
    setIdeas((prev) => prev.filter((i) => i.title !== idea.title));
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold mb-1">For You</h2>
          <p className="text-neutral-400 text-sm">
            AI-powered video ideas from trending data and brainstorm strategies
          </p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={loadingIdeas}
          className="flex items-center gap-2 text-sm px-4 py-2 rounded-lg font-medium bg-violet-600 hover:bg-violet-500 disabled:opacity-50 disabled:cursor-not-allowed text-white transition-colors"
        >
          {loadingIdeas ? (
            <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          ) : (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
            </svg>
          )}
          {loadingIdeas ? "Generating..." : "Generate Ideas"}
        </button>
      </div>

      {/* Content profile card — only when profile exists */}
      {profile && (
        <ContentProfileCard
          profile={profile}
          loading={loadingProfile}
          onRefresh={handleRefreshProfile}
        />
      )}

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Loading skeletons */}
      {loadingIdeas && ideas.length === 0 && (
        <div className="space-y-3">
          {[0, 1, 2].map((i) => (
            <div key={i} className="bg-neutral-800/50 border border-neutral-700/40 rounded-xl p-5 animate-pulse">
              <div className="flex gap-4">
                <div className="w-12 h-12 rounded-xl bg-neutral-700/50 shrink-0" />
                <div className="flex-1 space-y-3">
                  <div className="h-4 bg-neutral-700/50 rounded w-3/4" />
                  <div className="h-3 bg-neutral-700/50 rounded w-full" />
                  <div className="flex gap-1.5">
                    <div className="h-4 w-16 bg-neutral-700/50 rounded" />
                    <div className="h-4 w-12 bg-neutral-700/50 rounded" />
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Smart idea cards */}
      {ideas.length > 0 && (
        <div className="space-y-3">
          <p className="text-xs text-neutral-500">
            {ideas.length} idea{ideas.length !== 1 ? "s" : ""} generated
          </p>
          {ideas.map((idea, i) => (
            <SmartIdeaCard
              key={`${idea.title}-${i}`}
              idea={idea}
              index={i}
              onUseIdea={handleUseIdea}
              onDismiss={handleDismiss}
            />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loadingIdeas && ideas.length === 0 && (
        <div className="text-center py-12 space-y-3">
          <p className="text-neutral-400">
            Hit &ldquo;Generate Ideas&rdquo; to get AI-powered video suggestions
          </p>
          <p className="text-xs text-neutral-500">
            Combines trending data from 7 sources with 5 brainstorm strategies
          </p>
        </div>
      )}
    </div>
  );
}
