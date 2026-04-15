import { useEffect, useRef, useState } from "react";
import api, { fetchGenerationEstimate } from "../../api";
import { DEFAULT_MODEL } from "../../constants";
import { usePollJob } from "../../hooks/usePollJob";
import type { VideoIdea } from "../../types/idea";
import type { ScriptContent } from "../../types/script";

// Mirrors backend config.ALLOWED_SEGMENT_COUNTS — keep in sync
const ALLOWED_SEGMENT_COUNTS = [8, 10] as const;

/** Snap an arbitrary segment count to the nearest allowed value (8 or 10). */
function snapSegmentCount(n: number): 8 | 10 {
  let best = ALLOWED_SEGMENT_COUNTS[0];
  for (const c of ALLOWED_SEGMENT_COUNTS) {
    if (Math.abs(c - n) < Math.abs(best - n)) best = c;
  }
  return best;
}

interface Params {
  brandId: string;
  idea: VideoIdea;
}

interface GenJobStatus {
  status: string;
  current_step: string;
  error: string | null;
  script_id?: string;
  elapsed_seconds?: number;
}

export interface ScriptGenerationState {
  script: ScriptContent | null;
  scriptId: string | null;
  loading: boolean;
  error: string | null;
  selectedModel: string;
  segmented: boolean;
  generationStarted: boolean;
  settingsLoaded: boolean;
  estimatedSeconds: number | null;
  elapsedSeconds: number | null;
  genSegments: { segment: number; total: number; name: string } | null;
  genCompletedSegments: number[];
  setScript: (s: ScriptContent) => void;
  handleGenerate: () => Promise<void>;
  handleCancelGeneration: () => void;
  handleModelChange: (value: string) => void;
  setSegmented: (v: boolean) => void;
}

export default function useScriptGeneration({ brandId, idea }: Params): ScriptGenerationState {
  const [script, setScript] = useState<ScriptContent | null>(null);
  const [scriptId, setScriptId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [selectedModel, setSelectedModel] = useState(DEFAULT_MODEL);
  const [segmented, setSegmented] = useState(true);
  const [generationStarted, setGenerationStarted] = useState(false);
  const [settingsLoaded, setSettingsLoaded] = useState(false);
  const [estimatedSeconds, setEstimatedSeconds] = useState<number | null>(null);

  const [genSegments, setGenSegments] = useState<{ segment: number; total: number; name: string } | null>(null);
  const [genCompletedSegments, setGenCompletedSegments] = useState<number[]>([]);
  const [elapsedSeconds, setElapsedSeconds] = useState<number | null>(null);

  const cancelledRef = useRef(false);

  const { startPolling, stopPolling } = usePollJob<GenJobStatus>({
    pollFn: async (jobId) => {
      if (cancelledRef.current) {
        stopPolling();
        return null;
      }
      const res = await api.get(`/api/scripts/generate-status/${jobId}`);
      if (!res.ok) return null;
      return res.data as GenJobStatus;
    },
    isComplete: (s) => s.status === "completed",
    isFailed: (s) => s.status === "failed",
    onStatus: async (job) => {
      if (job.elapsed_seconds != null) {
        setElapsedSeconds(job.elapsed_seconds);
      }

      // Parse per-segment progress
      if (job.current_step && job.current_step !== "Complete") {
        try {
          const progress = JSON.parse(job.current_step) as {
            segment: number;
            total: number;
            name: string;
          };
          setGenSegments(progress);
          setGenCompletedSegments(() => {
            const completed = [];
            for (let i = 1; i < progress.segment; i++) {
              completed.push(i);
            }
            return completed;
          });
        } catch {
          // current_step may not be JSON
        }
      }

      if (job.status === "completed" && job.script_id) {
        const fullRes = await api.get(`/api/scripts/${job.script_id}`);
        if (fullRes.ok) {
          const data = fullRes.data as { id: string; script: ScriptContent };
          setScript(data.script);
          setScriptId(data.id);
        }
        setLoading(false);
      } else if (job.status === "failed") {
        setError(job.error ?? "Script generation failed");
        setLoading(false);
      }
    },
    onConnectionLost: () => {
      setError(
        "Lost connection to the generation job. The backend may have restarted. Please try again.",
      );
      setLoading(false);
    },
    intervalMs: 1500,
  });

  // Load default model from settings
  useEffect(() => {
    api.get("/api/settings/keys").then((res) => {
      if (res.ok) {
        const data = res.data as Record<string, { masked: string }>;
        const saved = data?.SCRIPT_MODEL?.masked;
        if (saved) {
          setSelectedModel(saved);
          if (saved !== DEFAULT_MODEL) {
            setSegmented(true);
          }
        }
      }
      setSettingsLoaded(true);
    }).catch(() => setSettingsLoaded(true));
  }, []);

  const handleModelChange = (value: string) => {
    setSelectedModel(value);
    if (value !== DEFAULT_MODEL) {
      setSegmented(true);
    }
  };

  const handleGenerate = async () => {
    cancelledRef.current = false;
    setGenerationStarted(true);
    setLoading(true);
    setError(null);
    setGenSegments(null);
    setGenCompletedSegments([]);
    setElapsedSeconds(null);
    fetchGenerationEstimate("script_generation_youtube")
      .then((est) => setEstimatedSeconds(est.average_seconds))
      .catch(() => setEstimatedSeconds(null));

    try {
      const res = await api.post("/api/scripts/generate", {
        topic: idea.title,
        description: idea.description,
        brand_id: brandId,
        segment_count: idea.segments_est > 0 ? snapSegmentCount(idea.segments_est) : undefined,
        animated_scene_count: 5,
        model: selectedModel !== DEFAULT_MODEL ? selectedModel : undefined,
        segmented,
      });
      if (cancelledRef.current) return;
      if (!res.ok) {
        const detail =
          res.data && typeof res.data === "object" && "detail" in res.data
            ? (res.data as { detail: string }).detail
            : "Failed to start script generation";
        setError(detail);
        setLoading(false);
        return;
      }

      const { job_id } = res.data as { job_id: string };
      startPolling(job_id);
    } catch (err) {
      if (!cancelledRef.current) {
        console.error("[ScriptGeneration] Request failed:", err);
        setError("Could not reach the backend. Is it running?");
        setLoading(false);
      }
    }
  };

  const handleCancelGeneration = () => {
    cancelledRef.current = true;
    stopPolling();
    setLoading(false);
  };

  return {
    script,
    scriptId,
    loading,
    error,
    selectedModel,
    segmented,
    generationStarted,
    settingsLoaded,
    estimatedSeconds,
    elapsedSeconds,
    genSegments,
    genCompletedSegments,
    setScript,
    handleGenerate,
    handleCancelGeneration,
    handleModelChange,
    setSegmented,
  };
}
