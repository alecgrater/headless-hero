import { useState } from "react";
import { assetUrl } from "../../api";
import type { RenderStatusResponse } from "../../types/render";

interface Props {
  youtubeStatus: RenderStatusResponse | null;
  youtubeUrl: string | null;
  estimatedSeconds: number | null;
  onStartRender: (fadeOut?: number, speed?: number) => void;
  onClose: () => void;
}

const SPEED_OPTIONS = [1, 1.25, 1.5, 1.75, 2];

function formatEstimate(seconds: number): string {
  if (seconds < 60) return `~${Math.round(seconds)} sec`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return secs > 0 ? `~${mins} min ${secs} sec` : `~${mins} min`;
}

export default function VideoPreviewModal({
  youtubeStatus,
  youtubeUrl,
  estimatedSeconds,
  onStartRender,
  onClose,
}: Props) {
  const [speed, setSpeed] = useState(1.0);
  const rendering = youtubeStatus?.status === "running" || youtubeStatus?.status === "pending";
  const failed = youtubeStatus?.status === "failed";

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-8" onClick={onClose}>
      <div
        className="bg-neutral-900 border border-neutral-800 rounded-2xl w-full max-w-3xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-800">
          <h2 className="text-lg font-bold">Full Video Preview</h2>
          <button
            onClick={onClose}
            className="text-neutral-400 hover:text-white transition-colors text-xl leading-none"
          >
            &times;
          </button>
        </div>

        <div className="p-6 space-y-4">
          {/* Video player when complete */}
          {youtubeUrl && !rendering && (
            <video
              src={assetUrl(youtubeUrl)}
              controls
              autoPlay
              className="w-full rounded-lg border border-neutral-700"
              style={{ maxHeight: "60vh" }}
            />
          )}

          {/* Progress bar when rendering */}
          {rendering && youtubeStatus && (
            <div className="space-y-2 py-8">
              <div className="flex justify-between text-xs text-neutral-400">
                <span>{youtubeStatus.current_step}</span>
                <span>{Math.round(youtubeStatus.progress * 100)}%</span>
              </div>
              <div className="w-full h-2 bg-neutral-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-violet-500 rounded-full transition-all duration-300"
                  style={{ width: `${youtubeStatus.progress * 100}%` }}
                />
              </div>
            </div>
          )}

          {/* Error state */}
          {failed && (
            <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/30 rounded-lg p-3">
              Render failed: {youtubeStatus?.error ?? "Unknown error"}
            </div>
          )}

          {/* Speed selector */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-neutral-500 mr-1">Speed:</span>
            {SPEED_OPTIONS.map((s) => (
              <button
                key={s}
                onClick={() => setSpeed(s)}
                className={`text-xs px-2.5 py-1 rounded-full font-medium transition-colors ${
                  speed === s
                    ? "bg-violet-600 text-white"
                    : "bg-neutral-800 text-neutral-400 hover:bg-neutral-700"
                }`}
              >
                {s}x
              </button>
            ))}
          </div>

          {/* Render / Re-render button */}
          {!rendering && (
            <div className="flex items-center gap-3">
              <button
                onClick={() => onStartRender(0.3, speed)}
                className="text-sm px-4 py-2 bg-violet-600 hover:bg-violet-500 rounded-lg font-medium transition-colors"
              >
                {youtubeUrl ? "Re-render" : "Render Preview"}{speed !== 1 ? ` (${speed}x)` : ""}
              </button>
              {estimatedSeconds != null && !youtubeUrl && (
                <span className="text-xs text-neutral-500">
                  Estimated: {formatEstimate(estimatedSeconds)}
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
