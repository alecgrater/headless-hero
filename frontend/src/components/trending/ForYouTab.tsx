import { useEffect, useMemo, useState } from "react";
import {
  getContentProfile,
  refreshContentProfile,
  generateSmartIdeas,
  createPostIt,
} from "../../api";
import { showToast } from "../ToastContainer";
import type { VideoIdea } from "../../types/idea";
import type { ContentProfile, SmartIdea } from "../../types/trending";
import ContentProfileCard from "./ContentProfileCard";
import SmartIdeaCard from "./SmartIdeaCard";
import { Button } from "../ui/Button";
import { SkeletonCard } from "../ui/Skeleton";

interface Props {
  onGenerateIdeas: (ideas: VideoIdea[], niche: string) => void;
}

export default function ForYouTab({ onGenerateIdeas }: Props) {
  const [profile, setProfile] = useState<ContentProfile | null>(null);
  const [ideas, setIdeas] = useState<SmartIdea[]>([]);
  const [categoryOrder, setCategoryOrder] = useState<string[]>([]);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
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
      const result = await generateSmartIdeas(40);
      setIdeas(result.ideas);
      setCategoryOrder(result.categories);
      setActiveCategory(null);
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

  const handleSaveToPostIt = async (idea: SmartIdea) => {
    try {
      await createPostIt(idea.title, 70, "for_you");
      showToast("Saved to Post-Its", "success");
    } catch {
      showToast("Failed to save to Post-Its");
    }
  };

  const { categories, categoryCounts, groupedIdeas } = useMemo(() => {
    const groupedMap = new Map<string, SmartIdea[]>();
    const counts: Record<string, number> = {};
    for (const idea of ideas) {
      const cat = idea.category;
      if (!groupedMap.has(cat)) groupedMap.set(cat, []);
      groupedMap.get(cat)!.push(idea);
      counts[cat] = (counts[cat] || 0) + 1;
    }

    const cats = categoryOrder.filter((c) => (counts[c] || 0) > 0);

    let groups: { category: string; ideas: SmartIdea[] }[];
    if (activeCategory) {
      groups = [{ category: activeCategory, ideas: groupedMap.get(activeCategory) || [] }];
    } else {
      groups = cats.map((cat) => ({ category: cat, ideas: groupedMap.get(cat) || [] }));
    }

    return { categories: cats, categoryCounts: counts, groupedIdeas: groups };
  }, [ideas, categoryOrder, activeCategory]);

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
        <Button
          variant="primary"
          size="lg"
          onClick={handleGenerate}
          loading={loadingIdeas}
          icon={!loadingIdeas ? (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.8} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z" />
            </svg>
          ) : undefined}
        >
          {loadingIdeas ? "Generating..." : "Generate Ideas"}
        </Button>
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
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      )}

      {/* Category filter chips */}
      {ideas.length > 0 && categories.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => setActiveCategory(null)}
            className={`text-xs font-medium px-3 py-1.5 rounded-lg transition-colors ${
              activeCategory === null
                ? "bg-violet-600 text-white"
                : "bg-neutral-800 text-neutral-400 border border-neutral-700/60 hover:text-neutral-200 hover:border-neutral-600"
            }`}
          >
            All ({ideas.length})
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setActiveCategory(activeCategory === cat ? null : cat)}
              className={`text-xs font-medium px-3 py-1.5 rounded-lg transition-colors ${
                activeCategory === cat
                  ? "bg-violet-600 text-white"
                  : "bg-neutral-800 text-neutral-400 border border-neutral-700/60 hover:text-neutral-200 hover:border-neutral-600"
              }`}
            >
              {cat} ({categoryCounts[cat] || 0})
            </button>
          ))}
        </div>
      )}

      {/* Grouped smart idea cards */}
      {groupedIdeas.length > 0 && (
        <div className="space-y-6">
          {groupedIdeas.map((group) => (
            <div key={group.category} className="space-y-3">
              <h3 className="text-sm font-semibold text-neutral-300 tracking-wide">
                {group.category}
                <span className="ml-2 text-neutral-500 font-normal">
                  {group.ideas.length} idea{group.ideas.length !== 1 ? "s" : ""}
                </span>
              </h3>
              {group.ideas.map((idea, i) => (
                <SmartIdeaCard
                  key={`${idea.title}-${i}`}
                  idea={idea}
                  index={i}
                  onUseIdea={handleUseIdea}
                  onDismiss={handleDismiss}
                  onSaveToPostIt={handleSaveToPostIt}
                />
              ))}
            </div>
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
