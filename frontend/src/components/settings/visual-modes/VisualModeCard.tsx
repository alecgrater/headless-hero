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
      title={entry.shortDescription}
      className={`group text-left rounded-lg border bg-neutral-900/60 overflow-hidden transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${
        selected
          ? "border-violet-500/80 ring-1 ring-violet-500/40 bg-neutral-900"
          : "border-neutral-800 hover:border-neutral-700 hover:bg-neutral-900"
      }`}
    >
      <div className="relative aspect-video bg-neutral-950 overflow-hidden">
        {videoFailed ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-0.5 px-2">
            <span className="text-[10px] uppercase tracking-wider text-neutral-600 text-center leading-tight">
              {entry.label}
            </span>
            <span className="text-[9px] text-neutral-700 leading-tight">preview unavailable</span>
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
      <div className="px-2.5 py-1.5">
        <div className={`text-[12px] font-semibold leading-tight truncate ${selected ? "text-neutral-100" : "text-neutral-300"}`}>
          {entry.label}
        </div>
        <div className="text-[10px] font-mono text-neutral-500 truncate">{entry.id}</div>
      </div>
    </button>
  );
}
