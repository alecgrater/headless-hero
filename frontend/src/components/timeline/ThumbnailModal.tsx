import { useState, useEffect } from "react";
import { assetUrl } from "../../api";
import type { ThumbnailConcept } from "../../types/render";

interface Props {
  thumbnails: ThumbnailConcept[];
  generating: boolean;
  onGenerate: () => void;
  onClose: () => void;
}

export default function ThumbnailModal({ thumbnails, generating, onGenerate, onClose }: Props) {
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
      <div className="bg-neutral-900 border border-neutral-700 rounded-xl shadow-2xl p-6 max-w-4xl w-full mx-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-neutral-100">Thumbnails</h3>
          <button
            onClick={onClose}
            className="text-neutral-500 hover:text-neutral-300 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Thumbnail grid */}
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
            <svg className="w-10 h-10 mb-3 text-neutral-600" fill="none" viewBox="0 0 24 24" strokeWidth={1} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="m2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0 0 22.5 18.75V5.25A2.25 2.25 0 0 0 20.25 3H3.75A2.25 2.25 0 0 0 1.5 5.25v13.5A2.25 2.25 0 0 0 3.75 21z" />
            </svg>
            <p className="text-sm">No thumbnails yet</p>
            <p className="text-xs text-neutral-600 mt-1">Generate 3 YouTube thumbnail concepts</p>
          </div>
        ) : null}

        {/* Generating indicator */}
        {generating && (
          <div className="flex items-center justify-center gap-3 py-8">
            <span className="w-5 h-5 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-sm text-neutral-300">Generating thumbnail concepts...</span>
          </div>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-3 pt-2 border-t border-neutral-800">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm rounded-lg text-neutral-400 hover:bg-neutral-800 transition-colors"
          >
            Close
          </button>
          <button
            onClick={onGenerate}
            disabled={generating}
            className={`px-4 py-2 text-sm rounded-lg font-medium transition-colors ${
              generating
                ? "bg-neutral-800 text-neutral-500 cursor-not-allowed"
                : "bg-violet-600 hover:bg-violet-500 text-white"
            }`}
          >
            {thumbnails.length > 0 ? "Regenerate Thumbnails" : "Generate Thumbnails"}
          </button>
        </div>
      </div>

      {/* Lightbox overlay */}
      {selectedUrl && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/80"
          onClick={() => setSelectedUrl(null)}
        >
          <button
            onClick={() => setSelectedUrl(null)}
            className="absolute top-4 right-4 text-neutral-400 hover:text-white transition-colors"
          >
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
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
