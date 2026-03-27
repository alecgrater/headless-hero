import { useState } from "react";
import { assetUrl } from "../../api";
import type { SEOMetadata, ThumbnailConcept } from "../../types/render";

interface Props {
  youtubeStatus: { status: string; progress: number; current_step: string } | null;
  youtubeUrl: string | null;
  onStartYoutubeRender: (fadeOut?: number) => void;

  tiktokStatus: { status: string; progress: number; current_step: string } | null;
  tiktokUrls: string[];
  onStartTiktokRender: () => void;

  audioUrl: string | null;
  audioExporting: boolean;
  onExportAudio: () => void;

  thumbnails: ThumbnailConcept[];
  thumbnailsGenerating: boolean;
  onGenerateThumbnails: () => void;

  seoMetadata: SEOMetadata | null;
  seoGenerating: boolean;
  onGenerateSEO: () => void;

  onClose: () => void;
}

function ProgressBar({ progress, label }: { progress: number; label: string }) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs text-neutral-400">
        <span>{label}</span>
        <span>{Math.round(progress * 100)}%</span>
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
  return (
    <a
      href={assetUrl(url)}
      download
      className="inline-flex items-center gap-2 text-sm px-4 py-2 bg-emerald-600 hover:bg-emerald-500 rounded-lg font-medium transition-colors"
    >
      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
      </svg>
      {label}
    </a>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      }}
      className="text-xs px-2 py-1 bg-neutral-800 hover:bg-neutral-700 rounded transition-colors text-neutral-400"
    >
      {copied ? "Copied!" : "Copy"}
    </button>
  );
}

export default function ExportPanel({
  youtubeStatus,
  youtubeUrl,
  onStartYoutubeRender,
  tiktokStatus,
  tiktokUrls,
  onStartTiktokRender,
  audioUrl,
  audioExporting,
  onExportAudio,
  thumbnails,
  thumbnailsGenerating,
  onGenerateThumbnails,
  seoMetadata,
  seoGenerating,
  onGenerateSEO,
  onClose,
}: Props) {
  const youtubeRendering = youtubeStatus?.status === "running" || youtubeStatus?.status === "pending";
  const tiktokRendering = tiktokStatus?.status === "running" || tiktokStatus?.status === "pending";

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-8">
      <div className="bg-neutral-900 border border-neutral-800 rounded-2xl w-full max-w-4xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-800 sticky top-0 bg-neutral-900 z-10">
          <h2 className="text-lg font-bold">Export & Publish</h2>
          <button
            onClick={onClose}
            className="text-neutral-400 hover:text-white transition-colors text-xl leading-none"
          >
            &times;
          </button>
        </div>

        <div className="p-6 space-y-8">
          {/* YouTube Export */}
          <section className="space-y-3">
            <h3 className="text-sm font-semibold text-neutral-300 uppercase tracking-wider">
              YouTube Export (16:9)
            </h3>
            {youtubeRendering && youtubeStatus ? (
              <ProgressBar progress={youtubeStatus.progress} label={youtubeStatus.current_step} />
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
              <button
                onClick={() => onStartYoutubeRender()}
                className="text-sm px-4 py-2 bg-violet-600 hover:bg-violet-500 rounded-lg font-medium transition-colors"
              >
                {youtubeUrl ? "Re-render" : "Render YouTube Video"}
              </button>
            )}
          </section>

          {/* TikTok Export */}
          <section className="space-y-3">
            <h3 className="text-sm font-semibold text-neutral-300 uppercase tracking-wider">
              TikTok Export (9:16)
            </h3>
            {tiktokRendering && tiktokStatus ? (
              <ProgressBar progress={tiktokStatus.progress} label={tiktokStatus.current_step} />
            ) : tiktokUrls.length > 0 ? (
              <div className="grid grid-cols-3 gap-3">
                {tiktokUrls.map((url, i) => (
                  <div key={i} className="space-y-2">
                    <video
                      src={assetUrl(url)}
                      controls
                      className="w-full rounded-lg border border-neutral-700"
                    />
                    <DownloadButton url={url} label={`Segment ${i + 1}`} />
                  </div>
                ))}
              </div>
            ) : tiktokStatus?.status === "failed" ? (
              <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                Render failed: {tiktokStatus.error ?? "Unknown error"}
              </div>
            ) : null}
            {!tiktokRendering && (
              <button
                onClick={onStartTiktokRender}
                className="text-sm px-4 py-2 bg-violet-600 hover:bg-violet-500 rounded-lg font-medium transition-colors"
              >
                {tiktokUrls.length > 0 ? "Re-render" : "Render TikTok Segments"}
              </button>
            )}
          </section>

          {/* Audio Export */}
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

          {/* Thumbnails */}
          <section className="space-y-3">
            <h3 className="text-sm font-semibold text-neutral-300 uppercase tracking-wider">
              Thumbnails
            </h3>
            {thumbnails.length > 0 && (
              <div className="grid grid-cols-3 gap-3">
                {thumbnails.map((t) => (
                  <div key={t.idx} className="space-y-1">
                    {t.image_url ? (
                      <img
                        src={assetUrl(t.image_url)}
                        alt={t.title_text}
                        className="w-full aspect-video object-cover rounded-lg border border-neutral-700 cursor-pointer hover:border-violet-500 transition-colors"
                      />
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
              onClick={onGenerateThumbnails}
              disabled={thumbnailsGenerating}
              className="text-sm px-4 py-2 bg-amber-600 hover:bg-amber-500 disabled:opacity-40 rounded-lg font-medium transition-colors flex items-center gap-2"
            >
              {thumbnailsGenerating ? (
                <>
                  <span className="w-4 h-4 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />
                  Generating...
                </>
              ) : thumbnails.length > 0 ? (
                "Regenerate Thumbnails"
              ) : (
                "Generate Thumbnails"
              )}
            </button>
          </section>

          {/* SEO Metadata */}
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

                {/* TikTok */}
                <div className="bg-neutral-800/50 rounded-lg p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-neutral-400 uppercase">TikTok</span>
                    <CopyButton text={seoMetadata.tiktok.map((t) => `${t.caption} ${t.hashtags.join(" ")}`).join("\n\n")} />
                  </div>
                  {seoMetadata.tiktok.map((t, i) => (
                    <div key={i} className="text-xs text-neutral-400">
                      <span className="text-neutral-500">Seg {i + 1}:</span> {t.caption}{" "}
                      <span className="text-violet-400">{t.hashtags.join(" ")}</span>
                    </div>
                  ))}
                </div>

                {/* Instagram */}
                <div className="bg-neutral-800/50 rounded-lg p-4 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold text-neutral-400 uppercase">Instagram</span>
                    <CopyButton text={`${seoMetadata.instagram.caption}\n\n${seoMetadata.instagram.hashtags.join(" ")}`} />
                  </div>
                  <p className="text-xs text-neutral-400 whitespace-pre-wrap">{seoMetadata.instagram.caption}</p>
                  <p className="text-xs text-violet-400">{seoMetadata.instagram.hashtags.slice(0, 10).join(" ")}</p>
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
        </div>
      </div>
    </div>
  );
}
