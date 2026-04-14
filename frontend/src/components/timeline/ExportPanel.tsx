import { useState } from "react";
import { assetUrl, openInBrowser } from "../../api";
import type { PublishRecord } from "../../types/publish";
import type { RenderStatusResponse, SEOMetadata, ThumbnailConcept } from "../../types/render";

interface Props {
  youtubeStatus: { status: string; progress: number; current_step: string; error?: string } | null;
  youtubeUrl: string | null;
  onStartYoutubeRender: () => void;

  audioUrl: string | null;
  audioExporting: boolean;
  onExportAudio: () => void;

  thumbnails: ThumbnailConcept[];
  thumbnailsGenerating: boolean;
  onRecompositeThumbnail: () => void;
  onRecompositeThumbnailWithoutEli: () => void;

  seoMetadata: SEOMetadata | null;
  seoGenerating: boolean;
  onGenerateSEO: () => void;

  // Publishing
  youtubeConnected: boolean;
  youtubeChannelName: string;
  onConnectYouTube: () => void;
  connecting: boolean;
  publishStatus: RenderStatusResponse | null;
  onStartPublish: (
    platform: string,
    fileUrl: string,
    metadata: { title: string; description: string; tags: string[] },
    scheduleAt?: string,
  ) => void;
  publishHistory: PublishRecord[];

  // Render estimate
  estimatedSeconds: number | null;

  onClose: () => void;
}

type Tab = "render" | "thumbnails" | "seo" | "publish" | "audio";

const TABS: { key: Tab; label: string }[] = [
  { key: "render", label: "Render" },
  { key: "thumbnails", label: "Thumbnails" },
  { key: "seo", label: "SEO" },
  { key: "publish", label: "Publish" },
  { key: "audio", label: "Audio" },
];

function formatEstimate(seconds: number): string {
  if (seconds < 60) return `~${Math.round(seconds)} sec`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return secs > 0 ? `~${mins} min ${secs} sec` : `~${mins} min`;
}

function ProgressBar({ progress, label, estimatedSeconds }: { progress: number; label: string; estimatedSeconds?: number }) {
  // Compute remaining time from estimated_seconds and progress
  const remaining = estimatedSeconds && progress > 0 && progress < 1
    ? Math.max(0, Math.round(estimatedSeconds * (1 - progress)))
    : null;
  const etaStr = remaining !== null && remaining > 0
    ? remaining >= 60
      ? `~${Math.ceil(remaining / 60)}m remaining`
      : `~${remaining}s remaining`
    : null;

  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-neutral-400">
        <span>{label}</span>
        <span className="flex items-center gap-2">
          {etaStr && <span className="text-neutral-500">{etaStr}</span>}
          {Math.round(progress * 100)}%
        </span>
      </div>
      <div className="w-full h-2 bg-neutral-800 rounded-full overflow-hidden">
        <div
          className="h-full bg-violet-500 rounded-full transition-all duration-300"
          style={{ width: `${progress * 100}%` }}
        />
      </div>
    </div>
  );
}

function DownloadButton({ url, label }: { url: string; label: string }) {
  const [downloading, setDownloading] = useState(false);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const fullUrl = assetUrl(url);
      const filename = url.split("/").pop() || "download";

      // Use Electron native save dialog if available
      if (window.api?.downloadFile) {
        await window.api.downloadFile(fullUrl, filename);
        return;
      }

      // Fallback for browser dev mode
      const response = await fetch(fullUrl);
      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = filename;
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

export default function ExportPanel({
  youtubeStatus,
  youtubeUrl,
  onStartYoutubeRender,
  audioUrl,
  audioExporting,
  onExportAudio,
  thumbnails,
  thumbnailsGenerating,
  onRecompositeThumbnail,
  onRecompositeThumbnailWithoutEli,
  seoMetadata,
  seoGenerating,
  onGenerateSEO,
  youtubeConnected,
  youtubeChannelName,
  onConnectYouTube,
  connecting,
  publishStatus,
  onStartPublish,
  publishHistory,
  estimatedSeconds,

  onClose,
}: Props) {
  const youtubeRendering = youtubeStatus?.status === "running" || youtubeStatus?.status === "pending";
  const publishing = publishStatus?.status === "running" || publishStatus?.status === "pending";

  const [activeTab, setActiveTab] = useState<Tab>("render");
  const [scheduleAt, setScheduleAt] = useState("");
  const [confirmPublish, setConfirmPublish] = useState(false);

  // Latest YouTube publish from history
  const latestYtPublish = publishHistory.find(
    (r) => r.platform === "youtube" && (r.status === "published" || r.status === "scheduled"),
  );

  // Badge indicators
  const tabBadges: Record<Tab, boolean> = {
    render: !!youtubeUrl,
    thumbnails: thumbnails.length > 0,
    seo: !!seoMetadata,
    publish: publishHistory.some((r) => r.status === "published" || r.status === "scheduled"),
    audio: !!audioUrl,
  };

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-8">
      <div className="bg-neutral-900 border border-neutral-800 rounded-2xl w-full max-w-4xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-800 shrink-0">
          <h2 className="text-lg font-bold">Export & Publish</h2>
          <button
            onClick={onClose}
            className="text-neutral-400 hover:text-white transition-colors text-xl leading-none"
          >
            &times;
          </button>
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
                  <ProgressBar progress={youtubeStatus.progress} label={youtubeStatus.current_step} estimatedSeconds={youtubeStatus.estimated_seconds} />
                ) : youtubeUrl ? (
                  <div className="space-y-3">
                    <video
                      src={assetUrl(youtubeUrl)}
                      controls
                      className="w-full max-h-[300px] rounded-lg border border-neutral-700"
                    />
                    <DownloadButton url={youtubeUrl} label="Download YouTube Video" />
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
                    {estimatedSeconds != null && !youtubeUrl && (
                      <span className="text-xs text-neutral-500">
                        Estimated render time: {formatEstimate(estimatedSeconds)}
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
                <div className="grid grid-cols-3 gap-3">
                  {thumbnails.map((t) => (
                    <div key={t.idx} className="space-y-1">
                      {t.image_url ? (
                        <>
                          <img
                            src={assetUrl(t.image_url)}
                            alt={t.title_text}
                            className="w-full aspect-video object-cover rounded-lg border border-neutral-700 cursor-pointer hover:border-violet-500 transition-colors"
                          />
                          <DownloadButton url={t.image_url} label="Download" />
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
              <div className="flex gap-2">
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
                <button
                  onClick={onRecompositeThumbnailWithoutEli}
                  disabled={thumbnailsGenerating}
                  className="text-sm px-4 py-2 bg-neutral-600 hover:bg-neutral-500 disabled:opacity-40 rounded-lg font-medium transition-colors flex items-center gap-2"
                >
                  {thumbnailsGenerating ? (
                    <>
                      <span className="w-4 h-4 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />
                      Generating...
                    </>
                  ) : (
                    "Generate Without Eli"
                  )}
                </button>
              </div>
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
                      <CopyButton text={`${seoMetadata.youtube.title}\n\n${seoMetadata.youtube.description}\n\n${seoMetadata.youtube.tags.join(", ")}`} />
                    </div>
                    <p className="text-sm font-medium text-neutral-200">{seoMetadata.youtube.title}</p>
                    <p className="text-xs text-neutral-400 whitespace-pre-wrap">{seoMetadata.youtube.description}</p>
                    <div className="flex flex-wrap gap-1">
                      {seoMetadata.youtube.tags.slice(0, 15).map((tag) => (
                        <span key={tag} className="text-[10px] px-1.5 py-0.5 bg-neutral-700 rounded text-neutral-300">
                          {tag}
                        </span>
                      ))}
                      {seoMetadata.youtube.tags.length > 15 && (
                        <span className="text-[10px] text-neutral-500">+{seoMetadata.youtube.tags.length - 15} more</span>
                      )}
                    </div>
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
            </section>
          )}

          {/* Publish Tab */}
          {activeTab === "publish" && (
            <div className="space-y-6">
              <section className="space-y-3">
                <h3 className="text-sm font-semibold text-neutral-300 uppercase tracking-wider">
                  YouTube Publish
                </h3>
                {!youtubeConnected ? (
                  <div className="space-y-2">
                    <p className="text-xs text-neutral-500">Connect your YouTube account to publish directly.</p>
                    <button
                      onClick={onConnectYouTube}
                      disabled={connecting}
                      className="text-sm px-4 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-50 rounded-lg font-medium transition-colors flex items-center gap-2"
                    >
                      {connecting ? (
                        <>
                          <span className="w-4 h-4 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />
                          Connecting...
                        </>
                      ) : (
                        "Connect YouTube"
                      )}
                    </button>
                  </div>
                ) : !youtubeUrl ? (
                  <p className="text-xs text-neutral-500">
                    Connected as <span className="text-emerald-400">{youtubeChannelName}</span>.
                    Render a YouTube video first to publish.
                  </p>
                ) : publishing ? (
                  <ProgressBar
                    progress={publishStatus?.progress ?? 0}
                    label={publishStatus?.current_step ?? "Publishing..."}
                  />
                ) : publishStatus?.status === "failed" ? (
                  <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                    Publish failed: {publishStatus.error ?? "Unknown error"}
                  </div>
                ) : latestYtPublish ? (
                  <div className="flex items-center gap-3">
                    <span className="inline-flex items-center gap-1.5 text-sm text-emerald-400">
                      <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                      {latestYtPublish.status === "scheduled" ? "Scheduled" : "Published"}
                    </span>
                    {latestYtPublish.platform_url && (
                      <button
                        onClick={() => openInBrowser(latestYtPublish.platform_url)}
                        className="text-xs text-violet-400 hover:text-violet-300 underline"
                      >
                        View on YouTube
                      </button>
                    )}
                  </div>
                ) : null}

                {youtubeConnected && youtubeUrl && !publishing && (
                  <div className="space-y-3">
                    <div className="flex items-center gap-2 text-xs text-neutral-400">
                      <span>Connected as <span className="text-emerald-400">{youtubeChannelName}</span></span>
                    </div>
                    <div className="flex items-center gap-3">
                      <label className="text-xs text-neutral-400">Schedule (optional):</label>
                      <input
                        type="datetime-local"
                        value={scheduleAt}
                        onChange={(e) => setScheduleAt(e.target.value)}
                        className="text-xs bg-neutral-800 border border-neutral-700 rounded-lg px-2 py-1.5 text-neutral-200 focus:outline-none focus:ring-1 focus:ring-violet-500"
                      />
                      {scheduleAt && (
                        <button
                          onClick={() => setScheduleAt("")}
                          className="text-xs text-neutral-500 hover:text-neutral-300"
                        >
                          Clear
                        </button>
                      )}
                    </div>

                    {confirmPublish ? (
                      <div className="bg-neutral-800/50 rounded-lg p-4 space-y-3">
                        <p className="text-sm text-neutral-300">
                          {scheduleAt
                            ? `Schedule video for ${new Date(scheduleAt).toLocaleString()}?`
                            : "Publish video to YouTube as private?"}
                        </p>
                        <div className="flex gap-2">
                          <button
                            onClick={() => {
                              setConfirmPublish(false);
                              const metadata = seoMetadata?.youtube ?? { title: "Untitled", description: "", tags: [] };
                              onStartPublish(
                                "youtube",
                                youtubeUrl,
                                metadata,
                                scheduleAt ? new Date(scheduleAt).toISOString() : undefined,
                              );
                            }}
                            className="text-sm px-4 py-2 bg-red-600 hover:bg-red-500 rounded-lg font-medium transition-colors"
                          >
                            Yes, Publish
                          </button>
                          <button
                            onClick={() => setConfirmPublish(false)}
                            className="text-sm px-4 py-2 bg-neutral-700 hover:bg-neutral-600 rounded-lg font-medium transition-colors"
                          >
                            Cancel
                          </button>
                        </div>
                      </div>
                    ) : (
                      <button
                        onClick={() => setConfirmPublish(true)}
                        className="text-sm px-4 py-2 bg-red-600 hover:bg-red-500 rounded-lg font-medium transition-colors flex items-center gap-2"
                      >
                        <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
                          <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
                        </svg>
                        {scheduleAt ? "Schedule on YouTube" : "Publish to YouTube"}
                      </button>
                    )}
                  </div>
                )}
              </section>

              {/* Publish History */}
              {publishHistory.length > 0 && (
                <section className="space-y-3">
                  <h3 className="text-sm font-semibold text-neutral-300 uppercase tracking-wider">
                    Publish History
                  </h3>
                  <div className="space-y-2">
                    {publishHistory.map((r) => (
                      <div key={r.id} className="flex items-center gap-3 bg-neutral-800/50 rounded-lg px-3 py-2 text-xs">
                        <span className="text-neutral-500 uppercase">{r.platform}</span>
                        <span
                          className={
                            r.status === "published" || r.status === "scheduled"
                              ? "text-emerald-400"
                              : r.status === "failed"
                                ? "text-red-400"
                                : "text-yellow-400"
                          }
                        >
                          {r.status}
                        </span>
                        {r.platform_url && (
                          <button
                            onClick={() => openInBrowser(r.platform_url)}
                            className="text-violet-400 hover:text-violet-300 underline"
                          >
                            View
                          </button>
                        )}
                        <span className="ml-auto text-neutral-600">
                          {new Date(r.created_at).toLocaleString()}
                        </span>
                        {r.error && (
                          <span className="text-red-400 truncate max-w-xs" title={r.error}>
                            {r.error}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </section>
              )}
            </div>
          )}

          {/* Audio Tab */}
          {activeTab === "audio" && (
            <section className="space-y-3">
              <h3 className="text-sm font-semibold text-neutral-300 uppercase tracking-wider">
                Audio Export
              </h3>
              {audioUrl && (
                <div className="space-y-2">
                  <audio src={assetUrl(audioUrl)} controls className="w-full h-10" />
                  <DownloadButton url={audioUrl} label="Download Full Audio" />
                </div>
              )}
              <button
                onClick={onExportAudio}
                disabled={audioExporting}
                className="text-sm px-4 py-2 bg-sky-600 hover:bg-sky-500 disabled:opacity-40 rounded-lg font-medium transition-colors flex items-center gap-2"
              >
                {audioExporting ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />
                    Exporting...
                  </>
                ) : audioUrl ? (
                  "Re-export Audio"
                ) : (
                  "Export Full Audio"
                )}
              </button>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
