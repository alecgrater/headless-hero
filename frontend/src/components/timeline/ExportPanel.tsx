import { useEffect, useState } from "react";
import { Film, ImageIcon, Search, Smartphone, Upload, Video, X, Zap } from "lucide-react";
import api, { assetUrl, catalogUpload, getPublishStatus, getYouTubeOAuthStatus, showInFolder, openInBrowser, uploadLongformYouTube, getUploadTracking, setUploadTracking as apiSetUploadTracking, YOUTUBE_STUDIO_URL } from "../../api";
import { showToast } from "../ToastContainer";
import type { CatalogUploadOptions, PublishJobStatus } from "../../api";
import type { UploadTracking } from "../../types/script";
import type {
  ExportBundleResponse,
  ExportProgressStatus,
  RenderStatusResponse,
  SEOMetadata,
  ShortFormSEO,
  ShortFormSEOMetadata,
  ThumbnailConcept,
} from "../../types/render";
import ShortFormTab from "./short-form/ShortFormTab";
import ShortFormThumbnailsCard from "./short-form/ShortFormThumbnailsCard";
import MiniProgressBar from "../MiniProgressBar";
import { usePollJob } from "../../hooks/usePollJob";

interface Props {
  youtubeStatus: RenderStatusResponse | null;
  youtubeUrl: string | null;
  onStartYoutubeRender: (speed?: number) => void;

  thumbnails: ThumbnailConcept[];
  thumbnailsGenerating: boolean;
  onRecompositeThumbnail: () => void;

  seoMetadata: SEOMetadata | null;
  seoGenerating: boolean;
  onGenerateSEO: () => void;
  shortFormSeoMetadata: ShortFormSEOMetadata | null;
  shortFormSeoGenerating: boolean;
  onGenerateShortFormSEO: () => void;

  // Render estimate
  estimatedSeconds: number | null;

  // Export bundle
  exportBundleLoading: boolean;
  exportBundleResult: ExportBundleResponse | null;
  onYoloExport: () => Promise<void>;

  // Smart export phase
  exportPhase: "rendering" | "exporting" | null;
  exportStatus: ExportProgressStatus | null;

  // Operation progress
  thumbnailProgress: { estimatedSeconds: number | null; active: boolean };
  seoProgress: { estimatedSeconds: number | null; active: boolean };
  shortFormSeoProgress: { estimatedSeconds: number | null; active: boolean };
  exportBundleProgress: { estimatedSeconds: number | null; active: boolean };

  // YouTube upload
  youtubeConnected: boolean;
  onYoutubeConnectionChange: (connected: boolean) => void;
  onNavigateToSettings: () => void;
  seoTitle: string;
  seoDescription: string;
  seoTags: string[];
  projectTitle: string;

  onClose: () => void;

  // Short-form
  scriptId: string;
  segments: { name: string }[];

  initialTab?: LegacyInitialTab;
}

type LegacyInitialTab = "render-long" | "render-short" | "thumbnails" | "seo";
type TopTab = "long-form" | "short-form";
type SubTab = "render" | "thumbnails" | "seo";

const TOP_TABS: { key: TopTab; label: string; Icon: typeof Film }[] = [
  { key: "long-form", label: "Long Form", Icon: Film },
  { key: "short-form", label: "Short Form", Icon: Smartphone },
];

const SUB_TABS: { key: SubTab; label: string; Icon: typeof Video }[] = [
  { key: "render", label: "Render", Icon: Video },
  { key: "thumbnails", label: "Thumbnails", Icon: ImageIcon },
  { key: "seo", label: "SEO", Icon: Search },
];

function initialTopTab(initialTab?: LegacyInitialTab): TopTab {
  return initialTab === "render-short" ? "short-form" : "long-form";
}

function initialSubTab(initialTab?: LegacyInitialTab): SubTab {
  if (initialTab === "thumbnails") return "thumbnails";
  if (initialTab === "seo") return "seo";
  return "render";
}

function formatDuration(seconds: number, approximate = false): string {
  const m = Math.floor(seconds / 60);
  const s = Math.round(seconds % 60);
  const prefix = approximate ? "~" : "";
  if (m === 0) return `${prefix}${s}s`;
  return s > 0 ? `${prefix}${m}m ${s}s` : `${prefix}${m}m`;
}

function ProgressBar({
  progress,
  label,
  estimatedSeconds,
  elapsedSeconds,
}: {
  progress: number;
  label: string;
  estimatedSeconds?: number;
  elapsedSeconds?: number;
}) {
  const isRendering = progress > 0.4 && progress < 1;
  const remaining = estimatedSeconds && progress > 0.4 && progress < 1
    ? Math.max(0, Math.round(estimatedSeconds * (1 - progress)))
    : null;

  const elapsedStr = elapsedSeconds != null && elapsedSeconds > 0
    ? formatDuration(elapsedSeconds)
    : null;
  const etaStr = remaining != null && remaining > 0
    ? `${formatDuration(remaining, true)} remaining`
    : null;

  return (
    <div className="space-y-1.5">
      <div className="flex justify-between text-xs text-neutral-400">
        <span>{label}</span>
        <span className="flex items-center gap-3">
          {elapsedStr && <span className="text-neutral-300">{elapsedStr} elapsed</span>}
          {etaStr && <span className="text-neutral-500">{etaStr}</span>}
        </span>
      </div>
      <div className="w-full h-2 bg-neutral-800 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-300 ${
            isRendering
              ? "bg-gradient-to-r from-violet-600 via-violet-400 to-violet-600 bg-[length:200%_100%] animate-[shimmer_2s_ease-in-out_infinite]"
              : "bg-violet-500"
          }`}
          style={{ width: `${Math.max(progress * 100, 1)}%` }}
        />
      </div>
    </div>
  );
}

function DownloadButton({ url, label, projectTitle, filename }: { url: string; label: string; projectTitle?: string; filename?: string }) {
  const [downloading, setDownloading] = useState(false);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const cleanUrl = url.split("?")[0];
      const fullUrl = assetUrl(cleanUrl);
      const resolvedFilename = filename || cleanUrl.split("/").pop() || "download";

      if (projectTitle && window.api?.saveToDownloads) {
        const result = await window.api.saveToDownloads(fullUrl, projectTitle, resolvedFilename);
        const savedName = result?.filePath ? result.filePath.split("/").pop() || resolvedFilename : resolvedFilename;
        showToast(`Saved ${savedName} to Downloads`, "success");
        return;
      }

      if (window.api?.downloadFile) {
        await window.api.downloadFile(fullUrl, resolvedFilename);
        return;
      }

      // Fallback for browser dev mode
      const response = await fetch(fullUrl);
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = resolvedFilename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(blobUrl);
    } catch (err) {
      console.error("Download failed:", err);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <button
      onClick={handleDownload}
      disabled={downloading}
      className="inline-flex items-center gap-2 text-sm px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-60 rounded-lg font-medium transition-colors"
    >
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
      </svg>
      {downloading ? "Downloading..." : label}
    </button>
  );
}

function sanitizeExportName(name: string): string {
  return (name || "Untitled").replace(/[/\\?%*:|"<>]/g, "").trim() || "Untitled";
}

function longformExportFilename(asset: "Thumbnail" | "SEO" | "Video", projectTitle: string, extension: string): string {
  return `[Longform] [${asset}] - ${sanitizeExportName(projectTitle)}${extension}`;
}

function settingEnabled(value: string) {
  return !new Set(["0", "false", "no", "off"]).has(value.trim().toLowerCase());
}

function CopyButton({ text, label }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      className={`text-xs px-2 py-1 bg-neutral-800 hover:bg-neutral-700 rounded transition-all duration-150 ${
        copied ? "text-emerald-400 scale-105" : "text-neutral-400 scale-100"
      }`}
    >
      <span className="transition-opacity duration-150">
        {copied ? "Copied!" : label ?? "Copy"}
      </span>
    </button>
  );
}

function TagList({ tags }: { tags: string[] }) {
  const tagString = tags.join(", ");
  const charCount = tagString.length;
  const overLimit = charCount > 500;

  return (
    <div className="space-y-1">
      <p className="text-xs text-neutral-400 whitespace-pre-wrap select-all cursor-text bg-neutral-900/50 rounded p-2">
        {tagString}
      </p>
      <div className="flex items-center justify-between">
        <span className={`text-[10px] ${overLimit ? "text-red-400" : "text-neutral-500"}`}>
          {charCount}/500 characters
        </span>
        <CopyButton text={tagString} />
      </div>
    </div>
  );
}

function formatShortFormSEO(item: ShortFormSEO): string {
  const sections = [
    `Short ${item.index}`,
    `Title:\n${item.title}`,
    `Description:\n${item.description}`,
  ];
  if (item.hashtags.length > 0) {
    sections.push(`Hashtags:\n${item.hashtags.join(" ")}`);
  }
  if (item.tags.length > 0) {
    sections.push(`YouTube Tags:\n${item.tags.join(", ")}`);
  }
  return sections.join("\n\n");
}

export default function ExportPanel({
  youtubeStatus,
  youtubeUrl,
  onStartYoutubeRender,
  thumbnails,
  thumbnailsGenerating,
  onRecompositeThumbnail,
  seoMetadata,
  seoGenerating,
  onGenerateSEO,
  shortFormSeoMetadata,
  shortFormSeoGenerating,
  onGenerateShortFormSEO,
  estimatedSeconds,
  exportBundleLoading,
  exportBundleResult,
  onYoloExport,
  exportPhase,
  exportStatus,
  thumbnailProgress,
  seoProgress,
  shortFormSeoProgress,
  exportBundleProgress,
  youtubeConnected,
  onYoutubeConnectionChange,
  onNavigateToSettings,
  seoTitle,
  seoDescription,
  seoTags,
  projectTitle,
  onClose,
  scriptId,
  segments,
  initialTab,
}: Props) {
  const youtubeRendering = youtubeStatus?.status === "running" || youtubeStatus?.status === "pending";

  const [activeTopTab, setActiveTopTab] = useState<TopTab>(initialTopTab(initialTab));
  const [activeSubTab, setActiveSubTab] = useState<SubTab>(initialSubTab(initialTab));

  // YouTube upload state (post-export)
  const [showUploadPanel, setShowUploadPanel] = useState(false);
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadDesc, setUploadDesc] = useState("");
  const [uploadTags, setUploadTags] = useState("");
  const [uploadPrivacy, setUploadPrivacy] = useState("unlisted");
  const [uploadEditing, setUploadEditing] = useState(false);
  const [ytUploading, setYtUploading] = useState(false);
  const [ytUploadStatus, setYtUploadStatus] = useState<PublishJobStatus | null>(null);
  const [ytUploadError, setYtUploadError] = useState<string | null>(null);
  const [ytUploadedUrl, setYtUploadedUrl] = useState<string | null>(null);
  const [yoloExportError, setYoloExportError] = useState<string | null>(null);
  const [showSpeedRenderButton, setShowSpeedRenderButton] = useState(true);
  const [uploadTracking, setUploadTracking] = useState<UploadTracking>({
    longform_youtube: false,
    shortform_youtube: false,
    shortform_instagram: false,
    shortform_tiktok: false,
  });
  const [trackingUpdating, setTrackingUpdating] = useState<Partial<Record<keyof UploadTracking, boolean>>>({});

  const refreshUploadTracking = async () => {
    try {
      const tracking = await getUploadTracking(scriptId);
      setUploadTracking(tracking);
    } catch {
      // non-critical
    }
  };

  const handleToggleTracking = async (key: keyof UploadTracking) => {
    const newVal = !uploadTracking[key];
    setTrackingUpdating((prev) => ({ ...prev, [key]: true }));
    try {
      const updated = await apiSetUploadTracking(scriptId, { [key]: newVal });
      setUploadTracking(updated);
    } catch {
      // revert is handled by not updating local state on failure
    } finally {
      setTrackingUpdating((prev) => ({ ...prev, [key]: false }));
    }
  };

  useEffect(() => {
    let cancelled = false;
    api.get("/api/settings/keys").then((res) => {
      if (!res.ok || cancelled) return;
      const data = res.data as Record<string, { masked?: string }>;
      const value = data.SHOW_SPEED_RENDER_BUTTON?.masked ?? "true";
      setShowSpeedRenderButton(settingEnabled(value));
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    refreshUploadTracking();
  }, [scriptId]);

  const { startPolling: startUploadPolling, stopPolling: stopUploadPolling } = usePollJob<PublishJobStatus>({
    pollFn: async (jobId) => getPublishStatus(jobId),
    isComplete: (s) => s.status === "completed",
    isFailed: (s) => s.status === "failed",
    onStatus: (status) => {
      setYtUploadStatus(status);
      if (status.status === "completed" && status.output_urls.length > 0) {
        setYtUploading(false);
        setYtUploadedUrl(status.output_urls[0]);
        refreshUploadTracking();
      }
      if (status.status === "failed") {
        setYtUploading(false);
        setYtUploadError(status.error || "Upload failed");
        void getYouTubeOAuthStatus()
          .then((s) => onYoutubeConnectionChange(s.youtube.connected))
          .catch(() => {
            // Non-critical; the upload failure itself remains visible to the user.
          });
      }
    },
    onConnectionLost: () => {
      setYtUploading(false);
      setYtUploadError("Lost connection to upload job");
    },
  });

  const handleOpenUploadPanel = () => {
    const yt = seoMetadata?.youtube;
    setUploadTitle(yt?.title || seoTitle || "");
    setUploadDesc(yt?.description || seoDescription || "");
    setUploadTags((yt?.tags || seoTags || []).join(", "));
    setUploadPrivacy("unlisted");
    setUploadEditing(false);
    setYtUploadError(null);
    setYtUploadStatus(null);
    setYtUploadedUrl(null);
    setShowUploadPanel(true);
  };

  const handleStartUpload = async () => {
    if (!exportBundleResult) return;
    const folderPath = exportBundleResult.folder_path;
    const folderName = folderPath.split("/").pop() || "";
    setYtUploading(true);
    setYtUploadError(null);
    try {
      const options: CatalogUploadOptions = {
        folder_name: folderName,
        title: uploadTitle,
        description: uploadDesc,
        tags: uploadTags.split(",").map((t) => t.trim()).filter(Boolean),
        privacy_status: uploadPrivacy,
      };
      const { job_id } = await catalogUpload(options);
      startUploadPolling(job_id);
    } catch (err) {
      setYtUploading(false);
      setYtUploadError(err instanceof Error ? err.message : "Upload failed");
    }
  };

  const handleYoloExport = async () => {
    if (exportBundleLoading || exportPhase !== null) return;
    setYoloExportError(null);
    try {
      await onYoloExport();
    } catch (err) {
      setYoloExportError(err instanceof Error ? err.message : "YOLO export failed");
    }
  };

  const handleUploadLongform = async () => {
    if (ytUploading) return;
    setYtUploadError(null);
    setYtUploadedUrl(null);
    setYtUploadStatus(null);
    setShowUploadPanel(false);
    setYtUploading(true);
    try {
      const { job_id } = await uploadLongformYouTube(scriptId);
      startUploadPolling(job_id);
    } catch (err) {
      setYtUploading(false);
      setYtUploadError(err instanceof Error ? err.message : "Upload failed");
    }
  };

  const tabDescriptions: Record<TopTab, Record<SubTab, string>> = {
    "long-form": {
      render: "Renders the full long form video at 1920×1080 16:9 30FPS.",
      thumbnails: "Generate and download YouTube thumbnail concepts for this video.",
      seo: "Generate long-form YouTube title, timestamped description, and tags.",
    },
    "short-form": {
      render: `Renders ${segments.length} short form videos, one per segment. 1080×1920 9:16 30FPS.`,
      thumbnails: "Generate TikTok-safe vertical thumbnail covers from each segment title-card image.",
      seo: "Generate upload text for TikTok, YouTube Shorts, and Instagram.",
    },
  };

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-8">
      <div className="bg-neutral-900 border border-neutral-700/80 rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl shadow-black/70 overflow-hidden">
        {/* Header */}
        <div className="flex flex-col border-b border-neutral-800 shrink-0 bg-neutral-900/95">
          <div className="flex items-center justify-between px-6 py-4">
            <div>
              <h2 className="text-lg font-semibold text-neutral-100">Export</h2>
              <p className="mt-0.5 text-xs text-neutral-500">Package final video assets, thumbnails, and upload metadata.</p>
            </div>
            <div className="flex items-center gap-3">
              {exportBundleResult && (
                <div className="flex items-center gap-2 text-xs text-emerald-400">
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                  </svg>
                  <span>{exportBundleResult.files.length} files exported</span>
                  <button
                    onClick={() => showInFolder(exportBundleResult.folder_path)}
                    className="text-violet-400 hover:text-violet-300 underline"
                  >
                    Open in Finder
                  </button>
                  {youtubeConnected && !ytUploadedUrl && !ytUploading && (
                    <button
                      onClick={handleOpenUploadPanel}
                      className="flex items-center gap-1 text-red-400 hover:text-red-300 underline"
                    >
                      <svg className="w-3 h-3" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0C.488 3.45.029 5.804 0 12c.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0C23.512 20.55 23.971 18.196 24 12c-.029-6.185-.484-8.549-4.385-8.816zM9 16V8l8 4-8 4z" />
                      </svg>
                      Upload to YouTube
                    </button>
                  )}
                  {!youtubeConnected && (
                    <button
                      onClick={onNavigateToSettings}
                      className="text-neutral-400 hover:text-neutral-300 underline"
                    >
                      Connect YouTube
                    </button>
                  )}
                  {ytUploadedUrl && (
                    <button
                      onClick={() => openInBrowser(ytUploadedUrl)}
                      className="flex items-center gap-1 text-red-400 hover:text-red-300 underline"
                    >
                      <svg className="w-3 h-3" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0C.488 3.45.029 5.804 0 12c.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0C23.512 20.55 23.971 18.196 24 12c-.029-6.185-.484-8.549-4.385-8.816zM9 16V8l8 4-8 4z" />
                      </svg>
                      View on YouTube
                    </button>
                  )}
                </div>
              )}
              <button
                onClick={handleYoloExport}
                disabled={exportBundleLoading || exportPhase !== null}
                className="group relative flex h-10 w-[9.5rem] items-center justify-center overflow-hidden rounded-lg px-4 text-center text-xs font-bold leading-tight text-white/95 transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 hover:scale-[1.02] disabled:opacity-50 disabled:hover:scale-100 bg-gradient-to-r from-sky-500/80 via-emerald-400/70 to-amber-400/70 shadow-[0_0_15px_rgba(14,165,233,0.2)] hover:shadow-[0_0_22px_rgba(14,165,233,0.35)]"
              >
                <span className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent animate-[shimmer_2s_ease-in-out_infinite]" />
                {exportPhase === "rendering" ? (
                  <span className="relative flex min-w-0 items-center justify-center gap-1.5 text-center">
                    <span className="w-3 h-3 border-2 border-white/70 border-t-transparent rounded-full animate-spin" />
                    Rendering
                  </span>
                ) : exportPhase === "exporting" || exportBundleLoading ? (
                  <span className="relative flex min-w-0 items-center justify-center gap-1.5 text-center">
                    <span className="w-3 h-3 border-2 border-white/70 border-t-transparent rounded-full animate-spin" />
                    Exporting
                  </span>
                ) : (
                  <span className="relative flex min-w-0 items-center justify-center gap-1.5 text-center">
                    <Zap size={12} />
                    YOLO EXPORT
                  </span>
                )}
              </button>
              <button
                onClick={onClose}
                className="w-8 h-8 rounded-lg text-neutral-500 hover:text-neutral-100 hover:bg-neutral-800 transition-colors flex items-center justify-center"
                aria-label="Close export window"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>
          {exportPhase === "rendering" && (youtubeRendering && youtubeStatus ? youtubeStatus : exportStatus) && (
            <div className="px-6 pb-3">
              <ProgressBar
                progress={youtubeRendering && youtubeStatus ? youtubeStatus.progress : exportStatus?.progress ?? 0}
                label={youtubeRendering && youtubeStatus ? youtubeStatus.current_step : exportStatus?.label ?? "Preparing export..."}
                estimatedSeconds={youtubeRendering && youtubeStatus ? youtubeStatus.estimated_seconds : exportBundleProgress.estimatedSeconds ?? undefined}
                elapsedSeconds={youtubeRendering && youtubeStatus ? youtubeStatus.elapsed_seconds : undefined}
              />
            </div>
          )}
          {(exportPhase === "exporting" || exportBundleLoading) && (
            <div className="px-6 pb-3">
              {exportStatus ? (
                <ProgressBar
                  progress={exportStatus.progress}
                  label={exportStatus.label}
                  estimatedSeconds={exportBundleProgress.estimatedSeconds ?? undefined}
                />
              ) : (
                <>
                  <div className="mb-1 flex justify-between text-xs text-neutral-400">
                    <span>Preparing export deliverables...</span>
                  </div>
                  <MiniProgressBar estimatedSeconds={exportBundleProgress.estimatedSeconds} active={exportBundleProgress.active} />
                </>
              )}
            </div>
          )}
          {yoloExportError && (
            <div className="px-6 pb-3 text-xs text-red-400">
              {yoloExportError}
            </div>
          )}
        </div>

        {/* Top Tab Bar */}
        <div className="px-6 py-4 shrink-0 border-b border-neutral-800 bg-neutral-950/25">
          <div className="flex items-center gap-4">
            <div className="inline-flex rounded-xl border border-neutral-800 bg-neutral-950/70 p-1">
              {TOP_TABS.map((tab) => {
                const Icon = tab.Icon;
                return (
                  <button
                    key={tab.key}
                    onClick={() => setActiveTopTab(tab.key)}
                    className={`h-9 min-w-32 px-4 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2 ${
                      activeTopTab === tab.key
                        ? "bg-violet-500/15 text-violet-200 border border-violet-400/30"
                        : "text-neutral-500 border border-transparent hover:text-neutral-300 hover:bg-neutral-800/70"
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    {tab.label}
                  </button>
                );
              })}
            </div>
            <div className="h-8 w-px bg-neutral-800" />
            <div className="inline-flex rounded-xl border border-neutral-800 bg-neutral-950/70 p-1">
              {SUB_TABS.map((tab) => {
                const Icon = tab.Icon;
                return (
                  <button
                    key={tab.key}
                    onClick={() => setActiveSubTab(tab.key)}
                    className={`h-8 px-3 rounded-lg text-xs font-medium transition-colors flex items-center justify-center gap-1.5 ${
                      activeSubTab === tab.key
                        ? "bg-neutral-100 text-neutral-950"
                        : "text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800/70"
                    }`}
                  >
                    <Icon className="w-3.5 h-3.5" />
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
        <div className="px-6 py-3 text-xs text-neutral-400 border-b border-neutral-800/50 shrink-0 bg-neutral-900">
          {tabDescriptions[activeTopTab][activeSubTab]}
        </div>

        {/* Tab Content */}
        <div className="p-6 overflow-y-auto flex-1">
          {/* Render - Long Form Tab */}
          {activeTopTab === "long-form" && activeSubTab === "render" && (
            <div className="space-y-8">
              {/* YouTube Export */}
              <section className="space-y-3">
                <h3 className="text-sm font-semibold text-neutral-300 uppercase tracking-wider">
                  YouTube Export (16:9)
                </h3>
                {youtubeRendering && youtubeStatus ? (
                  <ProgressBar progress={youtubeStatus.progress} label={youtubeStatus.current_step} estimatedSeconds={youtubeStatus.estimated_seconds} elapsedSeconds={youtubeStatus.elapsed_seconds} />
                ) : youtubeUrl ? (
                  <div className="space-y-3">
                    <video
                      src={assetUrl(youtubeUrl)}
                      controls
                      className="w-full max-h-[300px] rounded-lg border border-neutral-700"
                    />
                    <DownloadButton url={youtubeUrl} label="Download YouTube Video" projectTitle={projectTitle} filename={longformExportFilename("Video", projectTitle, ".mp4")} />
                  </div>
                ) : youtubeStatus?.status === "failed" ? (
                  <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                    Render failed: {youtubeStatus.error ?? "Unknown error"}
                  </div>
                ) : null}
                {!youtubeRendering && (
                  <div className="flex flex-wrap items-center gap-3">
                    <button
                      onClick={() => onStartYoutubeRender()}
                      className="text-sm px-4 py-2 bg-violet-600 hover:bg-violet-500 rounded-lg font-medium transition-colors"
                    >
                      {youtubeUrl ? "Re-render" : "Render YouTube Video"}
                    </button>
                    <button
                      onClick={youtubeConnected ? handleUploadLongform : onNavigateToSettings}
                      disabled={ytUploading}
                      className="text-sm px-4 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-50 rounded-lg font-medium transition-colors inline-flex items-center gap-2"
                    >
                      {ytUploading ? (
                        <>
                          <span className="w-4 h-4 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />
                          Uploading
                        </>
                      ) : (
                        <>
                          <Upload className="w-4 h-4" />
                          Upload YouTube Video
                        </>
                      )}
                    </button>
                    <button
                      onClick={() => openInBrowser(YOUTUBE_STUDIO_URL)}
                      className="text-sm px-4 py-2 bg-neutral-700 hover:bg-neutral-600 rounded-lg font-medium transition-colors inline-flex items-center gap-2 text-neutral-200"
                    >
                      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0C.488 3.45.029 5.804 0 12c.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0C23.512 20.55 23.971 18.196 24 12c-.029-6.185-.484-8.549-4.385-8.816zM9 16V8l8 4-8 4z" />
                      </svg>
                      Open YouTube Studio
                    </button>
                    {showSpeedRenderButton && (
                      <button
                        onClick={() => onStartYoutubeRender(1.25)}
                        className="text-sm px-4 py-2 bg-violet-600 hover:bg-violet-500 rounded-lg font-medium transition-colors"
                      >
                        {youtubeUrl ? "Re-render (1.25x)" : "Render YouTube Video (1.25x Speed)"}
                      </button>
                    )}
                    {estimatedSeconds != null && !youtubeUrl && (
                      <span className="text-xs text-neutral-500">
                        Estimated render time: {formatDuration(estimatedSeconds, true)}
                      </span>
                    )}
                  </div>
                )}
                {ytUploading && ytUploadStatus && (
                  <ProgressBar
                    progress={ytUploadStatus.progress || 0}
                    label={ytUploadStatus.current_step || "Uploading to YouTube..."}
                  />
                )}
                {ytUploadError && (
                  <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                    {ytUploadError}
                  </div>
                )}
                {ytUploadedUrl && (
                  <div className="text-sm text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-3 flex items-center gap-2">
                    <span>Uploaded to YouTube.</span>
                    <button
                      onClick={() => openInBrowser(ytUploadedUrl)}
                      className="text-red-300 hover:text-red-200 underline transition-colors"
                    >
                      View on YouTube
                    </button>
                  </div>
                )}
              </section>


              {/* Distribution Tracking */}
              <section className="space-y-3">
                <h3 className="text-sm font-semibold text-neutral-300 uppercase tracking-wider">Distribution Tracking</h3>
                <p className="text-xs text-neutral-500">Track where this video has been published. Auto-updates after in-app uploads — click to toggle manually.</p>
                <div className="flex flex-wrap gap-2">
                  {([
                    { key: "longform_youtube" as const, label: "YouTube (Long)", icon: (filled: boolean) => (
                      <svg className={`w-3.5 h-3.5 ${filled ? "text-red-400" : "text-neutral-500"}`} viewBox="0 0 24 24" fill={filled ? "currentColor" : "none"} stroke={filled ? "none" : "currentColor"} strokeWidth={1.5}>
                        <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0C.488 3.45.029 5.804 0 12c.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0C23.512 20.55 23.971 18.196 24 12c-.029-6.185-.484-8.549-4.385-8.816zM9 16V8l8 4-8 4z" />
                      </svg>
                    )},
                    { key: "shortform_youtube" as const, label: "YouTube (Short)", icon: (filled: boolean) => (
                      <svg className={`w-3.5 h-3.5 ${filled ? "text-red-400" : "text-neutral-500"}`} viewBox="0 0 24 24" fill={filled ? "currentColor" : "none"} stroke={filled ? "none" : "currentColor"} strokeWidth={1.5}>
                        <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0C.488 3.45.029 5.804 0 12c.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0C23.512 20.55 23.971 18.196 24 12c-.029-6.185-.484-8.549-4.385-8.816zM9 16V8l8 4-8 4z" />
                        <path d="M3 19h18" strokeLinecap="round" />
                      </svg>
                    )},
                    { key: "shortform_instagram" as const, label: "Instagram", icon: (filled: boolean) => (
                      <svg className={`w-3.5 h-3.5 ${filled ? "text-pink-400" : "text-neutral-500"}`} viewBox="0 0 24 24" fill={filled ? "currentColor" : "none"} stroke={filled ? "none" : "currentColor"} strokeWidth={1.5}>
                        <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z" />
                      </svg>
                    )},
                    { key: "shortform_tiktok" as const, label: "TikTok", icon: (filled: boolean) => (
                      <svg className={`w-3.5 h-3.5 ${filled ? "text-neutral-100" : "text-neutral-500"}`} viewBox="0 0 24 24" fill={filled ? "currentColor" : "none"} stroke={filled ? "none" : "currentColor"} strokeWidth={1.5}>
                        <path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-2.88 2.5 2.89 2.89 0 01-2.89-2.89 2.89 2.89 0 012.89-2.89c.28 0 .54.04.79.1V9.01a6.27 6.27 0 00-.79-.05 6.34 6.34 0 00-6.34 6.34 6.34 6.34 0 006.34 6.34 6.34 6.34 0 006.33-6.34V8.95a8.19 8.19 0 004.79 1.53V7.03a4.85 4.85 0 01-1.02-.34z" />
                      </svg>
                    )},
                  ] as const).map(({ key, label, icon }) => {
                    const isUploaded = uploadTracking[key];
                    const isUpdating = trackingUpdating[key];
                    return (
                      <button
                        key={key}
                        onClick={() => handleToggleTracking(key)}
                        disabled={isUpdating}
                        title={isUploaded ? `Mark as not uploaded to ${label}` : `Mark as uploaded to ${label}`}
                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-all ${
                          isUploaded
                            ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20"
                            : "border-neutral-700 bg-neutral-800/60 text-neutral-500 hover:text-neutral-300 hover:border-neutral-600"
                        } disabled:opacity-50`}
                      >
                        {isUpdating ? (
                          <span className="w-3.5 h-3.5 border border-current border-t-transparent rounded-full animate-spin" />
                        ) : icon(isUploaded)}
                        {label}
                        {isUploaded && (
                          <svg className="w-3 h-3 text-emerald-400" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
                          </svg>
                        )}
                      </button>
                    );
                  })}
                </div>
              </section>
            </div>
          )}

          {/* Render - Short Form Tab */}
          {activeTopTab === "short-form" && activeSubTab === "render" && (
            <div className="space-y-6">
              <ShortFormTab
                scriptId={scriptId}
                segments={segments}
                shortFormSeoMetadata={shortFormSeoMetadata}
                onUploadComplete={refreshUploadTracking}
              />
              {/* Distribution Tracking — Short-Form */}
              <section className="space-y-3 border-t border-neutral-800 pt-5">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-neutral-300 uppercase tracking-wider">Distribution Tracking</h3>
                  <span className="text-xs text-neutral-600">Click to toggle</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {([
                    { key: "shortform_youtube" as const, label: "YouTube Shorts", icon: (filled: boolean) => (
                      <svg className={`w-3.5 h-3.5 ${filled ? "text-red-400" : "text-neutral-500"}`} viewBox="0 0 24 24" fill={filled ? "currentColor" : "none"} stroke={filled ? "none" : "currentColor"} strokeWidth={1.5}>
                        <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0C.488 3.45.029 5.804 0 12c.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0C23.512 20.55 23.971 18.196 24 12c-.029-6.185-.484-8.549-4.385-8.816zM9 16V8l8 4-8 4z" />
                      </svg>
                    )},
                    { key: "shortform_instagram" as const, label: "Instagram Reels", icon: (filled: boolean) => (
                      <svg className={`w-3.5 h-3.5 ${filled ? "text-pink-400" : "text-neutral-500"}`} viewBox="0 0 24 24" fill={filled ? "currentColor" : "none"} stroke={filled ? "none" : "currentColor"} strokeWidth={1.5}>
                        <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z" />
                      </svg>
                    )},
                    { key: "shortform_tiktok" as const, label: "TikTok", icon: (filled: boolean) => (
                      <svg className={`w-3.5 h-3.5 ${filled ? "text-neutral-100" : "text-neutral-500"}`} viewBox="0 0 24 24" fill={filled ? "currentColor" : "none"} stroke={filled ? "none" : "currentColor"} strokeWidth={1.5}>
                        <path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-2.88 2.5 2.89 2.89 0 01-2.89-2.89 2.89 2.89 0 012.89-2.89c.28 0 .54.04.79.1V9.01a6.27 6.27 0 00-.79-.05 6.34 6.34 0 00-6.34 6.34 6.34 6.34 0 006.34 6.34 6.34 6.34 0 006.33-6.34V8.95a8.19 8.19 0 004.79 1.53V7.03a4.85 4.85 0 01-1.02-.34z" />
                      </svg>
                    )},
                  ] as const).map(({ key, label, icon }) => {
                    const isUploaded = uploadTracking[key];
                    const isUpdating = trackingUpdating[key];
                    return (
                      <button
                        key={key}
                        onClick={() => handleToggleTracking(key)}
                        disabled={isUpdating}
                        title={isUploaded ? `Mark as not uploaded to ${label}` : `Mark as uploaded to ${label}`}
                        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-all ${
                          isUploaded
                            ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20"
                            : "border-neutral-700 bg-neutral-800/60 text-neutral-500 hover:text-neutral-300 hover:border-neutral-600"
                        } disabled:opacity-50`}
                      >
                        {isUpdating ? (
                          <span className="w-3.5 h-3.5 border border-current border-t-transparent rounded-full animate-spin" />
                        ) : icon(isUploaded)}
                        {label}
                        {isUploaded && (
                          <svg className="w-3 h-3 text-emerald-400" fill="none" viewBox="0 0 24 24" strokeWidth={2.5} stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
                          </svg>
                        )}
                      </button>
                    );
                  })}
                </div>
              </section>
            </div>
          )}

          {/* Thumbnails Tab */}
          {activeTopTab === "long-form" && activeSubTab === "thumbnails" && (
            <section className="space-y-3">
              <h3 className="text-sm font-semibold text-neutral-300 uppercase tracking-wider">
                Thumbnails
              </h3>

              {thumbnails.length > 0 && (
                <div className="grid grid-cols-2 gap-3">
                  {thumbnails.map((t) => (
                    <div key={t.idx} className="space-y-1">
                      {t.image_url ? (
                        <>
                          <img
                            src={assetUrl(t.image_url)}
                            alt={t.title_text}
                            className="w-full aspect-video object-cover rounded-lg border border-neutral-700 cursor-pointer hover:border-violet-500 transition-colors"
                          />
                          <DownloadButton url={t.image_url} label="Download" projectTitle={projectTitle} filename={longformExportFilename("Thumbnail", projectTitle, ".png")} />
                        </>
                      ) : t.error ? (
                        <div className="w-full aspect-video bg-red-500/10 rounded-lg flex items-center justify-center text-xs text-red-400 p-2">
                          Error: {t.error}
                        </div>
                      ) : null}
                      <p className="text-xs text-neutral-400 truncate">{t.title_text}</p>
                    </div>
                  ))}
                </div>
              )}
              <button
                onClick={onRecompositeThumbnail}
                disabled={thumbnailsGenerating}
                className="text-sm px-4 py-2 bg-amber-600 hover:bg-amber-500 disabled:opacity-40 rounded-lg font-medium transition-colors flex items-center gap-2"
              >
                {thumbnailsGenerating ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />
                    Regenerating...
                  </>
                ) : (
                  "Regenerate Thumbnail"
                )}
              </button>
              {thumbnailsGenerating && <MiniProgressBar estimatedSeconds={thumbnailProgress.estimatedSeconds} active={thumbnailProgress.active} />}
            </section>
          )}

          {/* Short-Form Thumbnails Tab */}
          {activeTopTab === "short-form" && activeSubTab === "thumbnails" && (
            <ShortFormThumbnailsCard scriptId={scriptId} segments={segments} />
          )}

          {/* SEO Tab */}
          {activeTopTab === "long-form" && activeSubTab === "seo" && (
            <section className="space-y-6">
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-semibold text-neutral-300 uppercase tracking-wider">
                      Long-Form YouTube
                    </h3>
                    <p className="text-xs text-neutral-500">
                      Title, timestamped description, and tags for the full video.
                    </p>
                  </div>
                  <button
                    onClick={onGenerateSEO}
                    disabled={seoGenerating}
                    className="text-sm px-4 py-2 bg-teal-600 hover:bg-teal-500 disabled:opacity-40 rounded-lg font-medium transition-colors flex items-center gap-2"
                  >
                    {seoGenerating ? (
                      <>
                        <span className="w-4 h-4 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />
                        Generating...
                      </>
                    ) : seoMetadata ? (
                      "Regenerate Long SEO"
                    ) : (
                      "Generate Long SEO"
                    )}
                  </button>
                </div>

                {seoMetadata && (
                  <div className="bg-neutral-800/50 rounded-lg p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-neutral-400 uppercase">YouTube</span>
                      <CopyButton text={`Title:\n${seoMetadata.youtube.title}\n\nDescription:\n${seoMetadata.youtube.description}\n\nTags:\n${seoMetadata.youtube.tags.join(", ")}`} />
                    </div>
                    <p className="text-sm font-medium text-neutral-200">{seoMetadata.youtube.title}</p>
                    <p className="text-xs text-neutral-400 whitespace-pre-wrap">{seoMetadata.youtube.description}</p>
                    <TagList tags={seoMetadata.youtube.tags} />
                  </div>
                )}
                {seoGenerating && <MiniProgressBar estimatedSeconds={seoProgress.estimatedSeconds} active={seoProgress.active} />}
              </div>
            </section>
          )}

          {activeTopTab === "short-form" && activeSubTab === "seo" && (
            <section className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold text-neutral-300 uppercase tracking-wider">
                    Short-Form Uploads
                  </h3>
                  <p className="text-xs text-neutral-500">
                    One generation call creates upload text for all {segments.length} shorts across TikTok, YouTube Shorts, and Instagram.
                  </p>
                </div>
                <button
                  onClick={onGenerateShortFormSEO}
                  disabled={shortFormSeoGenerating}
                  className="text-sm px-4 py-2 bg-sky-600 hover:bg-sky-500 disabled:opacity-40 rounded-lg font-medium transition-colors flex items-center gap-2"
                >
                  {shortFormSeoGenerating ? (
                    <>
                      <span className="w-4 h-4 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />
                      Generating...
                    </>
                  ) : shortFormSeoMetadata ? (
                    "Regenerate Short SEO"
                  ) : (
                    `Generate All ${segments.length} Short SEO`
                  )}
                </button>
              </div>

              {shortFormSeoMetadata && (
                <div className="space-y-3">
                  <div className="flex items-center justify-between rounded-lg border border-sky-500/20 bg-sky-500/10 px-3 py-2">
                    <span className="text-xs text-sky-200">
                      {shortFormSeoMetadata.shorts.length}/{segments.length} shorts packaged
                    </span>
                    <CopyButton
                      label="Copy All"
                      text={shortFormSeoMetadata.shorts.map(formatShortFormSEO).join("\n\n---\n\n")}
                    />
                  </div>
                  <div className="grid grid-cols-1 gap-3">
                    {shortFormSeoMetadata.shorts
                      .slice()
                      .sort((a, b) => a.index - b.index)
                      .map((item) => (
                        <div key={item.index} className="bg-neutral-800/50 rounded-lg p-4 space-y-3">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <span className="text-xs font-semibold text-neutral-400 uppercase">
                                Short {item.index}
                              </span>
                              <p className="mt-1 text-sm font-medium text-neutral-200">{item.title}</p>
                            </div>
                            <CopyButton text={formatShortFormSEO(item)} />
                          </div>
                          <p className="text-xs text-neutral-400 whitespace-pre-wrap">{item.description}</p>
                          {item.hashtags.length > 0 && (
                            <p className="text-xs text-sky-300 whitespace-pre-wrap select-all cursor-text bg-neutral-900/50 rounded p-2">
                              {item.hashtags.join(" ")}
                            </p>
                          )}
                          <TagList tags={item.tags} />
                        </div>
                      ))}
                  </div>
                </div>
              )}
              {shortFormSeoGenerating && (
                <MiniProgressBar
                  estimatedSeconds={shortFormSeoProgress.estimatedSeconds}
                  active={shortFormSeoProgress.active}
                />
              )}
            </section>
          )}
        </div>

        {/* YouTube Upload Panel (slide-up after export) */}
        {showUploadPanel && (
          <div className="border-t border-neutral-800 p-6 shrink-0 space-y-4 bg-neutral-900/95">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-neutral-300 uppercase tracking-wider">Upload to YouTube</h3>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setUploadEditing(!uploadEditing)}
                  className="text-[11px] text-violet-400 hover:text-violet-300 transition-colors"
                >
                  {uploadEditing ? "Done Editing" : "Edit Metadata"}
                </button>
                <button
                  onClick={() => { setShowUploadPanel(false); stopUploadPolling(); }}
                  className="text-neutral-500 hover:text-neutral-300 transition-colors text-lg leading-none"
                >
                  &times;
                </button>
              </div>
            </div>

            {ytUploading && ytUploadStatus && (
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs text-neutral-400">
                  <span>{ytUploadStatus.current_step || "Starting upload..."}</span>
                  <span>{Math.round((ytUploadStatus.progress || 0) * 100)}%</span>
                </div>
                <div className="w-full h-2 bg-neutral-800 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full bg-red-500 transition-all duration-300"
                    style={{ width: `${Math.max((ytUploadStatus.progress || 0) * 100, 1)}%` }}
                  />
                </div>
              </div>
            )}

            {ytUploadError && (
              <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/30 rounded-lg p-2">
                {ytUploadError}
              </div>
            )}

            {ytUploadedUrl && (
              <div className="flex items-center gap-2 text-sm text-emerald-400">
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
                <span>Uploaded!</span>
                <button
                  onClick={() => openInBrowser(ytUploadedUrl)}
                  className="text-red-400 hover:text-red-300 underline"
                >
                  View on YouTube
                </button>
              </div>
            )}

            {!ytUploading && !ytUploadedUrl && (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[11px] text-neutral-500 block mb-0.5">Title</label>
                    {uploadEditing ? (
                      <input
                        type="text"
                        value={uploadTitle}
                        onChange={(e) => setUploadTitle(e.target.value)}
                        className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-2.5 py-1.5 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 transition-colors"
                      />
                    ) : (
                      <p className="text-sm text-neutral-200 truncate">{uploadTitle || "Untitled"}</p>
                    )}
                  </div>
                  <div>
                    <label className="text-[11px] text-neutral-500 block mb-0.5">Privacy</label>
                    <select
                      value={uploadPrivacy}
                      onChange={(e) => setUploadPrivacy(e.target.value)}
                      className="bg-neutral-800 border border-neutral-700 rounded-lg px-2.5 py-1.5 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 transition-colors"
                    >
                      <option value="unlisted">Unlisted</option>
                      <option value="private">Private</option>
                      <option value="public">Public</option>
                    </select>
                  </div>
                </div>

                {uploadEditing && (
                  <div className="space-y-2">
                    <div>
                      <label className="text-[11px] text-neutral-500 block mb-0.5">Description</label>
                      <textarea
                        value={uploadDesc}
                        onChange={(e) => setUploadDesc(e.target.value)}
                        rows={2}
                        className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-2.5 py-1.5 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 transition-colors resize-none"
                      />
                    </div>
                    <div>
                      <label className="text-[11px] text-neutral-500 block mb-0.5">Tags</label>
                      <input
                        type="text"
                        value={uploadTags}
                        onChange={(e) => setUploadTags(e.target.value)}
                        className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-2.5 py-1.5 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 transition-colors"
                        placeholder="tag1, tag2, tag3"
                      />
                    </div>
                  </div>
                )}

                <div className="flex items-center gap-2">
                  <button
                    onClick={handleStartUpload}
                    className="flex items-center gap-2 text-sm px-4 py-2 bg-red-600 hover:bg-red-500 rounded-lg font-medium transition-colors text-white"
                  >
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0C.488 3.45.029 5.804 0 12c.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0C23.512 20.55 23.971 18.196 24 12c-.029-6.185-.484-8.549-4.385-8.816zM9 16V8l8 4-8 4z" />
                    </svg>
                    Upload
                  </button>
                  <button
                    onClick={() => openInBrowser(YOUTUBE_STUDIO_URL)}
                    className="flex items-center gap-2 text-sm px-4 py-2 bg-neutral-700 hover:bg-neutral-600 rounded-lg font-medium transition-colors text-neutral-200"
                  >
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0C.488 3.45.029 5.804 0 12c.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0C23.512 20.55 23.971 18.196 24 12c-.029-6.185-.484-8.549-4.385-8.816zM9 16V8l8 4-8 4z" />
                    </svg>
                    Open YouTube Studio
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
