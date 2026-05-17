import { useEffect, useRef, useState } from "react";
import api, { fetchGenerationEstimate } from "../../api";
import type { GenerateIdeasResponse, VideoIdea } from "../../types/idea";
import GenerationProgressBar from "../GenerationProgressBar";
import IdeaCard from "./IdeaCard";
import IdeationInput, { type IdeationInputHandle } from "./IdeationInput";

interface Props {
  onUseIdea: (idea: VideoIdea) => void;
  initialNiche?: string | null;
  initialIdeas?: VideoIdea[] | null;
  autoGenerateNiche?: string | null;
  autoGenerateRequestId?: number;
}

const BATCH_SIZE = 5;

const EXAMPLE_NICHES = [
  "deep sea creatures",
  "unsolved crimes",
  "retro gaming history",
  "psychology experiments",
  "space exploration",
  "ancient civilizations",
];

export default function IdeationPage({ onUseIdea, initialNiche, initialIdeas, autoGenerateNiche, autoGenerateRequestId }: Props) {
  const [ideas, setIdeas] = useState<VideoIdea[]>(initialIdeas ?? []);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastNiche, setLastNiche] = useState(initialNiche ?? "");
  const [estimatedSeconds, setEstimatedSeconds] = useState<number | null>(null);
  const [bookmarked, setBookmarked] = useState<Set<string>>(() => {
    try {
      const stored = localStorage.getItem("hh-bookmarked-ideas");
      return stored ? new Set(JSON.parse(stored) as string[]) : new Set();
    } catch {
      return new Set();
    }
  });
  const [animateFromIndex, setAnimateFromIndex] = useState(0);
  const inputRef = useRef<IdeationInputHandle>(null);
  const cancelledRef = useRef(false);
  const lastAutoGenerateRequestId = useRef<number | null>(null);

  useEffect(() => {
    if (!initialIdeas) return;
    cancelledRef.current = true;
    setLoading(false);
    setError(null);
    setAnimateFromIndex(0);
    setIdeas(initialIdeas);
    setLastNiche(initialNiche ?? "");
    if (initialNiche) inputRef.current?.setNiche(initialNiche);
  }, [initialIdeas, initialNiche]);

  useEffect(() => {
    if (
      autoGenerateNiche &&
      autoGenerateRequestId !== undefined &&
      autoGenerateRequestId !== lastAutoGenerateRequestId.current
    ) {
      lastAutoGenerateRequestId.current = autoGenerateRequestId;
      inputRef.current?.setNiche(autoGenerateNiche);
      generate(autoGenerateNiche);
    }
  }, [autoGenerateNiche, autoGenerateRequestId]); // eslint-disable-line react-hooks/exhaustive-deps

  const generate = async (
    niche: string,
    guide?: string,
    opts?: { append?: boolean; excludeTitles?: string[] },
  ) => {
    cancelledRef.current = false;
    setLoading(true);
    setError(null);
    fetchGenerationEstimate("idea_generation")
      .then((est) => setEstimatedSeconds(est.average_seconds))
      .catch(() => setEstimatedSeconds(null));
    try {
      const res = await api.post("/api/ideas/generate", {
        niche,
        guide,
        count: BATCH_SIZE,
        exclude_titles: opts?.excludeTitles ?? [],
      });
      if (cancelledRef.current) return;
      if (res.ok) {
        const data = res.data as GenerateIdeasResponse;
        if (opts?.append) {
          setAnimateFromIndex(ideas.length);
          setIdeas((prev) => [...prev, ...data.ideas]);
        } else {
          setAnimateFromIndex(0);
          setIdeas(data.ideas);
        }
        setLastNiche(niche);
      } else {
        const err = res.data as { detail?: string };
        setError(err.detail ?? "Failed to generate ideas");
      }
    } catch {
      if (!cancelledRef.current) {
        setError("Could not reach the backend. Is it running?");
      }
    } finally {
      setLoading(false);
    }
  };

  const handleCancel = () => {
    cancelledRef.current = true;
    setLoading(false);
  };

  const handleMoreLikeThis = (idea: VideoIdea) => {
    generate(`${lastNiche} — more ideas similar to "${idea.title}"`);
  };

  const handleLoadMore = () => {
    generate(lastNiche, undefined, {
      append: true,
      excludeTitles: ideas.map((i) => i.title),
    });
  };

  const toggleBookmark = (title: string) => {
    setBookmarked((prev) => {
      const next = new Set(prev);
      if (next.has(title)) next.delete(title);
      else next.add(title);
      localStorage.setItem("hh-bookmarked-ideas", JSON.stringify([...next]));
      return next;
    });
  };

  const handleChipClick = (niche: string) => {
    inputRef.current?.setNiche(niche);
  };

  return (
    <div className="space-y-6">
      {/* Inline keyframes for card animations */}
      <style>{`
        @keyframes fadeSlideUp {
          from { opacity: 0; transform: translateY(12px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      <div>
        <h2 className="text-2xl font-bold mb-1">Generate Video Ideas</h2>
        <p className="text-neutral-400 text-sm">
          Enter a niche to brainstorm video topics.
        </p>
      </div>

      <IdeationInput ref={inputRef} onGenerate={generate} onCancel={handleCancel} loading={loading} />

      {loading && (
        <div className="px-1">
          <GenerationProgressBar
            estimatedSeconds={estimatedSeconds}
            active={loading}
          />
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {ideas.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-lg font-semibold text-neutral-200">
            {ideas.length} Ideas
          </h3>

          <div className="grid gap-3">
            {ideas.map((idea, i) => (
              <IdeaCard
                key={`${idea.title}-${i}`}
                idea={idea}
                index={i}
                bookmarked={bookmarked.has(idea.title)}
                onToggleBookmark={() => toggleBookmark(idea.title)}
                onMoreLikeThis={handleMoreLikeThis}
                onUseIdea={onUseIdea}
                animationDelay={
                  i >= animateFromIndex
                    ? (i - animateFromIndex) * 80
                    : undefined
                }
              />
            ))}
          </div>

          {/* Load More button */}
          <div className="flex justify-center pt-2">
            <button
              onClick={handleLoadMore}
              disabled={loading}
              className="text-sm px-5 py-2.5 bg-neutral-800 border border-neutral-700 hover:border-neutral-600 hover:bg-neutral-700/50 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg font-medium transition-colors text-neutral-300"
            >
              Load 5 More
            </button>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!loading && ideas.length === 0 && !error && (
        <div className="text-center py-20 space-y-4">
          {/* Sparkles icon */}
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
                d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456zM16.894 20.567L16.5 21.75l-.394-1.183a2.25 2.25 0 00-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 001.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 001.423 1.423l1.183.394-1.183.394a2.25 2.25 0 00-1.423 1.423z"
              />
            </svg>
          </div>
          <p className="text-xl font-medium text-neutral-300">
            What should your next video be about?
          </p>
          <p className="text-sm text-neutral-500">
            Pick a niche to get started
          </p>
          <div className="flex flex-wrap justify-center gap-2 pt-1">
            {EXAMPLE_NICHES.map((niche) => (
              <button
                key={niche}
                onClick={() => handleChipClick(niche)}
                className="text-sm px-4 py-2 rounded-full bg-neutral-800 border border-neutral-700/60 text-neutral-400 hover:border-violet-500/50 hover:text-violet-400 hover:bg-violet-500/10 transition-colors"
              >
                {niche}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
