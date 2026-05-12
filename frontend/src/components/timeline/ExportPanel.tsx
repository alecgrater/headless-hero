import { useState } from "react";
import { assetUrl, catalogUpload, getPublishStatus, showInFolder, openInBrowser } from "../../api";
import type { CatalogUploadOptions, PublishJobStatus } from "../../api";
import type { ExportBundleResponse, RenderStatusResponse, SEOMetadata, ThumbnailConcept } from "../../types/render";
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

  // Render estimate
  estimatedSeconds: number | null;

  // Export bundle
  exportBundleLoading: boolean;
  exportBundleResult: ExportBundleResponse | null;
  onExportBundle: () => void;

  // Smart export phase
  exportPhase: "rendering" | "exporting" | null;

  // Operation progress
  thumbnailProgress: { estimatedSeconds: number | null; active: boolean };
  seoProgress: { estimatedSeconds: number | null; active: boolean };
  exportBundleProgress: { estimatedSeconds: number | null; active: boolean };

  // YouTube upload
  youtubeConnected: boolean;
  onNavigateToSettings: () => void;
  seoTitle: string;
  seoDescription: string;
  seoTags: string[];
  projectTitle: string;

  onClose: () => void;
}

type Tab = "render" | "thumbnails" | "seo";

const TABS: { key: Tab; label: string }[] = [
  { key: "render", label: "Render" },
  { key: "thumbnails", label: "Thumbnails" },
  { key: "seo", label: "SEO" },
];

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
      const fullUrl = assetUrl(url.split("?")[0]);
      const resolvedFilename = filename || url.split("/").pop()?.split("?")[0] || "download";

      if (projectTitle && window.api?.saveToDownloads) {
        await window.api.saveToDownloads(fullUrl, projectTitle, resolvedFilename);
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

function TabBadge({ active }: { active: boolean }) {
  if (!active) return null;
  return <span className="w-2 h-2 rounded-full bg-emerald-400 ml-1.5 inline-block" />;
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
  estimatedSeconds,
  exportBundleLoading,
  exportBundleResult,
  onExportBundle,
  exportPhase,
  thumbnailProgress,
  seoProgress,
  exportBundleProgress,
  youtubeConnected,
  onNavigateToSettings,
  seoTitle,
  seoDescription,
  seoTags,
  projectTitle,
  onClose,
}: Props) {
  const youtubeRendering = youtubeStatus?.status === "running" || youtubeStatus?.status === "pending";

  const [activeTab, setActiveTab] = useState<Tab>("render");

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

  const { startPolling: startUploadPolling, stopPolling: stopUploadPolling } = usePollJob<PublishJobStatus>({
    pollFn: async (jobId) => getPublishStatus(jobId),
    isComplete: (s) => s.status === "completed",
    isFailed: (s) => s.status === "failed",
    onStatus: (status) => {
      setYtUploadStatus(status);
      if (status.status === "completed" && status.output_urls.length > 0) {
        setYtUploading(false);
        setYtUploadedUrl(status.output_urls[0]);
      }
      if (status.status === "failed") {
        setYtUploading(false);
        setYtUploadError(status.error || "Upload failed");
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

  const tabBadges: Record<Tab, boolean> = {
    render: !!youtubeUrl,
    thumbnails: thumbnails.length > 0,
    seo: !!seoMetadata,
  };

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-8">
      <div className="bg-neutral-900 border border-neutral-800 rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex flex-col border-b border-neutral-800 shrink-0">
          <div className="flex items-center justify-between px-6 py-4">
            <h2 className="text-lg font-bold">Export</h2>
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
                onClick={onExportBundle}
                disabled={exportBundleLoading || exportPhase !== null}
                className="text-sm px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 rounded-lg font-medium transition-colors flex items-center gap-2"
              >
                {exportPhase === "rendering" ? (
                  <>
                    <span className="w-3.5 h-3.5 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />
                    Rendering video...
                  </>
                ) : exportPhase === "exporting" || exportBundleLoading ? (
                  <>
                    <span className="w-3.5 h-3.5 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />
                    Exporting to iCloud...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    Export All
                  </>
                )}
              </button>
              <button
                onClick={onClose}
                className="text-neutral-400 hover:text-white transition-colors text-xl leading-none"
              >
                &times;
              </button>
            </div>
          </div>
          {exportPhase === "rendering" && youtubeStatus && (
            <div className="px-6 pb-3">
              <ProgressBar
                progress={youtubeStatus.progress}
                label={youtubeStatus.current_step}
                estimatedSeconds={youtubeStatus.estimated_seconds}
                elapsedSeconds={youtubeStatus.elapsed_seconds}
              />
            </div>
          )}
          {(exportPhase === "exporting" || exportBundleLoading) && (
            <div className="px-6 pb-3">
              <MiniProgressBar estimatedSeconds={exportBundleProgress.estimatedSeconds} active={exportBundleProgress.active} />
            </div>
          )}
        </div>

        {/* Tab Bar */}
        <div className="flex border-b border-neutral-800 px-6 shrink-0">
          {TABS.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`relative px-4 py-3 text-sm font-medium transition-colors flex items-center ${
                activeTab === tab.key
                  ? "text-violet-400"
                  : "text-neutral-500 hover:text-neutral-300"
              }`}
            >
              {tab.label}
              <TabBadge active={tabBadges[tab.key]} />
              {activeTab === tab.key && (
                <span className="absolute bottom-0 left-2 right-2 h-0.5 bg-violet-500 rounded-full" />
              )}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        <div className="p-6 overflow-y-auto flex-1">
          {/* Render Tab */}
          {activeTab === "render" && (
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
                    <DownloadButton url={youtubeUrl} label="Download YouTube Video" projectTitle={projectTitle} filename={`${projectTitle}.mp4`} />
                  </div>
                ) : youtubeStatus?.status === "failed" ? (
                  <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                    Render failed: {youtubeStatus.error ?? "Unknown error"}
                  </div>
                ) : null}
                {!youtubeRendering && (
                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => onStartYoutubeRender()}
                      className="text-sm px-4 py-2 bg-violet-600 hover:bg-violet-500 rounded-lg font-medium transition-colors"
                    >
                      {youtubeUrl ? "Re-render" : "Render YouTube Video"}
                    </button>
                    <button
                      onClick={() => onStartYoutubeRender(1.25)}
                      className="text-sm px-4 py-2 bg-violet-600 hover:bg-violet-500 rounded-lg font-medium transition-colors"
                    >
                      {youtubeUrl ? "Re-render (1.25x)" : "Render YouTube Video (1.25x Speed)"}
                    </button>
                    {estimatedSeconds != null && !youtubeUrl && (
                      <span className="text-xs text-neutral-500">
                        Estimated render time: {formatDuration(estimatedSeconds, true)}
                      </span>
                    )}
                  </div>
                )}
              </section>
            </div>
          )}

          {/* Thumbnails Tab */}
          {activeTab === "thumbnails" && (
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
                          <DownloadButton url={t.image_url} label="Download" projectTitle={projectTitle} filename="thumbnail.png" />
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

          {/* SEO Tab */}
          {activeTab === "seo" && (
            <section className="space-y-3">
              <h3 className="text-sm font-semibold text-neutral-300 uppercase tracking-wider">
                SEO Metadata
              </h3>

              {seoMetadata && (
                <div className="space-y-4">
                  {/* YouTube */}
                  <div className="bg-neutral-800/50 rounded-lg p-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-semibold text-neutral-400 uppercase">YouTube</span>
                      <CopyButton text={`Title:\n${seoMetadata.youtube.title}\n\nDescription:\n${seoMetadata.youtube.description}\n\nTags:\n${seoMetadata.youtube.tags.join(", ")}`} />
                    </div>
                    <p className="text-sm font-medium text-neutral-200">{seoMetadata.youtube.title}</p>
                    <p className="text-xs text-neutral-400 whitespace-pre-wrap">{seoMetadata.youtube.description}</p>
                    <TagList tags={seoMetadata.youtube.tags} />
                  </div>
                </div>
              )}
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
                  "Regenerate SEO"
                ) : (
                  "Generate SEO Metadata"
                )}
              </button>
              {seoGenerating && <MiniProgressBar estimatedSeconds={seoProgress.estimatedSeconds} active={seoProgress.active} />}
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

                <button
                  onClick={handleStartUpload}
                  className="flex items-center gap-2 text-sm px-4 py-2 bg-red-600 hover:bg-red-500 rounded-lg font-medium transition-colors text-white"
                >
                  <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0C.488 3.45.029 5.804 0 12c.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0C23.512 20.55 23.971 18.196 24 12c-.029-6.185-.484-8.549-4.385-8.816zM9 16V8l8 4-8 4z" />
                  </svg>
                  Upload
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
