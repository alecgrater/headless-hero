import { useState } from "react";
import type { VisualModeEntry } from "./catalog";

interface Props {
  entry: VisualModeEntry;
  selected: boolean;
  onSelect: () => void;
}

export default function VisualModeCard({ entry, selected, onSelect }: Props) {
  const [videoFailed, setVideoFailed] = useState(false);

  return (
    <button
      type="button"
      onClick={onSelect}
      className={`text-left rounded-xl border bg-neutral-900/60 overflow-hidden transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${
        selected
          ? "border-violet-500/70 bg-neutral-900"
          : "border-neutral-800 hover:border-neutral-700"
      }`}
    >
      <div className="relative aspect-video bg-neutral-950 overflow-hidden">
        {videoFailed ? (
          <div className="absolute inset-0 flex items-center justify-center bg-neutral-900">
            <span className="text-xs uppercase tracking-wider text-neutral-500">
              {entry.label} preview
            </span>
          </div>
        ) : (
          <video
            src={entry.previewSrc}
            autoPlay
            loop
            muted
            playsInline
            onError={() => setVideoFailed(true)}
            className="w-full h-full object-cover"
          />
        )}
      </div>
      <div className="p-3 space-y-1.5">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-semibold text-neutral-100">{entry.label}</span>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-neutral-800 text-neutral-400">
            {entry.id}
          </span>
        </div>
        <p className="text-xs text-neutral-400 leading-snug">{entry.shortDescription}</p>
      </div>
    </button>
  );
}
