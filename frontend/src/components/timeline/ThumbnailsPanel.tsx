import { useState } from "react";
import { ChevronLeft, ChevronRight, Download, Star } from "lucide-react";
import { assetUrl } from "../../api";
import type { ThumbnailConcept, ThumbnailLabelStyle } from "../../types/render";
import MiniProgressBar from "../MiniProgressBar";
import ThumbnailLabelStyleToggle from "./ThumbnailLabelStyleToggle";

export function LongFormThumbnailsPanel({
  thumbnails,
  generating,
  onGenerate,
  onExport,
  exporting,
  progress,
  formatId,
  thumbnailLabelStyle,
  onThumbnailLabelStyleChange,
  onSetActiveThumbnail,
}: {
  thumbnails: ThumbnailConcept[];
  generating: boolean;
  onGenerate: () => void;
  onExport: () => void;
  exporting: boolean;
  progress: { estimatedSeconds: number | null; active: boolean };
  formatId?: string;
  thumbnailLabelStyle?: ThumbnailLabelStyle;
  onThumbnailLabelStyleChange?: (style: ThumbnailLabelStyle) => void;
  onSetActiveThumbnail?: (idx: number) => Promise<void> | void;
}) {
  const [activeIndex, setActiveIndex] = useState(0);
  const [promoting, setPromoting] = useState(false);
  const safeActiveIndex = thumbnails.length === 0 ? 0 : Math.min(activeIndex, thumbnails.length - 1);
  const activeThumbnail = thumbnails[safeActiveIndex] ?? null;
  const canFlip = thumbnails.length > 1;
  const canPromote = !!onSetActiveThumbnail
    && !!activeThumbnail
    && activeThumbnail.idx !== 0
    && !generating
    && !promoting;

  const goPrevious = () => {
    if (!canFlip) return;
    setActiveIndex((idx) => {
      const currentIndex = Math.min(idx, thumbnails.length - 1);
      return currentIndex === 0 ? thumbnails.length - 1 : currentIndex - 1;
    });
  };

  const goNext = () => {
    if (!canFlip) return;
    setActiveIndex((idx) => (Math.min(idx, thumbnails.length - 1) + 1) % thumbnails.length);
  };

  const handleSetActive = async () => {
    if (!onSetActiveThumbnail || !activeThumbnail || activeThumbnail.idx === 0) return;
    setPromoting(true);
    try {
      await onSetActiveThumbnail(activeThumbnail.idx);
      setActiveIndex(0);
    } finally {
      setPromoting(false);
    }
  };

  return (
    <div className="flex-1 overflow-y-auto p-5">
      <section className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold text-neutral-300 uppercase tracking-wider">Long-Form Thumbnails</h3>
            <p className="text-xs text-neutral-500">{thumbnails.length} concept{thumbnails.length !== 1 ? "s" : ""} available</p>
          </div>
          <div className="flex flex-wrap items-center justify-end gap-2">
            {formatId === "life-as-a"
              && thumbnailLabelStyle
              && onThumbnailLabelStyleChange && (
                <ThumbnailLabelStyleToggle
                  value={thumbnailLabelStyle}
                  onChange={onThumbnailLabelStyleChange}
                  disabled={generating}
                />
              )}
            <button
              onClick={onGenerate}
              disabled={generating}
              className="text-sm px-4 py-2 bg-amber-600 hover:bg-amber-500 disabled:opacity-40 rounded-lg font-medium transition-colors flex items-center gap-2"
            >
              {generating && <span className="w-4 h-4 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />}
              {generating ? "Regenerating..." : thumbnails.length > 0 ? "Regenerate Thumbnail" : "Generate Thumbnail"}
            </button>
            <button
              onClick={onExport}
              disabled={exporting || generating}
              className="text-sm px-4 py-2 bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 disabled:opacity-40 rounded-lg font-medium transition-colors flex items-center gap-2"
            >
              {exporting && <span className="w-4 h-4 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />}
              {exporting ? "Exporting..." : "Export"}
            </button>
          </div>
        </div>
        {generating && <MiniProgressBar estimatedSeconds={progress.estimatedSeconds} active={progress.active} />}
        {thumbnails.length > 0 ? (
          <div className="space-y-4">
            <article className="rounded-lg border border-neutral-800 bg-neutral-900/70 overflow-hidden">
              {activeThumbnail?.image_url ? (
                <img
                  src={assetUrl(activeThumbnail.image_url)}
                  alt={activeThumbnail.title_text}
                  className="w-full aspect-video object-cover"
                />
              ) : (
                <div className="w-full aspect-video bg-red-500/10 flex items-center justify-center text-xs text-red-400 p-3">
                  {activeThumbnail?.error ?? "No image generated"}
                </div>
              )}
              <div className="p-3 flex flex-wrap items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm text-neutral-200 truncate">{activeThumbnail?.title_text}</p>
                  <p className="text-xs text-neutral-500">{safeActiveIndex + 1} of {thumbnails.length}</p>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={goPrevious}
                    disabled={!canFlip}
                    className="w-8 h-8 rounded-lg bg-neutral-800 hover:bg-neutral-700 disabled:opacity-40 disabled:hover:bg-neutral-800 text-neutral-300 transition-colors flex items-center justify-center"
                    aria-label="Previous thumbnail"
                  >
                    <ChevronLeft className="w-4 h-4" />
                  </button>
                  <button
                    type="button"
                    onClick={goNext}
                    disabled={!canFlip}
                    className="w-8 h-8 rounded-lg bg-neutral-800 hover:bg-neutral-700 disabled:opacity-40 disabled:hover:bg-neutral-800 text-neutral-300 transition-colors flex items-center justify-center"
                    aria-label="Next thumbnail"
                  >
                    <ChevronRight className="w-4 h-4" />
                  </button>
                  {onSetActiveThumbnail && activeThumbnail && activeThumbnail.idx !== 0 && (
                    <button
                      type="button"
                      onClick={() => void handleSetActive()}
                      disabled={!canPromote}
                      className="h-8 px-3 rounded-lg bg-neutral-800 hover:bg-neutral-700 disabled:opacity-40 disabled:hover:bg-neutral-800 text-neutral-300 transition-colors flex items-center gap-1.5 text-xs"
                      aria-label="Set as active thumbnail"
                      title="Set as active thumbnail"
                    >
                      <Star className="w-3.5 h-3.5" />
                      <span>{promoting ? "Setting..." : "Set as active"}</span>
                    </button>
                  )}
                  {activeThumbnail?.image_url && (
                    <a
                      href={assetUrl(activeThumbnail.image_url)}
                      download
                      className="w-8 h-8 bg-neutral-800 hover:bg-neutral-700 rounded-lg text-neutral-300 transition-colors flex items-center justify-center"
                      aria-label="Download thumbnail"
                    >
                      <Download className="w-4 h-4" />
                    </a>
                  )}
                </div>
              </div>
            </article>
            {canFlip && (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {thumbnails.map((thumbnail, idx) => (
                  <button
                    key={thumbnail.idx}
                    type="button"
                    onClick={() => setActiveIndex(idx)}
                    className={`rounded-lg overflow-hidden border transition-colors ${
                      idx === safeActiveIndex
                        ? "border-violet-400 bg-violet-500/10"
                        : "border-neutral-800 bg-neutral-900/50 hover:border-neutral-600"
                    }`}
                    aria-label={`Select thumbnail ${idx + 1}`}
                  >
                    {thumbnail.image_url ? (
                      <img src={assetUrl(thumbnail.image_url)} alt={thumbnail.title_text} className="w-full aspect-video object-cover" />
                    ) : (
                      <div className="w-full aspect-video bg-red-500/10" />
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="rounded-lg border border-dashed border-neutral-800 bg-neutral-900/40 p-10 text-center">
            <p className="text-sm text-neutral-500">No long-form thumbnail concepts yet.</p>
          </div>
        )}
      </section>
    </div>
  );
}
