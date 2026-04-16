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
  const [gated, setGated] = useState(false);

  useEffect(() => {
    getContentProfile()
      .then((p) => {
        if (p && p.script_count >= 3) {
          setProfile(p);
        } else if (p && p.script_count < 3) {
          setGated(true);
        }
        // If null, profile not yet generated — show setup state
      })
      .catch(() => {})
      .finally(() => setLoadingProfile(false));
  }, []);

  const handleSetupProfile = async () => {
    setLoadingProfile(true);
    setError(null);
    try {
      const p = await refreshContentProfile();
      setProfile(p);
      setGated(false);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Failed to analyze";
      if (msg.includes("No scripts") || msg.includes("422")) {
        setGated(true);
      } else {
        setError(msg);
      }
    } finally {
      setLoadingProfile(false);
    }
  };

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

  // Gated state: not enough scripts
  if (gated) {
    return (
      <div className="text-center py-20 space-y-5">
        <div className="flex justify-center">
          <div className="w-16 h-16 rounded-2xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center">
            <svg className="w-8 h-8 text-violet-400/60" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 6.042A8.967 8.967 0 006 3.75c-1.052 0-2.062.18-3 .512v14.25A8.987 8.987 0 016 18c2.305 0 4.408.867 6 2.292m0-14.25a8.966 8.966 0 016-2.292c1.052 0 2.062.18 3 .512v14.25A8.987 8.987 0 0018 18a8.967 8.967 0 00-6 2.292m0-14.25v14.25" />
            </svg>
          </div>
        </div>
        <div>
          <p className="text-xl font-semibold text-neutral-200">Build Your Content Profile</p>
          <p className="text-sm text-neutral-400 mt-2 max-w-md mx-auto leading-relaxed">
            Create at least 3 scripts to unlock personalized recommendations.
            This feature learns your content style and blends it with trending topics
            to generate ideas tailored to your audience.
          </p>
        </div>
        <div className="flex items-center justify-center gap-2 text-xs text-neutral-500">
          <div className="flex -space-x-1">
            {[0, 1, 2].map((i) => (
              <div
                key={i}
                className={`w-6 h-6 rounded-full border-2 border-neutral-900 flex items-center justify-center text-[9px] font-bold ${
                  i < (profile?.script_count ?? 0)
                    ? "bg-violet-500/30 text-violet-300"
                    : "bg-neutral-700/50 text-neutral-500"
                }`}
              >
                {i + 1}
              </div>
            ))}
          </div>
          <span>{profile?.script_count ?? 0} of 3 scripts needed</span>
        </div>
      </div>
    );
  }

  // Loading state
  if (loadingProfile && !profile) {
    return (
      <div className="space-y-4">
        <div className="bg-neutral-800/50 border border-neutral-700/40 rounded-xl p-5 animate-pulse">
          <div className="h-4 bg-neutral-700/50 rounded w-48 mb-3" />
          <div className="h-3 bg-neutral-700/50 rounded w-full mb-2" />
          <div className="h-3 bg-neutral-700/50 rounded w-2/3" />
        </div>
      </div>
    );
  }

  // No profile yet — offer to analyze
  if (!profile) {
    return (
      <div className="text-center py-20 space-y-5">
        <div className="flex justify-center">
          <div className="w-16 h-16 rounded-2xl bg-violet-500/10 border border-violet-500/20 flex items-center justify-center">
            <svg className="w-8 h-8 text-violet-400/60" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" />
            </svg>
          </div>
        </div>
        <div>
          <p className="text-xl font-semibold text-neutral-200">Personalized Ideas</p>
          <p className="text-sm text-neutral-400 mt-2 max-w-md mx-auto leading-relaxed">
            Analyze your script library to build a content profile, then get
            smart video ideas that match your style and capitalize on trends.
          </p>
        </div>
        <button
          onClick={handleSetupProfile}
          disabled={loadingProfile}
          className="text-sm px-5 py-2.5 rounded-lg font-medium bg-violet-600 hover:bg-violet-500 disabled:opacity-50 text-white transition-colors"
        >
          {loadingProfile ? "Analyzing..." : "Analyze My Content"}
        </button>
        {error && (
          <p className="text-sm text-red-400">{error}</p>
        )}
      </div>
    );
  }

  // Full UI: profile loaded
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold mb-1">For You</h2>
          <p className="text-neutral-400 text-sm">
            Ideas tailored to your style, powered by trending data
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

      {/* Content profile card */}
      <ContentProfileCard
        profile={profile}
        loading={loadingProfile}
        onRefresh={handleRefreshProfile}
      />

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

      {/* Empty state when no ideas yet */}
      {!loadingIdeas && ideas.length === 0 && (
        <div className="text-center py-12 space-y-3">
          <p className="text-neutral-400">
            Hit &ldquo;Generate Ideas&rdquo; to get personalized suggestions
          </p>
          <p className="text-xs text-neutral-500">
            Combines your content style with current trends from 7 sources
          </p>
        </div>
      )}
    </div>
  );
}
