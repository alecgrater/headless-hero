import { useCallback, useEffect, useRef, useState } from "react";
import api from "../../api";
import type {
  ExportAudioResponse,
  GenerateSEOResponse,
  GenerateThumbnailResponse,
  RenderEstimateResponse,
  RenderJobResponse,
  RenderStatusResponse,
  SEOMetadata,
  ThumbnailConcept,
} from "../../types/render";

interface RenderState {
  // YouTube render
  youtubeJobId: string | null;
  youtubeStatus: RenderStatusResponse | null;
  youtubeUrl: string | null;
  startYoutubeRender: () => Promise<void>;

  // Audio export
  audioUrl: string | null;
  audioExporting: boolean;
  exportAudio: () => Promise<void>;

  // Thumbnails
  thumbnails: ThumbnailConcept[];
  thumbnailsGenerating: boolean;
  recompositeThumbnail: () => Promise<void>;

  // SEO
  seoMetadata: SEOMetadata | null;
  seoGenerating: boolean;
  generateSEO: () => Promise<void>;

  // Render estimate
  estimatedSeconds: number | null;
  fetchEstimate: (sceneCount: number, totalAudioDuration: number) => Promise<void>;
}

export function useRenderState(scriptId: string, title: string, initialSeoMetadata?: SEOMetadata | null): RenderState {
  const [youtubeJobId, setYoutubeJobId] = useState<string | null>(null);
  const [youtubeStatus, setYoutubeStatus] = useState<RenderStatusResponse | null>(null);
  const [youtubeUrl, setYoutubeUrl] = useState<string | null>(null);

  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [audioExporting, setAudioExporting] = useState(false);

  const [thumbnails, setThumbnails] = useState<ThumbnailConcept[]>([]);
  const [thumbnailsGenerating, setThumbnailsGenerating] = useState(false);

  const [seoMetadata, setSeoMetadata] = useState<SEOMetadata | null>(initialSeoMetadata ?? null);
  const [seoGenerating, setSeoGenerating] = useState(false);

  const [estimatedSeconds, setEstimatedSeconds] = useState<number | null>(null);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Auto-load existing thumbnails on mount
  useEffect(() => {
    (async () => {
      try {
        const res = await api.get(`/api/thumbnail/${scriptId}`);
        if (res.ok) {
          const data = res.data as GenerateThumbnailResponse;
          if (data.concepts.length > 0) setThumbnails(data.concepts);
        }
      } catch {
        // ignore — thumbnails are optional
      }
    })();
  }, [scriptId]);

  // Polling for background jobs
  const pollJob = useCallback(
    (
      jobId: string,
      setStatus: (s: RenderStatusResponse) => void,
      onComplete: (urls: string[]) => void,
    ) => {
      if (pollRef.current) clearInterval(pollRef.current);

      let consecutiveFailures = 0;
      const MAX_POLL_FAILURES = 5;

      pollRef.current = setInterval(async () => {
        try {
          const res = await api.get(`/api/render/status/${jobId}`);
          if (!res.ok) {
            consecutiveFailures++;
            if (consecutiveFailures >= MAX_POLL_FAILURES) {
              if (pollRef.current) clearInterval(pollRef.current);
              pollRef.current = null;
              setStatus({
                job_id: jobId,
                status: "failed",
                progress: 0,
                current_step: "",
                output_urls: [],
                error: "Lost connection to the render job. The backend may have restarted.",
                estimated_seconds: undefined,
              });
            }
            return;
          }
          consecutiveFailures = 0;
          const status = res.data as RenderStatusResponse;
          setStatus(status);

          if (status.status === "completed" || status.status === "failed") {
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = null;
            if (status.status === "completed") {
              onComplete(status.output_urls);
            }
          }
        } catch {
          consecutiveFailures++;
          if (consecutiveFailures >= MAX_POLL_FAILURES) {
            if (pollRef.current) clearInterval(pollRef.current);
            pollRef.current = null;
            setStatus({
              job_id: jobId,
              status: "failed",
              progress: 0,
              current_step: "",
              output_urls: [],
              error: "Lost connection to the backend. Please check that it's running.",
              estimated_seconds: undefined,
            });
          }
        }
      }, 1000);
    },
    [],
  );

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const startYoutubeRender = useCallback(
    async () => {
      setYoutubeUrl(null);
      setYoutubeStatus(null);
      const res = await api.post("/api/render/full", {
        script_id: scriptId,
        title,
      });
      if (!res.ok) return;
      const { job_id } = res.data as RenderJobResponse;
      setYoutubeJobId(job_id);
      pollJob(job_id, setYoutubeStatus, (urls) => {
        if (urls.length > 0) setYoutubeUrl(urls[0]);
      });
    },
    [scriptId, title, pollJob],
  );

  const exportAudio = useCallback(async () => {
    setAudioExporting(true);
    try {
      const res = await api.post("/api/render/export-audio", {
        script_id: scriptId,
        title,
      });
      if (res.ok) {
        const data = res.data as ExportAudioResponse;
        setAudioUrl(data.audio_url);
      }
    } finally {
      setAudioExporting(false);
    }
  }, [scriptId, title]);

  const recompositeThumbnail = useCallback(
    async () => {
      setThumbnailsGenerating(true);
      try {
        const res = await api.post("/api/thumbnail/recomposite", {
          script_id: scriptId,
        });
        if (res.ok) {
          const data = res.data as GenerateThumbnailResponse;
          setThumbnails(data.concepts);
        }
      } finally {
        setThumbnailsGenerating(false);
      }
    },
    [scriptId],
  );

  const recompositeThumbnailWithoutEli = useCallback(
    async () => {
      setThumbnailsGenerating(true);
      try {
        const res = await api.post("/api/thumbnail/recomposite", {
          script_id: scriptId,
          include_eli: false,
        });
        if (res.ok) {
          const data = res.data as GenerateThumbnailResponse;
          setThumbnails(data.concepts);
        }
      } finally {
        setThumbnailsGenerating(false);
      }
    },
    [scriptId],
  );

  const generateSEO = useCallback(async () => {
    setSeoGenerating(true);
    try {
      const res = await api.post("/api/seo/generate", {
        script_id: scriptId,
      });
      if (res.ok) {
        const data = res.data as GenerateSEOResponse;
        setSeoMetadata(data.metadata);
      }
    } finally {
      setSeoGenerating(false);
    }
  }, [scriptId]);

  const fetchEstimate = useCallback(
    async (sceneCount: number, totalAudioDuration: number) => {
      try {
        const res = await api.get(
          `/api/render/estimate?scene_count=${sceneCount}&total_audio_duration=${totalAudioDuration}`,
        );
        if (res.ok) {
          const data = res.data as RenderEstimateResponse;
          setEstimatedSeconds(data.estimated_seconds);
        }
      } catch {
        // ignore — estimate is optional
      }
    },
    [],
  );

  return {
    youtubeJobId,
    youtubeStatus,
    youtubeUrl,
    startYoutubeRender,
    audioUrl,
    audioExporting,
    exportAudio,
    thumbnails,
    thumbnailsGenerating,
    recompositeThumbnail,
    recompositeThumbnailWithoutEli,
    seoMetadata,
    seoGenerating,
    generateSEO,
    estimatedSeconds,
    fetchEstimate,
  };
}
