import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  getContentProfile,
  refreshContentProfile,
  generateSmartIdeas,
  getSmartIdeasStatus,
  createIdea,
  refreshTrending,
  getTrendingRefreshStatus,
} from "../../api";
import { showToast } from "../ToastContainer";
import type { VideoIdea } from "../../types/idea";
import type { ContentProfile, SmartIdea, SmartIdeasResponse } from "../../types/trending";
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
  const [trendingAgeHours, setTrendingAgeHours] = useState<number | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const ideaPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    getContentProfile()
      .then((p) => setProfile(p))
      .catch(() => {})
      .finally(() => setLoadingProfile(false));
  }, []);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const startPolling = useCallback((jobId: string) => {
    setRefreshing(true);
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const status = await getTrendingRefreshStatus(jobId);
        if (!status) return;
        if (status.status === "completed" || status.status === "failed") {
          setRefreshing(false);
          if (status.status === "completed") {
            setTrendingAgeHours(0);
            showToast("Trending data refreshed", "success");
          }
          stopPolling();
        }
      } catch {
        setRefreshing(false);
        stopPolling();
        showToast("Refresh status check failed");
      }
    }, 3000);
  }, [stopPolling]);

  useEffect(() => () => stopPolling(), [stopPolling]);

  const stopIdeaPolling = useCallback(() => {
    if (ideaPollRef.current) {
      clearInterval(ideaPollRef.current);
      ideaPollRef.current = null;
    }
  }, []);

  useEffect(() => () => stopIdeaPolling(), [stopIdeaPolling]);

  const handleRefreshProfile = async () => {
    setLoadingProfile(true);
    setError(null);
    try {
      const p = await refreshContentProfile();
      setProfile(p);
      if (p.profile_input_upload.status === "uploaded" && p.seed_upload.status === "uploaded") {
        showToast("Content profile refreshed and remote discovery inputs uploaded", "success");
      } else if (p.profile_input_upload.status === "warning" || p.seed_upload.status === "warning") {
        const message = p.profile_input_upload.status === "warning"
          ? p.profile_input_upload.message
          : p.seed_upload.message;
        showToast(`Profile refreshed, but remote discovery upload failed: ${message}`, "error");
      } else {
        const message = p.profile_input_upload.message || p.seed_upload.message;
        showToast(`Content profile refreshed. ${message}`, "info");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to refresh profile");
    } finally {
      setLoadingProfile(false);
    }
  };

  const handleManualRefresh = async () => {
    try {
      const { job_id } = await refreshTrending();
      startPolling(job_id);
    } catch {
      showToast("Failed to start trending refresh");
    }
  };

  const handleGenerate = async () => {
    setLoadingIdeas(true);
    setError(null);
    stopIdeaPolling();
    try {
      const { job_id, refresh_triggered, refresh_job_id, trending_age_hours: age } = await generateSmartIdeas(40);
      if (age !== null) setTrendingAgeHours(age);
      if (refresh_triggered && refresh_job_id) {
        startPolling(refresh_job_id);
      }

      ideaPollRef.current = setInterval(async () => {
        try {
          const status = await getSmartIdeasStatus(job_id);
          if (!status) return;
          if (status.status === "completed" && status.output_data) {
            stopIdeaPolling();
            const result: SmartIdeasResponse = JSON.parse(status.output_data);
            setIdeas(result.ideas);
            setCategoryOrder(result.categories);
            setActiveCategory(null);
            if (result.trending_age_hours !== null) setTrendingAgeHours(result.trending_age_hours);
            setLoadingIdeas(false);
          } else if (status.status === "failed") {
            stopIdeaPolling();
            setError(status.error || "Idea generation failed");
            setLoadingIdeas(false);
          }
        } catch {
          stopIdeaPolling();
          setError("Lost connection while generating ideas");
          setLoadingIdeas(false);
        }
      }, 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate ideas");
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

  const handleSaveToIdea = async (idea: SmartIdea) => {
    try {
      await createIdea(idea.title, 70, "for_you", idea.description, idea.category);
      showToast("Saved to Ideas", "success");
    } catch {
      showToast("Failed to save to Ideas");
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
          <div className="flex items-center gap-2">
            <p className="text-neutral-400 text-sm">
              AI-powered video ideas from trending data and brainstorm strategies
            </p>
            {trendingAgeHours !== null && trendingAgeHours > 24 && !refreshing && (
              <button
                onClick={handleManualRefresh}
                className="inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-md bg-amber-500/15 text-amber-400 border border-amber-500/30 hover:bg-amber-500/25 transition-colors"
              >
                <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182" />
                </svg>
                {trendingAgeHours >= 48
                  ? `${Math.round(trendingAgeHours / 24)}d old`
                  : `${Math.round(trendingAgeHours)}h old`}
              </button>
            )}
          </div>
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

      {/* Background refresh banner */}
      {refreshing && (
        <div className="flex items-center gap-2 rounded-lg border border-sky-500/30 bg-sky-500/10 px-4 py-2.5 text-sm text-sky-300">
          <svg className="w-4 h-4 animate-spin shrink-0" fill="none" viewBox="0 0 24 24">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          Refreshing trending data in background — ideas based on cached data
        </div>
      )}

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
                  onSaveToIdea={handleSaveToIdea}
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
