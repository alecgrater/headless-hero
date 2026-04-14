import { useEffect, useRef, useState } from "react";
import api from "../../api";
import type { ScriptContent } from "../../types/script";

interface Params {
  scriptId: string | null;
  script: ScriptContent | null;
}

export interface TitleCardGenerationState {
  titleCardGenerating: boolean;
  titleCardGenerated: boolean;
  titleCardTimestamp: number;
  titleCardError: string | null;
  titleCardCompleted: number[];
  titleCardTotal: number;
  generateTitleCards: (force: boolean) => Promise<void>;
}

export default function useTitleCardGeneration({ scriptId, script }: Params): TitleCardGenerationState {
  const [titleCardGenerating, setTitleCardGenerating] = useState(false);
  const [titleCardGenerated, setTitleCardGenerated] = useState(false);
  const [titleCardTimestamp, setTitleCardTimestamp] = useState(0);
  const [titleCardError, setTitleCardError] = useState<string | null>(null);
  const [titleCardCompleted, setTitleCardCompleted] = useState<number[]>([]);
  const [titleCardTotal, setTitleCardTotal] = useState(0);

  const titleCardPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Cleanup poll interval on unmount
  useEffect(() => {
    return () => {
      if (titleCardPollRef.current) clearInterval(titleCardPollRef.current);
    };
  }, []);

  const generateTitleCards = async (force: boolean) => {
    if (!scriptId || !script) return;
    setTitleCardGenerating(true);
    setTitleCardError(null);
    setTitleCardCompleted([]);
    setTitleCardTotal(script.segments.length);

    try {
      const res = await api.post("/api/visuals/generate-title-cards", {
        script_id: scriptId,
        force,
      });
      if (!res.ok) {
        const err = res.data as { detail?: string };
        setTitleCardError(err.detail ?? "Failed to generate title cards");
        setTitleCardGenerating(false);
        return;
      }

      const { job_id } = res.data as { job_id: string };

      // Poll for progress — track consecutive failures to detect lost jobs
      let consecutiveFailures = 0;
      const MAX_POLL_FAILURES = 5;

      titleCardPollRef.current = setInterval(async () => {
        try {
          const statusRes = await api.get(`/api/visuals/title-cards-status/${job_id}`);
          if (!statusRes.ok) {
            consecutiveFailures++;
            if (consecutiveFailures >= MAX_POLL_FAILURES) {
              if (titleCardPollRef.current) clearInterval(titleCardPollRef.current);
              titleCardPollRef.current = null;
              setTitleCardGenerating(false);
              setTitleCardError("Lost connection to the generation job. The backend may have restarted. Please try again.");
            }
            return;
          }
          consecutiveFailures = 0;

          const job = statusRes.data as {
            status: string;
            current_step: string;
            error: string | null;
          };

          // Parse per-segment progress from current_step
          if (job.current_step) {
            try {
              const progress = JSON.parse(job.current_step) as {
                completed: number[];
                total: number;
                names: string[];
              };
              setTitleCardCompleted(progress.completed);
              setTitleCardTotal(progress.total);
            } catch {
              // current_step may be "Complete" or non-JSON
            }
          }

          if (job.status === "completed") {
            if (titleCardPollRef.current) clearInterval(titleCardPollRef.current);
            titleCardPollRef.current = null;
            setTitleCardGenerating(false);
            setTitleCardGenerated(true);
            setTitleCardTimestamp(Date.now());
          } else if (job.status === "failed") {
            if (titleCardPollRef.current) clearInterval(titleCardPollRef.current);
            titleCardPollRef.current = null;
            setTitleCardGenerating(false);
            setTitleCardError(job.error ?? "Title card generation failed");
          }
        } catch {
          consecutiveFailures++;
          if (consecutiveFailures >= MAX_POLL_FAILURES) {
            if (titleCardPollRef.current) clearInterval(titleCardPollRef.current);
            titleCardPollRef.current = null;
            setTitleCardGenerating(false);
            setTitleCardError("Lost connection to the backend. Please check that it's running and try again.");
          }
        }
      }, 1000);
    } catch {
      setTitleCardError("Could not reach the backend.");
      setTitleCardGenerating(false);
    }
  };

  return {
    titleCardGenerating,
    titleCardGenerated,
    titleCardTimestamp,
    titleCardError,
    titleCardCompleted,
    titleCardTotal,
    generateTitleCards,
  };
}
