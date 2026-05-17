import { useCallback, useEffect, useState } from "react";
import api, {
  exportShortFormThumbnails,
  getRenderedShortsStatus,
  pollRenderJob,
  pollShortFormJob,
  renderShortAll,
} from "../../api";
import { usePollJob } from "../../hooks/usePollJob";
import { useOperationProgress } from "../../hooks/useOperationProgress";
import type {
  ExportAudioResponse,
  ExportBundleResponse,
  GenerateSEOResponse,
  GenerateShortFormSEOResponse,
  GenerateThumbnailResponse,
  RenderEstimateResponse,
  RenderJobResponse,
  RenderStatusResponse,
  SEOMetadata,
  ShortFormSEOMetadata,
  ThumbnailConcept,
} from "../../types/render";

interface RenderState {
  // YouTube render
  youtubeJobId: string | null;
  youtubeStatus: RenderStatusResponse | null;
  youtubeUrl: string | null;
  startYoutubeRender: (speed?: number) => Promise<string | null>;

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
  shortFormSeoMetadata: ShortFormSEOMetadata | null;
  shortFormSeoGenerating: boolean;
  generateShortFormSEO: () => Promise<void>;

  // Render estimate
  estimatedSeconds: number | null;
  fetchEstimate: (sceneCount: number, totalAudioDuration: number) => Promise<void>;

  // Export bundle
  exportBundleLoading: boolean;
  exportBundleResult: ExportBundleResponse | null;
  exportBundle: () => Promise<void>;

  // Smart export
  exportPhase: "rendering" | "exporting" | null;
  smartExportBundle: (onComplete?: (result: ExportBundleResponse) => void) => Promise<void>;
  yoloRender: (onComplete?: (result: ExportBundleResponse) => void) => Promise<void>;

  // Operation progress
  thumbnailProgress: { estimatedSeconds: number | null; active: boolean };
  seoProgress: { estimatedSeconds: number | null; active: boolean };
  shortFormSeoProgress: { estimatedSeconds: number | null; active: boolean };
  audioExportProgress: { estimatedSeconds: number | null; active: boolean };
  exportBundleProgress: { estimatedSeconds: number | null; active: boolean };
}

export function useRenderState(
  scriptId: string,
  title: string,
  initialSeoMetadata?: SEOMetadata | null,
  initialShortFormSeoMetadata?: ShortFormSEOMetadata | null,
): RenderState {
  const [youtubeJobId, setYoutubeJobId] = useState<string | null>(null);
  const [youtubeStatus, setYoutubeStatus] = useState<RenderStatusResponse | null>(null);
  const [youtubeUrl, setYoutubeUrl] = useState<string | null>(null);

  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [audioExporting, setAudioExporting] = useState(false);

  const [thumbnails, setThumbnails] = useState<ThumbnailConcept[]>([]);
  const [thumbnailsGenerating, setThumbnailsGenerating] = useState(false);

  const [seoMetadata, setSeoMetadata] = useState<SEOMetadata | null>(initialSeoMetadata ?? null);
  const [seoGenerating, setSeoGenerating] = useState(false);
  const [shortFormSeoMetadata, setShortFormSeoMetadata] = useState<ShortFormSEOMetadata | null>(initialShortFormSeoMetadata ?? null);
  const [shortFormSeoGenerating, setShortFormSeoGenerating] = useState(false);

  const [estimatedSeconds, setEstimatedSeconds] = useState<number | null>(null);

  const [exportBundleLoading, setExportBundleLoading] = useState(false);
  const [exportBundleResult, setExportBundleResult] = useState<ExportBundleResponse | null>(null);

  const [exportPhase, setExportPhase] = useState<"rendering" | "exporting" | null>(null);

  const thumbnailProgressHook = useOperationProgress("thumbnail_generation");
  const seoProgressHook = useOperationProgress("seo_generation");
  const shortFormSeoProgressHook = useOperationProgress("short_form_seo_generation");
  const audioExportProgressHook = useOperationProgress("audio_export");
  const exportBundleProgressHook = useOperationProgress("export_bundle");

  const { startPolling } = usePollJob<RenderStatusResponse>({
    pollFn: async (jobId) => {
      const res = await api.get(`/api/render/status/${jobId}`);
      if (!res.ok) return null;
      return res.data as RenderStatusResponse;
    },
    isComplete: (s) => s.status === "completed",
    isFailed: (s) => s.status === "failed",
    onStatus: (status) => {
      setYoutubeStatus(status);
      if (status.status === "completed" && status.output_urls.length > 0) {
        setYoutubeUrl(status.output_urls[0]);
      }
    },
    onConnectionLost: () => {
      setYoutubeStatus({
        job_id: youtubeJobId ?? "",
        status: "failed",
        progress: 0,
        current_step: "",
        output_urls: [],
        error: "Lost connection to the render job. The backend may have restarted.",
        estimated_seconds: undefined,
      });
    },
  });

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
  }, [scriptId, exportBundleProgressHook]);

  const startYoutubeRender = useCallback(
    async (speed?: number): Promise<string | null> => {
      setYoutubeUrl(null);
      setYoutubeStatus(null);
      const res = await api.post("/api/render/full", {
        script_id: scriptId,
        title,
        ...(speed != null && speed !== 1.0 ? { speed } : {}),
      });
      if (!res.ok) return null;
      const { job_id } = res.data as RenderJobResponse;
      setYoutubeJobId(job_id);
      startPolling(job_id);
      return job_id;
    },
    [scriptId, title, startPolling],
  );

  const exportAudio = useCallback(async () => {
    setAudioExporting(true);
    audioExportProgressHook.start();
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
      audioExportProgressHook.end();
    }
  }, [scriptId, title]);

  const recompositeThumbnail = useCallback(
    async () => {
      setThumbnailsGenerating(true);
      thumbnailProgressHook.start();
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
        thumbnailProgressHook.end();
      }
    },
    [scriptId],
  );

  const generateSEO = useCallback(async () => {
    setSeoGenerating(true);
    seoProgressHook.start();
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
      seoProgressHook.end();
    }
  }, [scriptId]);

  const generateShortFormSEO = useCallback(async () => {
    setShortFormSeoGenerating(true);
    shortFormSeoProgressHook.start();
    try {
      const res = await api.post("/api/seo/generate-shorts", {
        script_id: scriptId,
      });
      if (res.ok) {
        const data = res.data as GenerateShortFormSEOResponse;
        setShortFormSeoMetadata(data.metadata);
      }
    } finally {
      setShortFormSeoGenerating(false);
      shortFormSeoProgressHook.end();
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

  const exportBundle = useCallback(async () => {
    setExportBundleLoading(true);
    setExportBundleResult(null);
    exportBundleProgressHook.start();
    try {
      const res = await api.post("/api/render/export-bundle", {
        script_id: scriptId,
      });
      if (res.ok) {
        setExportBundleResult(res.data as ExportBundleResponse);
      }
    } finally {
      setExportBundleLoading(false);
      exportBundleProgressHook.end();
    }
  }, [scriptId]);

  const smartExportBundle = useCallback(
    async (onComplete?: (result: ExportBundleResponse) => void) => {
      if (exportPhase) return;
      setExportPhase("rendering");
      try {
        // Step 1: render video if not already rendered
        if (!youtubeUrl) {
          const jobId = await startYoutubeRender();
          if (!jobId) return;
          // pollRenderJob awaits completion while usePollJob updates UI in parallel
          await pollRenderJob(jobId);
        }

        // Step 2: export bundle to the configured export folder
        setExportPhase("exporting");
        setExportBundleLoading(true);
        setExportBundleResult(null);
        exportBundleProgressHook.start();
        const res = await api.post("/api/render/export-bundle", {
          script_id: scriptId,
        });
        if (res.ok) {
          const result = res.data as ExportBundleResponse;
          setExportBundleResult(result);
          onComplete?.(result);
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Export failed";
        setExportBundleResult(null);
        throw new Error(msg);
      } finally {
        setExportBundleLoading(false);
        exportBundleProgressHook.end();
        setExportPhase(null);
      }
    },
    [scriptId, youtubeUrl, startYoutubeRender, exportPhase, exportBundleProgressHook],
  );

  const yoloRender = useCallback(
    async (onComplete?: (result: ExportBundleResponse) => void) => {
      if (exportPhase) return;
      setExportBundleResult(null);
      try {
        setExportPhase("rendering");
        if (!youtubeUrl) {
          const jobId = await startYoutubeRender();
          if (!jobId) return;
          await pollRenderJob(jobId);
        }

        setExportPhase("exporting");
        setExportBundleLoading(true);
        exportBundleProgressHook.start();
        const scriptRes = await api.get(`/api/scripts/${scriptId}`);
        const content = scriptRes.ok
          ? (scriptRes.data as { script?: { segments?: unknown[] } }).script
          : null;
        const segmentCount = content?.segments?.length ?? 0;
        const rendered = await getRenderedShortsStatus(scriptId);
        if (segmentCount > 0 && rendered.rendered_indices.length < segmentCount) {
          const { job_id } = await renderShortAll(scriptId);
          await pollShortFormJob(job_id);
        }

        await exportShortFormThumbnails(scriptId);

        const res = await api.post("/api/render/export-bundle", {
          script_id: scriptId,
        });
        if (res.ok) {
          const result = res.data as ExportBundleResponse;
          setExportBundleResult(result);
          onComplete?.(result);
        }
      } catch (err) {
        const msg = err instanceof Error ? err.message : "YOLO render failed";
        setExportBundleResult(null);
        throw new Error(msg);
      } finally {
        setExportBundleLoading(false);
        exportBundleProgressHook.end();
        setExportPhase(null);
      }
    },
    [scriptId, youtubeUrl, startYoutubeRender, exportPhase, exportBundleProgressHook],
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
    seoMetadata,
    seoGenerating,
    generateSEO,
    shortFormSeoMetadata,
    shortFormSeoGenerating,
    generateShortFormSEO,
    estimatedSeconds,
    fetchEstimate,
    exportBundleLoading,
    exportBundleResult,
    exportBundle,
    exportPhase,
    smartExportBundle,
    yoloRender,
    thumbnailProgress: { estimatedSeconds: thumbnailProgressHook.estimatedSeconds, active: thumbnailProgressHook.active },
    seoProgress: { estimatedSeconds: seoProgressHook.estimatedSeconds, active: seoProgressHook.active },
    shortFormSeoProgress: { estimatedSeconds: shortFormSeoProgressHook.estimatedSeconds, active: shortFormSeoProgressHook.active },
    audioExportProgress: { estimatedSeconds: audioExportProgressHook.estimatedSeconds, active: audioExportProgressHook.active },
    exportBundleProgress: { estimatedSeconds: exportBundleProgressHook.estimatedSeconds, active: exportBundleProgressHook.active },
  };
}
