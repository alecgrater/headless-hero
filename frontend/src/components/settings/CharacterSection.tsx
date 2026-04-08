import { useCallback, useEffect, useState } from "react";
import {
  assetUrl,
  generateCharacterFrames,
  getCharacterFrames,
  getCharacterStatus,
  regenerateCharacterFrame,
} from "../../api";

interface FrameEntry {
  id: string;
  file_closed: string;
  file_open: string;
  expression: string;
  pose: string;
  gesture: string;
}

interface Manifest {
  canonical_frame: string | null;
  generated_at: string | null;
  frames: FrameEntry[];
}

export default function CharacterSection() {
  const [manifest, setManifest] = useState<Manifest | null>(null);
  const [loading, setLoading] = useState(true);
  const [jobId, setJobId] = useState<string | null>(null);
  const [progress, setProgress] = useState({ completed: 0, total: 0, current_label: "" });
  const [regeneratingId, setRegeneratingId] = useState<string | null>(null);

  const fetchManifest = useCallback(async () => {
    const res = await getCharacterFrames();
    if (res.ok) {
      setManifest(res.data as Manifest);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchManifest();
  }, [fetchManifest]);

  // Poll job status
  useEffect(() => {
    if (!jobId) return;
    const interval = setInterval(async () => {
      const res = await getCharacterStatus(jobId);
      if (!res.ok) return;
      const status = res.data as {
        status: string;
        completed: number;
        total: number;
        current_label: string;
      };
      setProgress({
        completed: status.completed,
        total: status.total,
        current_label: status.current_label,
      });
      if (status.status === "completed" || status.status === "failed") {
        setJobId(null);
        fetchManifest();
      }
    }, 2000);
    return () => clearInterval(interval);
  }, [jobId, fetchManifest]);

  const handleGenerate = async () => {
    const result = await generateCharacterFrames();
    setJobId(result.job_id);
    setProgress({ completed: 0, total: 50, current_label: "Starting..." });
  };

  const handleRegenerate = async (frameId: string) => {
    setRegeneratingId(frameId);
    await regenerateCharacterFrame(frameId);
    await fetchManifest();
    setRegeneratingId(null);
  };

  const frameCount = manifest?.frames?.length ?? 0;
  const isGenerating = !!jobId;
  const pct = progress.total > 0 ? progress.completed / progress.total : 0;

  // Group frames by expression
  const grouped = (manifest?.frames ?? []).reduce(
    (acc, frame) => {
      const key = frame.expression;
      if (!acc[key]) acc[key] = [];
      acc[key].push(frame);
      return acc;
    },
    {} as Record<string, FrameEntry[]>,
  );

  if (loading) {
    return (
      <div className="p-6">
        <div className="text-neutral-400 text-sm">Loading character data...</div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-neutral-100">Eli Character Frames</h2>
        <p className="text-sm text-neutral-400 mt-1">
          Pre-generated character overlay frames for video rendering. Each pose has open and closed mouth variants.
        </p>
      </div>

      {/* Status + Actions */}
      <div className="flex items-center gap-4">
        <div className="text-sm text-neutral-300">
          {frameCount > 0 ? (
            <span className="text-emerald-400">{frameCount * 2} frames generated</span>
          ) : (
            <span className="text-neutral-500">No frames generated yet</span>
          )}
        </div>

        <div className="flex gap-2">
          <button
            onClick={handleGenerate}
            disabled={isGenerating}
            className="text-sm px-4 py-2 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg font-medium transition-colors"
          >
            {isGenerating ? "Generating..." : frameCount > 0 ? "Regenerate All" : "Generate Frames"}
          </button>
        </div>
      </div>

      {/* Progress bar */}
      {isGenerating && (
        <div className="space-y-2">
          <div className="flex items-center gap-3 text-xs text-neutral-300">
            <span className="w-3 h-3 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
            <span>
              {progress.completed} / {progress.total} frames
            </span>
            <span className="text-neutral-500">{progress.current_label}</span>
          </div>
          <div className="h-1.5 bg-neutral-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-violet-500 rounded-full transition-all duration-300"
              style={{ width: `${pct * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* Frame grid grouped by expression */}
      {Object.entries(grouped).map(([expression, frames]) => (
        <div key={expression}>
          <h3 className="text-sm font-medium text-neutral-300 mb-2 capitalize">{expression}</h3>
          <div className="grid grid-cols-4 gap-3">
            {frames.map((frame) => (
              <div
                key={frame.id}
                className="group relative bg-neutral-800 rounded-lg overflow-hidden border border-neutral-700/50 hover:border-neutral-600 transition-colors"
              >
                <div className="flex">
                  <img
                    src={assetUrl(`/static/character/frames/${frame.file_closed}`)}
                    alt={`${frame.id} closed`}
                    className="w-1/2 aspect-square object-cover"
                  />
                  <img
                    src={assetUrl(`/static/character/frames/${frame.file_open}`)}
                    alt={`${frame.id} open`}
                    className="w-1/2 aspect-square object-cover"
                  />
                </div>
                <div className="px-2 py-1.5">
                  <div className="text-[10px] text-neutral-400 truncate">{frame.pose}</div>
                  {frame.gesture !== "none" && (
                    <div className="text-[9px] text-neutral-500">{frame.gesture}</div>
                  )}
                </div>
                {/* Regenerate overlay */}
                <button
                  onClick={() => handleRegenerate(frame.id)}
                  disabled={regeneratingId === frame.id}
                  className="absolute inset-0 flex items-center justify-center bg-black/60 opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <span className="text-xs text-neutral-200 font-medium">
                    {regeneratingId === frame.id ? "Regenerating..." : "Regenerate"}
                  </span>
                </button>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
