import { useEffect, useState } from "react";
import { Film, ImageIcon, Smartphone, X } from "lucide-react";
import { assetUrl } from "../../api";
import type { ThumbnailConcept } from "../../types/render";
import ShortFormThumbnailsCard from "./short-form/ShortFormThumbnailsCard";

interface Props {
  thumbnails: ThumbnailConcept[];
  generating: boolean;
  onGenerate: () => void;
  onClose: () => void;
  scriptId: string;
  segments: { name: string }[];
}

type ThumbnailTab = "long-form" | "short-form";

const THUMBNAIL_TABS: { key: ThumbnailTab; label: string; Icon: typeof Film }[] = [
  { key: "long-form", label: "Long Form", Icon: Film },
  { key: "short-form", label: "Short Form", Icon: Smartphone },
];

export default function ThumbnailModal({
  thumbnails,
  generating,
  onGenerate,
  onClose,
  scriptId,
  segments,
}: Props) {
  const [activeTab, setActiveTab] = useState<ThumbnailTab>("long-form");
  const [selectedUrl, setSelectedUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedUrl) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setSelectedUrl(null);
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [selectedUrl]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-neutral-900 border border-neutral-700 rounded-xl shadow-2xl max-w-4xl max-h-[90vh] w-full mx-4 flex flex-col overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-800 shrink-0">
          <div>
            <h3 className="text-lg font-semibold text-neutral-100">Thumbnails</h3>
            <p className="mt-0.5 text-xs text-neutral-500">
              Generate cover art for long-form and short-form uploads.
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg text-neutral-500 hover:text-neutral-100 hover:bg-neutral-800 transition-colors flex items-center justify-center"
            aria-label="Close thumbnails window"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="px-6 py-4 shrink-0 border-b border-neutral-800 bg-neutral-950/25">
          <div className="inline-flex rounded-xl border border-neutral-800 bg-neutral-950/70 p-1">
            {THUMBNAIL_TABS.map((tab) => {
              const Icon = tab.Icon;
              return (
                <button
                  key={tab.key}
                  onClick={() => setActiveTab(tab.key)}
                  className={`h-9 min-w-32 px-4 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2 ${
                    activeTab === tab.key
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
        </div>

        <div className="px-6 py-3 text-xs text-neutral-400 border-b border-neutral-800/50 shrink-0 bg-neutral-900">
          {activeTab === "long-form"
            ? "Generate and preview the 16:9 YouTube thumbnail for this video."
            : "Generate vertical 9:16 short-form thumbnail covers from each segment title-card image."}
        </div>

        <div className="p-6 overflow-y-auto flex-1">
          {activeTab === "long-form" ? (
            <>
              {thumbnails.length > 0 ? (
                <div className="grid gap-4 mb-4" style={{ gridTemplateColumns: `repeat(${Math.min(thumbnails.length, 3)}, 1fr)` }}>
                  {thumbnails.map((t) => (
                    <div key={t.idx} className="space-y-1.5">
                      {t.image_url ? (
                        <div className="relative group">
                          <img
                            src={assetUrl(t.image_url)}
                            alt={t.title_text}
                            onClick={() => setSelectedUrl(assetUrl(t.image_url!))}
                            className="w-full aspect-video object-cover rounded-lg border border-neutral-700 cursor-pointer hover:border-violet-500 transition-colors"
                          />
                          <a
                            href={assetUrl(t.image_url)}
                            download
                            className="absolute bottom-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity bg-black/70 text-neutral-200 text-[10px] px-2 py-1 rounded-md hover:bg-black/90"
                          >
                            Download
                          </a>
                        </div>
                      ) : t.error ? (
                        <div className="w-full aspect-video bg-red-500/10 rounded-lg flex items-center justify-center text-xs text-red-400 border border-red-500/20">
                          Error generating
                        </div>
                      ) : null}
                      <p className="text-[11px] text-neutral-400 truncate">{t.title_text}</p>
                      <p className="text-[10px] text-neutral-600 line-clamp-2">{t.visual_description}</p>
                    </div>
                  ))}
                </div>
              ) : !generating ? (
                <div className="flex flex-col items-center justify-center py-12 text-neutral-500">
                  <ImageIcon className="w-10 h-10 mb-3 text-neutral-600" strokeWidth={1} />
                  <p className="text-sm">No thumbnails yet</p>
                  <p className="text-xs text-neutral-600 mt-1">Generate 3 YouTube thumbnail concepts</p>
                </div>
              ) : null}

              {generating && (
                <div className="flex items-center justify-center gap-3 py-8">
                  <span className="w-5 h-5 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
                  <span className="text-sm text-neutral-300">Generating thumbnail concepts...</span>
                </div>
              )}
            </>
          ) : (
            <ShortFormThumbnailsCard scriptId={scriptId} segments={segments} />
          )}
        </div>

        <div className="flex justify-end gap-3 px-6 py-4 border-t border-neutral-800 shrink-0">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-lg text-neutral-400 hover:bg-neutral-800 transition-colors"
          >
            Close
          </button>
          {activeTab === "long-form" && (
            <button
              onClick={onGenerate}
              disabled={generating}
              className={`px-4 py-2 text-sm rounded-lg font-medium transition-colors ${
                generating
                  ? "bg-neutral-800 text-neutral-500 cursor-not-allowed"
                  : "bg-violet-600 hover:bg-violet-500 text-white"
              }`}
            >
              {thumbnails.length > 0 ? "Regenerate Thumbnail" : "Generate Thumbnail"}
            </button>
          )}
        </div>
      </div>

      {selectedUrl && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/80"
          onClick={() => setSelectedUrl(null)}
        >
          <button
            onClick={() => setSelectedUrl(null)}
            className="absolute top-4 right-4 text-neutral-400 hover:text-white transition-colors"
            aria-label="Close thumbnail preview"
          >
            <X className="w-8 h-8" />
          </button>
          <img
            src={selectedUrl}
            alt="Thumbnail preview"
            className="max-w-[90vw] max-h-[90vh] object-contain rounded-lg"
            onClick={(e) => e.stopPropagation()}
          />
        </div>
      )}
    </div>
  );
}
