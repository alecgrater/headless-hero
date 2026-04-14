import { useCallback, useEffect, useRef, useState } from "react";
import {
  generateIdeasFromTopic,
  getTrendingRefreshStatus,
  getTrendingTopics,
  refreshTrending,
  updateTopicStatus,
} from "../../api";
import type { VideoIdea } from "../../types/idea";
import type { TrendingRefreshStatus, TrendingTopic } from "../../types/trending";
import TopicCard from "./TopicCard";

type SortKey = "score" | "newest" | "search_velocity" | "format_fit";

const SOURCE_FILTERS = [
  { key: "all", label: "All" },
  { key: "youtube", label: "YouTube" },
  { key: "google_trends", label: "Trends" },
  { key: "reddit", label: "Reddit" },
  { key: "news", label: "News" },
] as const;

const SORT_OPTIONS: { key: SortKey; label: string }[] = [
  { key: "score", label: "Score" },
  { key: "newest", label: "Newest" },
  { key: "search_velocity", label: "Search Velocity" },
  { key: "format_fit", label: "Format Fit" },
];

interface Props {
  onGenerateIdeas: (ideas: VideoIdea[], niche: string) => void;
}

function SourceStatusIndicator({ sources }: { sources: Record<string, string> }) {
  const entries = Object.entries(sources);
  return (
    <div className="flex items-center gap-3 text-xs">
      {entries.map(([name, status]) => (
        <div key={name} className="flex items-center gap-1.5">
          {status === "done" ? (
            <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
          ) : status === "running" ? (
            <svg className="w-3.5 h-3.5 text-violet-400 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
          ) : status === "failed" ? (
            <svg className="w-3.5 h-3.5 text-red-400" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          ) : (
            <span className="w-3.5 h-3.5 flex items-center justify-center">
              <span className="w-1.5 h-1.5 rounded-full bg-neutral-600" />
            </span>
          )}
          <span className={status === "failed" ? "text-red-400" : "text-neutral-400"}>
            {name === "google_trends" ? "Trends" : name.charAt(0).toUpperCase() + name.slice(1)}
          </span>
        </div>
      ))}
    </div>
  );
}

function SkeletonCard() {
  return (
    <div className="bg-neutral-800/50 border border-neutral-700/40 rounded-xl p-5 animate-pulse">
      <div className="flex gap-4">
        <div className="w-12 h-12 rounded-xl bg-neutral-700/50 shrink-0" />
        <div className="flex-1 space-y-3">
          <div className="h-4 bg-neutral-700/50 rounded w-3/4" />
          <div className="h-1.5 bg-neutral-700/50 rounded w-full" />
          <div className="flex gap-1.5">
            <div className="h-4 w-14 bg-neutral-700/50 rounded" />
            <div className="h-4 w-12 bg-neutral-700/50 rounded" />
          </div>
          <div className="h-3 bg-neutral-700/50 rounded w-5/6" />
        </div>
      </div>
    </div>
  );
}

export default function DiscoverPage({ onGenerateIdeas }: Props) {
  const [topics, setTopics] = useState<TrendingTopic[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshStatus, setRefreshStatus] = useState<TrendingRefreshStatus | null>(null);
  const [sourceFilter, setSourceFilter] = useState("all");
  const [sortKey, setSortKey] = useState<SortKey>("score");
  const [breakoutOnly, setBreakoutOnly] = useState(false);
  const [generatingTopicId, setGeneratingTopicId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load topics on mount
  useEffect(() => {
    getTrendingTopics("new").then(setTopics).catch(() => {});
  }, []);

  // Poll refresh status
  const startPolling = useCallback((jobId: string) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const status = await getTrendingRefreshStatus(jobId);
        if (!status) return;
        setRefreshStatus(status);
        if (status.status === "completed" || status.status === "failed") {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
          setLoading(false);
          if (status.status === "completed") {
            const newTopics = await getTrendingTopics("new");
            setTopics(newTopics);
          }
          if (status.status === "failed" && status.error) {
            setError(status.error);
          }
        }
      } catch {
        // Silently retry
      }
    }, 1500);
  }, []);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const handleRefresh = async () => {
    setLoading(true);
    setError(null);
    setRefreshStatus(null);
    try {
      const { job_id } = await refreshTrending();
      startPolling(job_id);
    } catch {
      setError("Failed to start refresh");
      setLoading(false);
    }
  };

  const handleGenerateIdeas = async (topic: TrendingTopic) => {
    setGeneratingTopicId(topic.id);
    try {
      const result = await generateIdeasFromTopic(topic.id);
      const ideas: VideoIdea[] = result.ideas.map((i) => ({
        title: i.title,
        segments_est: i.segments_est,
        description: i.description,
        keywords: i.keywords,
      }));
      onGenerateIdeas(ideas, result.niche);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to generate ideas");
    } finally {
      setGeneratingTopicId(null);
    }
  };

  const handleDismiss = async (topic: TrendingTopic) => {
    await updateTopicStatus(topic.id, "dismissed");
    setTopics((prev) => prev.filter((t) => t.id !== topic.id));
  };

  // Filter and sort
  const filtered = topics
    .filter((t) => {
      if (sourceFilter !== "all" && !t.source.includes(sourceFilter)) return false;
      if (breakoutOnly && !t.is_breakout) return false;
      return true;
    })
    .sort((a, b) => {
      switch (sortKey) {
        case "newest":
          return new Date(b.fetched_at).getTime() - new Date(a.fetched_at).getTime();
        case "search_velocity":
          return b.score_breakdown.search_velocity - a.score_breakdown.search_velocity;
        case "format_fit":
          return b.score_breakdown.format_fit - a.score_breakdown.format_fit;
        default:
          return b.score - a.score;
      }
    });

  const lastFetched = topics.length > 0 ? topics[0].fetched_at : null;
  const timeAgo = lastFetched
    ? (() => {
        const diff = Date.now() - new Date(lastFetched).getTime();
        const mins = Math.floor(diff / 60000);
        if (mins < 1) return "just now";
        if (mins < 60) return `${mins}m ago`;
        const hours = Math.floor(mins / 60);
        if (hours < 24) return `${hours}h ago`;
        return `${Math.floor(hours / 24)}d ago`;
      })()
    : null;

  // Failed sources warning
  const failedSources = refreshStatus?.sources
    ? Object.entries(refreshStatus.sources)
        .filter(([, s]) => s === "failed")
        .map(([name]) => name)
    : [];

  return (
    <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
      {/* Inline keyframes */}
      <style>{`
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-2xl font-bold mb-1">Discover Trending Topics</h2>
          <p className="text-neutral-400 text-sm">
            {timeAgo
              ? `Last updated ${timeAgo}`
              : "Find trending topics across YouTube, Reddit, Google Trends, and news"}
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={loading}
          className="flex items-center gap-2 text-sm px-4 py-2 rounded-lg font-medium bg-violet-600 hover:bg-violet-500 disabled:opacity-50 disabled:cursor-not-allowed text-white transition-colors"
        >
          <svg
            className={`w-4 h-4 ${loading ? "animate-spin" : ""}`}
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0l3.181 3.183a8.25 8.25 0 0013.803-3.7M4.031 9.865a8.25 8.25 0 0113.803-3.7l3.181 3.182"
            />
          </svg>
          Refresh
        </button>
      </div>

      {/* Refresh progress */}
      {loading && refreshStatus && (
        <div className="rounded-lg border border-neutral-700/60 bg-neutral-800/50 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-neutral-200">Fetching trending data...</span>
            <span className="text-xs text-neutral-500 tabular-nums">
              {Math.round(refreshStatus.progress * 100)}%
            </span>
          </div>
          <div className="h-1 rounded-full bg-neutral-700/50 overflow-hidden">
            <div
              className="h-full bg-violet-500 rounded-full transition-all duration-500"
              style={{ width: `${refreshStatus.progress * 100}%` }}
            />
          </div>
          {refreshStatus.sources && <SourceStatusIndicator sources={refreshStatus.sources} />}
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {/* Failed sources warning */}
      {!loading && failedSources.length > 0 && topics.length > 0 && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-300">
          Some sources failed: {failedSources.join(", ")}. Results may be incomplete.
        </div>
      )}

      {/* Filter/sort bar */}
      {(topics.length > 0 || loading) && (
        <div className="flex items-center justify-between gap-4 flex-wrap">
          {/* Source filter chips */}
          <div className="flex items-center gap-1.5">
            {SOURCE_FILTERS.map((f) => (
              <button
                key={f.key}
                onClick={() => setSourceFilter(f.key)}
                className={`text-xs px-3 py-1.5 rounded-lg font-medium transition-colors ${
                  sourceFilter === f.key
                    ? "bg-violet-600/20 text-violet-400 border border-violet-500/30"
                    : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 border border-transparent"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          <div className="flex items-center gap-3">
            {/* Breakout toggle */}
            <label className="flex items-center gap-1.5 text-xs text-neutral-400 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={breakoutOnly}
                onChange={(e) => setBreakoutOnly(e.target.checked)}
                className="rounded border-neutral-600 bg-neutral-800 text-violet-500 focus:ring-violet-500/30 focus:ring-offset-0 w-3.5 h-3.5"
              />
              Breakout only
            </label>

            {/* Sort dropdown */}
            <select
              value={sortKey}
              onChange={(e) => setSortKey(e.target.value as SortKey)}
              className="text-xs px-2 py-1.5 rounded-lg bg-neutral-800 border border-neutral-700 text-neutral-300 focus:outline-none focus:border-violet-500/50"
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.key} value={opt.key}>
                  Sort: {opt.label}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      {/* Loading skeletons */}
      {loading && topics.length === 0 && (
        <div className="space-y-3">
          {[0, 1, 2, 3].map((i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      )}

      {/* Topic cards */}
      {filtered.length > 0 && (
        <div className="space-y-3">
          <p className="text-xs text-neutral-500">
            {filtered.length} topic{filtered.length !== 1 ? "s" : ""}
            {sourceFilter !== "all" ? ` from ${SOURCE_FILTERS.find((f) => f.key === sourceFilter)?.label}` : ""}
            {breakoutOnly ? " (breakout)" : ""}
          </p>
          {filtered.map((topic, i) => (
            <TopicCard
              key={topic.id}
              topic={topic}
              index={i}
              onGenerateIdeas={handleGenerateIdeas}
              onDismiss={handleDismiss}
              loading={generatingTopicId === topic.id}
            />
          ))}
        </div>
      )}

      {/* Empty state */}
      {!loading && topics.length === 0 && !error && (
        <div className="text-center py-20 space-y-4">
          <div className="flex justify-center">
            <svg
              className="w-12 h-12 text-violet-500/40"
              fill="none"
              stroke="currentColor"
              strokeWidth={1.2}
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 21a9.004 9.004 0 008.716-6.747M12 21a9.004 9.004 0 01-8.716-6.747M12 21c2.485 0 4.5-4.03 4.5-9S14.485 3 12 3m0 18c-2.485 0-4.5-4.03-4.5-9S9.515 3 12 3m0 0a8.997 8.997 0 017.843 4.582M12 3a8.997 8.997 0 00-7.843 4.582m15.686 0A11.953 11.953 0 0112 10.5c-2.998 0-5.74-1.1-7.843-2.918m15.686 0A8.959 8.959 0 0121 12c0 .778-.099 1.533-.284 2.253m0 0A17.919 17.919 0 0112 16.5c-3.162 0-6.133-.815-8.716-2.247m0 0A9.015 9.015 0 013 12c0-1.605.42-3.113 1.157-4.418"
              />
            </svg>
          </div>
          <p className="text-xl font-medium text-neutral-300">
            Discover what&apos;s trending
          </p>
          <p className="text-sm text-neutral-500">
            Hit Refresh to scan YouTube, Reddit, Google Trends, and news for hot topics
          </p>
          <button
            onClick={handleRefresh}
            className="mt-2 text-sm px-5 py-2.5 rounded-lg font-medium bg-violet-600 hover:bg-violet-500 text-white transition-colors"
          >
            Refresh Now
          </button>
        </div>
      )}

      {/* No results after filter */}
      {!loading && topics.length > 0 && filtered.length === 0 && (
        <div className="text-center py-12">
          <p className="text-neutral-400">No topics match your filters</p>
          <button
            onClick={() => {
              setSourceFilter("all");
              setBreakoutOnly(false);
            }}
            className="mt-2 text-sm text-violet-400 hover:text-violet-300 transition-colors"
          >
            Clear filters
          </button>
        </div>
      )}
    </div>
  );
}
