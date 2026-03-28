import { useCallback, useEffect, useRef, useState } from "react";
import api from "../../api";
import type { ShortformSEOMetadata } from "../../types/render";

interface ThumbnailEntry {
  idx: number;
  title_text: string;
  image_url?: string;
  error?: string;
}

export interface ShortformState {
  platforms: string[];
  renderJobId: string | null;
  renderStatus: string;
  renderProgress: number;
  renderCurrentStep: string;
  renderUrl: string | null;
  renderError: string | null;
  seoMetadata: ShortformSEOMetadata | null;
  thumbnails: ThumbnailEntry[];
  isGeneratingSEO: boolean;
  isGeneratingThumbnails: boolean;
  startRender: (scriptId: string, title?: string, speed?: number) => void;
  generateSEO: (scriptId: string, platforms: string[]) => Promise<void>;
  generateThumbnails: (scriptId: string, brandStyle?: string, title?: string) => Promise<void>;
}

export function useShortformState(platforms: string[]): ShortformState {
  const [renderJobId, setRenderJobId] = useState<string | null>(null);
  const [renderStatus, setRenderStatus] = useState<string>("idle");
  const [renderProgress, setRenderProgress] = useState<number>(0);
  const [renderCurrentStep, setRenderCurrentStep] = useState<string>("");
  const [renderUrl, setRenderUrl] = useState<string | null>(null);
  const [renderError, setRenderError] = useState<string | null>(null);
  const [seoMetadata, setSeoMetadata] = useState<ShortformSEOMetadata | null>(null);
  const [thumbnails, setThumbnails] = useState<ThumbnailEntry[]>([]);
  const [isGeneratingSEO, setIsGeneratingSEO] = useState(false);
  const [isGeneratingThumbnails, setIsGeneratingThumbnails] = useState(false);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Clean up poll interval on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
  }, []);

  const startRender = useCallback(
    (scriptId: string, title?: string, speed?: number) => {
      // Reset state
      setRenderJobId(null);
      setRenderStatus("starting");
      setRenderProgress(0);
      setRenderCurrentStep("");
      setRenderUrl(null);
      setRenderError(null);

      // Clear any existing poll
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }

      (async () => {
        const res = await api.post("/api/render/shortform", {
          script_id: scriptId,
          title,
          speed,
        });

        if (!res.ok) {
          setRenderStatus("failed");
          setRenderError(
            (res.data as Record<string, unknown>)?.detail as string ??
              "Failed to start shortform render"
          );
          return;
        }

        const jobId = (res.data as Record<string, unknown>).job_id as string;
        setRenderJobId(jobId);
        setRenderStatus("running");

        pollRef.current = setInterval(async () => {
          const statusRes = await api.get(`/api/render/status/${jobId}`);
          if (!statusRes.ok) return;

          const d = statusRes.data as Record<string, unknown>;
          const status = d.status as string;
          setRenderStatus(status);
          setRenderProgress((d.progress as number) ?? 0);
          setRenderCurrentStep((d.current_step as string) ?? "");

          if (status === "completed") {
            if (pollRef.current) {
              clearInterval(pollRef.current);
              pollRef.current = null;
            }
            const urls = d.output_urls as string[] | undefined;
            if (urls && urls.length > 0) {
              setRenderUrl(urls[0]);
            }
          } else if (status === "failed") {
            if (pollRef.current) {
              clearInterval(pollRef.current);
              pollRef.current = null;
            }
            setRenderError((d.error as string) ?? "Render failed");
          }
        }, 1000);
      })();
    },
    [],
  );

  const generateSEO = useCallback(
    async (scriptId: string, plats: string[]) => {
      setIsGeneratingSEO(true);
      try {
        const res = await api.post("/api/seo/generate-shortform", {
          script_id: scriptId,
          platforms: plats,
        });
        if (res.ok) {
          setSeoMetadata(res.data as ShortformSEOMetadata);
        }
      } finally {
        setIsGeneratingSEO(false);
      }
    },
    [],
  );

  const generateThumbnails = useCallback(
    async (scriptId: string, brandStyle?: string, title?: string) => {
      setIsGeneratingThumbnails(true);
      try {
        const res = await api.post("/api/thumbnail/generate-shortform", {
          script_id: scriptId,
          brand_style: brandStyle,
          title,
        });
        if (res.ok) {
          const data = res.data as ThumbnailEntry[];
          // Resolve any relative image_url paths
          setThumbnails(
            data.map((t) => ({
              ...t,
              image_url: t.image_url ? assetUrl(t.image_url) : undefined,
            })),
          );
        }
      } finally {
        setIsGeneratingThumbnails(false);
      }
    },
    [],
  );

  return {
    platforms,
    renderJobId,
    renderStatus,
    renderProgress,
    renderCurrentStep,
    renderUrl,
    renderError,
    seoMetadata,
    thumbnails,
    isGeneratingSEO,
    isGeneratingThumbnails,
    startRender,
    generateSEO,
    generateThumbnails,
  };
}
