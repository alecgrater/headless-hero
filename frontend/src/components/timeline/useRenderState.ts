import { useCallback, useEffect, useState } from "react";
import api, {
  exportShortFormThumbnails,
  getRenderedLongformStatus,
  getRenderedShortsStatus,
  pollRenderJob,
  pollShortFormJob,
  renderShortAll,
  renderShortBatch,
} from "../../api";
import { usePollJob } from "../../hooks/usePollJob";
import { useOperationProgress } from "../../hooks/useOperationProgress";
import type {
  ExportBundleResponse,
  ExportProgressStatus,
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
  exportStatus: ExportProgressStatus | null;
  smartExportBundle: (onComplete?: (result: ExportBundleResponse) => void) => Promise<void>;
  yoloRender: (onComplete?: (result: ExportBundleResponse) => void) => Promise<void>;

  // Operation progress
  thumbnailProgress: { estimatedSeconds: number | null; active: boolean };
  seoProgress: { estimatedSeconds: number | null; active: boolean };
  shortFormSeoProgress: { estimatedSeconds: number | null; active: boolean };
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
  const [exportStatus, setExportStatus] = useState<ExportProgressStatus | null>(null);

  const thumbnailProgressHook = useOperationProgress("thumbnail_generation");
  const seoProgressHook = useOperationProgress("seo_generation");
  const shortFormSeoProgressHook = useOperationProgress("short_form_seo_generation");
  const {
    estimatedSeconds: exportBundleEstimatedSeconds,
    active: exportBundleActive,
    start: startExportBundleProgress,
    end: endExportBundleProgress,
  } = useOperationProgress("export_bundle");

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
  }, [scriptId]);

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
    startExportBundleProgress();
    try {
      const res = await api.post("/api/render/export-bundle", {
        script_id: scriptId,
      });
      if (res.ok) {
        setExportBundleResult(res.data as ExportBundleResponse);
      }
    } finally {
      setExportBundleLoading(false);
      endExportBundleProgress();
    }
  }, [scriptId, startExportBundleProgress, endExportBundleProgress]);

  const ensureLongformRendered = useCallback(
    async (renderingLabel: string): Promise<boolean> => {
      if (youtubeUrl) return true;

      const rendered = await getRenderedLongformStatus(scriptId);
      if (rendered.rendered) {
        if (rendered.url) setYoutubeUrl(rendered.url);
        return true;
      }

      setExportStatus({ label: renderingLabel, progress: 0 });
      const jobId = await startYoutubeRender();
      if (!jobId) return false;
      await pollRenderJob(jobId);
      return true;
    },
    [scriptId, youtubeUrl, startYoutubeRender],
  );

  const smartExportBundle = useCallback(
    async (onComplete?: (result: ExportBundleResponse) => void) => {
      if (exportPhase) return;
      setExportPhase("rendering");
      setExportStatus({ label: "Checking long-form video export...", progress: 0 });
      try {
        const longformReady = await ensureLongformRendered("Rendering long-form YouTube video...");
        if (!longformReady) return;

        // Step 2: export bundle to the configured export folder
        setExportPhase("exporting");
        setExportStatus({ label: "Copying long-form video, thumbnail, and SEO files...", progress: 0.55 });
        setExportBundleLoading(true);
        setExportBundleResult(null);
        startExportBundleProgress();
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
        endExportBundleProgress();
        setExportPhase(null);
        setExportStatus(null);
      }
    },
    [scriptId, ensureLongformRendered, exportPhase, startExportBundleProgress, endExportBundleProgress],
  );

  const yoloRender = useCallback(
    async (onComplete?: (result: ExportBundleResponse) => void) => {
      if (exportPhase) return;
      setExportBundleResult(null);
      setExportStatus(null);
      try {
        setExportPhase("rendering");
        setExportStatus({ label: "Checking long-form video export...", progress: 0 });
        const longformReady = await ensureLongformRendered("Rendering long-form YouTube video...");
        if (!longformReady) return;

        setExportPhase("exporting");
        setExportBundleLoading(true);
        startExportBundleProgress();
        setExportStatus({ label: "Checking which short-form videos already exist...", progress: 0.02 });
        const scriptRes = await api.get(`/api/scripts/${scriptId}`);
        const content = scriptRes.ok
          ? (scriptRes.data as { script?: { segments?: unknown[] } }).script
          : null;
        const segmentCount = content?.segments?.length ?? 0;
        const rendered = await getRenderedShortsStatus(scriptId);
        if (segmentCount > 0 && rendered.rendered_indices.length < segmentCount) {
          const renderedSet = new Set(rendered.rendered_indices);
          const missingIndices = Array.from({ length: segmentCount }, (_, idx) => idx).filter(
            (idx) => !renderedSet.has(idx),
          );
          const missingCount = missingIndices.length;
          setExportStatus({
            label: `Rendering ${missingCount} missing short-form video${missingCount === 1 ? "" : "s"}...`,
            progress: 0.05,
          });
          const { job_id } = missingCount === segmentCount
            ? await renderShortAll(scriptId)
            : await renderShortBatch(scriptId, missingIndices);
          await pollShortFormJob(job_id, (status) => {
            setExportStatus({
              label: status.current_step || "Rendering short-form videos...",
              progress: 0.05 + (status.progress ?? 0) * 0.65,
            });
          });
        } else if (segmentCount > 0) {
          setExportStatus({ label: `All ${segmentCount} short-form videos already rendered.`, progress: 0.7 });
        }

        setExportStatus({ label: "Generating and exporting short-form thumbnails...", progress: 0.75 });
        await exportShortFormThumbnails(scriptId);

        setExportStatus({ label: "Building final export bundle with video, thumbnails, and SEO...", progress: 0.88 });
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
        endExportBundleProgress();
        setExportPhase(null);
        setExportStatus(null);
      }
    },
    [scriptId, ensureLongformRendered, exportPhase, startExportBundleProgress, endExportBundleProgress],
  );

  return {
    youtubeJobId,
    youtubeStatus,
    youtubeUrl,
    startYoutubeRender,
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
    exportStatus,
    smartExportBundle,
    yoloRender,
    thumbnailProgress: { estimatedSeconds: thumbnailProgressHook.estimatedSeconds, active: thumbnailProgressHook.active },
    seoProgress: { estimatedSeconds: seoProgressHook.estimatedSeconds, active: seoProgressHook.active },
    shortFormSeoProgress: { estimatedSeconds: shortFormSeoProgressHook.estimatedSeconds, active: shortFormSeoProgressHook.active },
    exportBundleProgress: { estimatedSeconds: exportBundleEstimatedSeconds, active: exportBundleActive },
  };
}
