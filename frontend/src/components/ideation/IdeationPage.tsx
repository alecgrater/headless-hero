import { useEffect, useRef, useState } from "react";
import api, { fetchGenerationEstimate, getFormats } from "../../api";
import type { GenerateIdeasResponse, VideoIdea } from "../../types/idea";
import type { VideoFormat } from "../../types/format";
import GenerationProgressBar from "../GenerationProgressBar";
import { FormatSelector } from "./FormatSelector";
import GeneratedIdeaCard from "./GeneratedIdeaCard";
import IdeationInput, { type IdeationInputHandle } from "./IdeationInput";

const FORMAT_KEY = "hh-selected-format";

interface Props {
  onUseIdea: (idea: VideoIdea, opts?: { eliEnabled?: boolean }) => void;
  initialNiche?: string | null;
  initialIdeas?: VideoIdea[] | null;
  autoGenerateNiche?: string | null;
  autoGenerateRequestId?: number;
}

const BATCH_SIZE = 5;

export default function IdeationPage({ onUseIdea, initialNiche, initialIdeas, autoGenerateNiche, autoGenerateRequestId }: Props) {
  const [ideas, setIdeas] = useState<VideoIdea[]>(initialIdeas ?? []);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastNiche, setLastNiche] = useState(initialNiche ?? "");
  const [lastGuide, setLastGuide] = useState("");
  const [estimatedSeconds, setEstimatedSeconds] = useState<number | null>(null);
  const [bookmarked, setBookmarked] = useState<Set<string>>(() => {
    try {
      const stored = localStorage.getItem("hh-bookmarked-ideas");
      return stored ? new Set(JSON.parse(stored) as string[]) : new Set();
    } catch {
      return new Set();
    }
  });
  const [formats, setFormats] = useState<VideoFormat[]>([]);
  const [selectedFormatId, setSelectedFormatId] = useState<string>(() => {
    try {
      return localStorage.getItem(FORMAT_KEY) || "youtube-listicle";
    } catch {
      return "youtube-listicle";
    }
  });
  const [animateFromIndex, setAnimateFromIndex] = useState(0);
  const [eliEnabled, setEliEnabled] = useState<boolean>(true);
  const inputRef = useRef<IdeationInputHandle>(null);
  const cancelledRef = useRef(false);
  const lastAutoGenerateRequestId = useRef<number | null>(null);

  useEffect(() => {
    getFormats().then(setFormats).catch(() => setFormats([]));
  }, []);

  useEffect(() => {
    (async () => {
      const res = await api.get("/api/settings/keys");
      if (res.ok) {
        const data = res.data as Record<string, { masked: string; configured: boolean; source: string }>;
        const raw = data.ELI_ENABLED_DEFAULT?.masked || "true";
        setEliEnabled(raw.trim().toLowerCase() !== "false");
      }
    })();
  }, []);

  useEffect(() => {
    try { localStorage.setItem(FORMAT_KEY, selectedFormatId); } catch { /* localStorage unavailable */ }
  }, [selectedFormatId]);

  useEffect(() => {
    if (!initialIdeas) return;
    cancelledRef.current = true;
    setLoading(false);
    setError(null);
    setAnimateFromIndex(0);
    setIdeas(initialIdeas);
    setLastNiche(initialNiche ?? "");
    setLastGuide("");
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
        format_id: selectedFormatId,
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
        setLastGuide(guide ?? "");
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
    generate(`${lastNiche} — more ideas similar to "${idea.title}"`, lastGuide || undefined);
  };

  const handleLoadMore = () => {
    generate(lastNiche, lastGuide || undefined, {
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

      {formats.length > 0 && (
        <FormatSelector
          formats={formats}
          selectedId={selectedFormatId}
          onSelect={setSelectedFormatId}
        />
      )}

      <div className="flex items-center gap-3 px-4 py-3 bg-neutral-900 rounded-lg border border-neutral-800">
        <span className="text-sm font-medium text-neutral-100">Eli host overlay</span>
        <button
          type="button"
          onClick={() => setEliEnabled(true)}
          className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
            eliEnabled ? "bg-violet-600 text-white" : "bg-neutral-800 text-neutral-400 hover:bg-neutral-700"
          }`}
        >
          Enabled
        </button>
        <button
          type="button"
          onClick={() => setEliEnabled(false)}
          className={`px-3 py-1.5 text-xs rounded-md transition-colors ${
            !eliEnabled ? "bg-violet-600 text-white" : "bg-neutral-800 text-neutral-400 hover:bg-neutral-700"
          }`}
        >
          Disabled
        </button>
        <span className="text-xs text-neutral-500 ml-2">
          {eliEnabled
            ? "Eli will be the recurring on-screen host."
            : "A topic-specific main character will appear in scene images instead."}
        </span>
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
              <GeneratedIdeaCard
                key={`${idea.title}-${i}`}
                idea={idea}
                index={i}
                bookmarked={bookmarked.has(idea.title)}
                onToggleBookmark={() => toggleBookmark(idea.title)}
                onMoreLikeThis={handleMoreLikeThis}
                onUseIdea={(idea) => onUseIdea({ ...idea, format_id: idea.format_id ?? selectedFormatId }, { eliEnabled })}
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

    </div>
  );
}
