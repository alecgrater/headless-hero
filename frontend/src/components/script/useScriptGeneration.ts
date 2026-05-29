import { useEffect, useRef, useState } from "react";
import api, { fetchGenerationEstimate, refineHook } from "../../api";
import { DEFAULT_MODEL } from "../../constants";
import { useOperationProgress } from "../../hooks/useOperationProgress";
import { usePollJob } from "../../hooks/usePollJob";
import type { VideoIdea } from "../../types/idea";
import type { ColdOpenResult, ColdOpenVariant, RefinedHookResult, ScriptContent } from "../../types/script";

// Mirrors backend config.ALLOWED_SEGMENT_COUNTS — keep in sync
const ALLOWED_SEGMENT_COUNTS = [8, 10] as const;

/** Snap an arbitrary segment count to the nearest allowed value (8 or 10). */
function snapSegmentCount(n: number): 8 | 10 {
  let best: 8 | 10 = ALLOWED_SEGMENT_COUNTS[0];
  for (const c of ALLOWED_SEGMENT_COUNTS) {
    if (Math.abs(c - n) < Math.abs(best - n)) best = c;
  }
  return best;
}

interface Params {
  brandId: string;
  idea: VideoIdea;
  supportsColdOpen?: boolean;
  eliEnabled?: boolean;
  stylePresetEnabled?: boolean;
}

interface GenJobStatus {
  status: string;
  current_step: string;
  error: string | null;
  script_id?: string;
  elapsed_seconds?: number;
}

interface ColdOpenJobStatus {
  status: string;
  error: string | null;
  cold_open_result?: ColdOpenResult;
  elapsed_seconds?: number;
}

interface RefineJobStatus {
  status: string;
  current_step: string;
  error: string | null;
  refine_result?: RefinedHookResult;
  elapsed_seconds?: number;
}

export type GenerationPhase = "idle" | "cold_opens" | "selecting" | "refining" | "script";

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
  phase: GenerationPhase;
  coldOpenResult: ColdOpenResult | null;
  refineResult: RefinedHookResult | null;
  setScript: (s: ScriptContent) => void;
  handleGenerate: () => Promise<void>;
  handleCancelGeneration: () => void;
  handleModelChange: (value: string) => void;
  handleColdOpenSelect: (variant: ColdOpenVariant) => void;
  setSegmented: (v: boolean) => void;
  coldOpenProgress: { estimatedSeconds: number | null; active: boolean };
}

export default function useScriptGeneration({ brandId, idea, supportsColdOpen = true, eliEnabled = false, stylePresetEnabled = true }: Params): ScriptGenerationState {
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

  const [phase, setPhase] = useState<GenerationPhase>("idle");
  const [coldOpenResult, setColdOpenResult] = useState<ColdOpenResult | null>(null);
  const [selectedColdOpen, setSelectedColdOpen] = useState<ColdOpenVariant | null>(null);
  const [refineResult, setRefineResult] = useState<RefinedHookResult | null>(null);

  const cancelledRef = useRef(false);
  const coldOpenJobIdRef = useRef<string | null>(null);
  const coldOpenProgress = useOperationProgress("cold_open_generation");

  // --- Script generation polling ---
  const { startPolling: startScriptPolling, stopPolling: stopScriptPolling } = usePollJob<GenJobStatus>({
    pollFn: async (jobId) => {
      if (cancelledRef.current) {
        stopScriptPolling();
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
        setPhase("idle");
      } else if (job.status === "failed") {
        setError(job.error ?? "Script generation failed");
        setLoading(false);
        setPhase("idle");
      }
    },
    onConnectionLost: () => {
      setError(
        "Lost connection to the generation job. The backend may have restarted. Please try again.",
      );
      setLoading(false);
      setPhase("idle");
    },
    intervalMs: 1500,
  });

  // --- Cold open polling ---
  const { startPolling: startColdOpenPolling, stopPolling: stopColdOpenPolling } = usePollJob<ColdOpenJobStatus>({
    pollFn: async (jobId) => {
      if (cancelledRef.current) {
        stopColdOpenPolling();
        return null;
      }
      const res = await api.get(`/api/scripts/cold-opens-status/${jobId}`);
      if (!res.ok) return null;
      return res.data as ColdOpenJobStatus;
    },
    isComplete: (s) => s.status === "completed",
    isFailed: (s) => s.status === "failed",
    onStatus: (job) => {
      if (job.elapsed_seconds != null) {
        setElapsedSeconds(job.elapsed_seconds);
      }

      if (job.status === "completed" && job.cold_open_result) {
        coldOpenProgress.end();
        setColdOpenResult(job.cold_open_result);
        setPhase("selecting");
        setLoading(false);
      } else if (job.status === "failed") {
        coldOpenProgress.end();
        setError(job.error ?? "Cold open generation failed");
        setLoading(false);
        setPhase("idle");
      }
    },
    onConnectionLost: () => {
      coldOpenProgress.end();
      setError(
        "Lost connection to the cold open job. The backend may have restarted. Please try again.",
      );
      setLoading(false);
      setPhase("idle");
    },
    intervalMs: 1500,
  });

  // --- Refine-hook polling ---
  const { startPolling: startRefinePolling, stopPolling: stopRefinePolling } =
    usePollJob<RefineJobStatus>({
      pollFn: async (jobId) => {
        const res = await api.get(`/api/scripts/refine-hook-status/${jobId}`);
        return res.ok ? (res.data as RefineJobStatus) : null;
      },
      isComplete: (s) => s.status === "completed",
      isFailed: (s) => s.status === "failed",
      onStatus: (s) => {
        setElapsedSeconds(s.elapsed_seconds ?? null);
        if (s.status === "completed") {
          if (s.refine_result) {
            setRefineResult(s.refine_result);
            setLoading(false);
          } else {
            setError("Hook refinement completed without a result.");
            setLoading(false);
            setPhase("idle");
          }
        } else if (s.status === "failed") {
          setError(s.error || "Hook refinement failed");
          setLoading(false);
          setPhase("idle");
        }
      },
      onConnectionLost: () => {
        setError("Lost connection to backend during hook refinement.");
        setLoading(false);
        setPhase("idle");
      },
      intervalMs: 1500,
    });

  // Load default model from settings
  useEffect(() => {
    api.get("/api/settings/keys").then((res) => {
      if (res.ok) {
        const data = res.data as Record<string, { configured: boolean; masked: string }>;
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

  // Phase 1: Generate cold opens (or skip if cold_open_text already provided)
  const handleGenerate = async () => {
    cancelledRef.current = false;
    setGenerationStarted(true);
    setLoading(true);
    setError(null);
    setGenSegments(null);
    setGenCompletedSegments([]);
    setElapsedSeconds(null);
    setColdOpenResult(null);
    setSelectedColdOpen(null);

    // Skip cold opens if:
    //   - idea already has a pre-selected hook, OR
    //   - the active format does not support cold opens (e.g. life-as-a)
    if (idea.cold_open_text || !supportsColdOpen) {
      setPhase("script");

      fetchGenerationEstimate("script_generation_youtube")
        .then((est) => setEstimatedSeconds(est.average_seconds))
        .catch(() => setEstimatedSeconds(null));

      try {
        const res = await api.post("/api/scripts/generate", {
          topic: idea.title,
          description: idea.description,
          brand_id: brandId,
          format_id: idea.format_id ?? "youtube-listicle",
          segment_count:
            idea.segments_est > 0 ? snapSegmentCount(idea.segments_est) : undefined,
          animated_scene_count: 5,
          model: selectedModel !== DEFAULT_MODEL ? selectedModel : undefined,
          segmented,
          cold_open_text: idea.cold_open_text ?? null,
          eli_enabled: eliEnabled,
          style_preset_enabled: stylePresetEnabled,
        });
        if (cancelledRef.current) return;
        if (!res.ok) {
          const detail =
            res.data && typeof res.data === "object" && "detail" in res.data
              ? (res.data as { detail: string }).detail
              : "Failed to start script generation";
          setError(detail);
          setLoading(false);
          setPhase("idle");
          return;
        }
        const { job_id } = res.data as { job_id: string };
        startScriptPolling(job_id);
      } catch (err) {
        if (!cancelledRef.current) {
          console.error("[ScriptGeneration] Script request failed:", err);
          setError("Could not reach the backend. Is it running?");
          setLoading(false);
          setPhase("idle");
        }
      }
      return;
    }

    setPhase("cold_opens");
    coldOpenProgress.start();

    try {
      const res = await api.post("/api/scripts/cold-opens", {
        topic: idea.title,
        description: idea.description,
        brand_id: brandId,
        model: selectedModel !== DEFAULT_MODEL ? selectedModel : undefined,
        format_id: idea.format_id ?? "youtube-listicle",
      });
      if (cancelledRef.current) return;
      if (!res.ok) {
        const detail =
          res.data && typeof res.data === "object" && "detail" in res.data
            ? (res.data as { detail: string }).detail
            : "Failed to start cold open generation";
        setError(detail);
        setLoading(false);
        setPhase("idle");
        return;
      }

      const { job_id } = res.data as { job_id: string };
      coldOpenJobIdRef.current = job_id;
      startColdOpenPolling(job_id);
    } catch (err) {
      if (!cancelledRef.current) {
        console.error("[ScriptGeneration] Cold open request failed:", err);
        setError("Could not reach the backend. Is it running?");
        setLoading(false);
        setPhase("idle");
      }
    }
  };

  // Phase 2: User selected a cold open → refine the hook
  const handleColdOpenSelect = async (variant: ColdOpenVariant) => {
    cancelledRef.current = false;
    setSelectedColdOpen(variant);
    setLoading(true);
    setError(null);
    setRefineResult(null);
    setElapsedSeconds(null);
    setPhase("refining");

    const variantIndex = coldOpenResult
      ? coldOpenResult.variants.findIndex((v) => v.id === variant.id)
      : 0;

    try {
      if (!coldOpenJobIdRef.current) {
        setError("Cold open job ID missing — please regenerate.");
        setLoading(false);
        setPhase("idle");
        return;
      }
      const { job_id } = await refineHook({
        topic: idea.title,
        description: idea.description,
        cold_open_index: variantIndex,
        cold_open_job_id: coldOpenJobIdRef.current,
        format_id: idea.format_id ?? "youtube-listicle",
      });
      if (cancelledRef.current) return;
      startRefinePolling(job_id);
    } catch (err) {
      if (!cancelledRef.current) {
        console.error("[ScriptGeneration] Refine request failed:", err);
        setError("Could not reach the backend. Is it running?");
        setLoading(false);
        setPhase("idle");
      }
    }
  };

  // Phase 3: Auto-proceed from refining → script generation immediately
  useEffect(() => {
    if (phase !== "refining" || !refineResult || !selectedColdOpen) return;

    const refined = refineResult.refined_hook;
    const coldOpenText = `${refined.intro_hook}\n\n${refined.opening_narration}`;

    setPhase("script");
    setLoading(true);
    setElapsedSeconds(null);
    setGenSegments(null);
    setGenCompletedSegments([]);

    fetchGenerationEstimate("script_generation_youtube")
      .then((est) => setEstimatedSeconds(est.average_seconds))
      .catch(() => setEstimatedSeconds(null));

    api
      .post("/api/scripts/generate", {
        topic: idea.title,
        description: idea.description,
        brand_id: brandId,
        format_id: idea.format_id ?? "youtube-listicle",
        segment_count:
          idea.segments_est > 0 ? snapSegmentCount(idea.segments_est) : undefined,
        animated_scene_count: 5,
        model: selectedModel !== DEFAULT_MODEL ? selectedModel : undefined,
        segmented,
        cold_open_text: coldOpenText,
        eli_enabled: eliEnabled,
        style_preset_enabled: stylePresetEnabled,
      })
      .then((res) => {
        if (cancelledRef.current) return;
        if (!res.ok) {
          const detail =
            res.data && typeof res.data === "object" && "detail" in res.data
              ? (res.data as { detail: string }).detail
              : "Failed to start script generation";
          setError(detail);
          setLoading(false);
          setPhase("idle");
          return;
        }
        const { job_id } = res.data as { job_id: string };
        startScriptPolling(job_id);
      })
      .catch((err) => {
        if (!cancelledRef.current) {
          console.error("[ScriptGeneration] Script request failed:", err);
          setError("Could not reach the backend. Is it running?");
          setLoading(false);
          setPhase("idle");
        }
      });
    // Fire-once effect: triggers only when refineResult arrives during the refining phase.
    // Other deps (idea, brandId, selectedModel, segmented, startScriptPolling) are stable
    // for the lifetime of this phase and intentionally excluded to prevent re-triggering.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, refineResult, selectedColdOpen]);

  const handleCancelGeneration = () => {
    cancelledRef.current = true;
    stopScriptPolling();
    stopColdOpenPolling();
    stopRefinePolling();
    setRefineResult(null);
    setLoading(false);
    setPhase("idle");
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
    phase,
    coldOpenResult,
    refineResult,
    setScript,
    handleGenerate,
    handleCancelGeneration,
    handleModelChange,
    handleColdOpenSelect,
    setSegmented,
    coldOpenProgress: { estimatedSeconds: coldOpenProgress.estimatedSeconds, active: coldOpenProgress.active },
  };
}
