import { useEffect, useRef, useState } from "react";
import api, { fetchGenerationEstimate } from "../../api";
import type { VideoIdea } from "../../types/idea";
import type { ScriptContent } from "../../types/script";

const DEFAULT_MODEL = "anthropic.claude-opus-4-6-v1";
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

  const cancelledRef = useRef(false);
  const genPollRef = useRef<ReturnType<typeof setInterval> | null>(null);

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

  // Cleanup poll interval on unmount
  useEffect(() => {
    return () => {
      if (genPollRef.current) clearInterval(genPollRef.current);
    };
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

      // Poll for progress
      genPollRef.current = setInterval(async () => {
        if (cancelledRef.current) {
          if (genPollRef.current) clearInterval(genPollRef.current);
          genPollRef.current = null;
          return;
        }
        try {
          const statusRes = await api.get(`/api/scripts/generate-status/${job_id}`);
          if (!statusRes.ok) return;

          const job = statusRes.data as {
            status: string;
            current_step: string;
            error: string | null;
            script_id?: string;
          };

          // Parse per-segment progress
          if (job.current_step && job.current_step !== "Complete") {
            try {
              const progress = JSON.parse(job.current_step) as {
                segment: number;
                total: number;
                name: string;
              };
              setGenSegments(progress);
              setGenCompletedSegments((_prev) => {
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

          if (job.status === "completed") {
            if (genPollRef.current) clearInterval(genPollRef.current);
            genPollRef.current = null;

            if (job.script_id) {
              const fullRes = await api.get(`/api/scripts/${job.script_id}`);
              if (fullRes.ok) {
                const data = fullRes.data as { id: string; script: ScriptContent };
                setScript(data.script);
                setScriptId(data.id);
              }
            }
            setLoading(false);
          } else if (job.status === "failed") {
            if (genPollRef.current) clearInterval(genPollRef.current);
            genPollRef.current = null;
            setError(job.error ?? "Script generation failed");
            setLoading(false);
          }
        } catch {
          // Network error during poll — ignore, will retry
        }
      }, 1500);
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
    if (genPollRef.current) clearInterval(genPollRef.current);
    genPollRef.current = null;
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
    genSegments,
    genCompletedSegments,
    setScript,
    handleGenerate,
    handleCancelGeneration,
    handleModelChange,
    setSegmented,
  };
}
