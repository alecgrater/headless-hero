import { useEffect, useRef, useState } from "react";
import { getIdeaColdOpenStatus, selectIdeaColdOpen } from "../../api";
import type { Idea } from "../../types/idea";
import type { ColdOpenResult, ColdOpenVariant, HookScore } from "../../types/script";
import ColdOpenSelector from "../script/ColdOpenSelector";
import HookScoreCard from "../script/HookScoreCard";

interface Props {
  idea: Idea;
  onClose: () => void;
  onScored: (idea: Idea) => void;
}

type Phase = "select" | "scoring" | "done";

export default function ColdOpenModal({ idea, onClose, onScored }: Props) {
  const [phase, setPhase] = useState<Phase>("select");
  const [hookScore, setHookScore] = useState<HookScore | null>(null);
  const [refinedHook, setRefinedHook] = useState<{ intro_hook: string; opening_narration: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const coldOpenResult: ColdOpenResult | null = idea.cold_open_variants_json
    ? JSON.parse(idea.cold_open_variants_json)
    : null;

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const handleSelect = async (variant: ColdOpenVariant) => {
    const index = coldOpenResult?.variants.findIndex((v) => v.id === variant.id) ?? -1;
    if (index < 0) return;

    setPhase("scoring");
    setError(null);

    try {
      await selectIdeaColdOpen(idea.id, index);

      pollRef.current = setInterval(async () => {
        try {
          const status = await getIdeaColdOpenStatus(idea.id);
          const coldStatus = status.cold_open_status as string;

          if (coldStatus === "scored") {
            if (pollRef.current) clearInterval(pollRef.current);
            const score = status.hook_score_json
              ? JSON.parse(status.hook_score_json as string)
              : null;
            const refined = status.selected_hook_json
              ? JSON.parse(status.selected_hook_json as string)
              : null;
            setHookScore(score);
            setRefinedHook(refined);
            setPhase("done");

            const updatedIdea: Idea = {
              ...idea,
              cold_open_status: "scored",
              hook_score: (status.hook_score as number) ?? null,
              hook_score_json: (status.hook_score_json as string) ?? "",
              selected_hook_json: (status.selected_hook_json as string) ?? "",
            };
            onScored(updatedIdea);
          } else if (coldStatus === "failed") {
            if (pollRef.current) clearInterval(pollRef.current);
            const jobError = (status.job_error as string) || "Hook scoring failed";
            setError(jobError);
            setPhase("select");
          }
        } catch {
          if (pollRef.current) clearInterval(pollRef.current);
          setError("Failed to check scoring status");
          setPhase("select");
        }
      }, 2000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start hook scoring");
      setPhase("select");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-neutral-900 border border-neutral-700 rounded-xl shadow-2xl w-full max-w-4xl max-h-[85vh] overflow-y-auto p-6 space-y-5">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h2 className="text-lg font-semibold text-neutral-100">Pick a Cold Open</h2>
            <p className="text-sm text-neutral-400 mt-0.5 line-clamp-1">{idea.text}</p>
          </div>
          <button
            onClick={onClose}
            className="text-neutral-500 hover:text-neutral-300 transition-colors p-1"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Error */}
        {error && (
          <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
            {error}
          </div>
        )}

        {/* Phase: select */}
        {phase === "select" && coldOpenResult && (
          <ColdOpenSelector result={coldOpenResult} onSelect={handleSelect} />
        )}

        {/* Phase: scoring */}
        {phase === "scoring" && (
          <div className="space-y-4">
            <div className="flex items-center gap-3 py-8 justify-center">
              <div className="w-5 h-5 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
              <span className="text-sm text-neutral-400">Scoring & refining hook...</span>
            </div>
          </div>
        )}

        {/* Phase: done */}
        {phase === "done" && (
          <div className="space-y-5">
            {refinedHook && (
              <div className="rounded-lg border border-violet-500/30 bg-violet-500/5 p-4 space-y-3">
                <h4 className="text-xs font-medium uppercase tracking-wider text-violet-400">
                  Refined Hook
                </h4>
                <p className="text-sm text-neutral-100 italic leading-relaxed">
                  &ldquo;{refinedHook.intro_hook}&rdquo;
                </p>
                <p className="text-xs text-neutral-400 leading-relaxed">
                  {refinedHook.opening_narration}
                </p>
              </div>
            )}

            {hookScore && (
              <HookScoreCard
                hookScore={null}
                loading={false}
                error={null}
                onRescore={() => {}}
                score={hookScore}
              />
            )}

            <div className="flex justify-end">
              <button
                onClick={onClose}
                className="px-4 py-2 rounded-lg bg-violet-600 hover:bg-violet-500 text-white text-sm font-medium transition-colors"
              >
                Done
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
