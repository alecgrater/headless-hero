import { useCallback, useState } from "react";
import api from "../../api";

interface DurationChange {
  scene_id: string;
  old_duration: number;
  new_duration: number;
}

interface Props {
  scriptId: string;
  recordedCount: number;
  onClose: () => void;
  onExported: () => void;
}

export default function ExportSection({ scriptId, recordedCount, onClose, onExported }: Props) {
  const [exporting, setExporting] = useState(false);
  const [result, setResult] = useState<{ scenes_exported: number; total_duration_seconds: number; duration_changed_scenes: DurationChange[] } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [normalizeLoudness, setNormalizeLoudness] = useState(true);

  const handleExport = useCallback(async () => {
    setExporting(true);
    setError(null);

    // Save loudness preference to session settings before export
    const sessionRes = await api.get(`/api/recording/session/${scriptId}`);
    if (sessionRes.ok) {
      const sessionData = sessionRes.data as Record<string, unknown>;
      const settings = (sessionData.settings as Record<string, unknown>) || {};
      settings.normalize_loudness = normalizeLoudness;
      await api.put(`/api/recording/session/${scriptId}`, { ...sessionData, settings });
    }

    const res = await api.post(`/api/recording/export/${scriptId}`);
    setExporting(false);
    if (res.ok) {
      setResult(res.data as { scenes_exported: number; total_duration_seconds: number; duration_changed_scenes: DurationChange[] });
    } else {
      const data = res.data as { detail?: string };
      setError(data.detail || "Export failed");
    }
  }, [scriptId, normalizeLoudness]);

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center" onClick={onClose}>
      <div className="bg-neutral-900 border border-neutral-700 rounded-xl shadow-2xl w-[420px] p-6" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold text-neutral-100 mb-4">Export Voiceover</h2>

        {!result ? (
          <>
            <p className="text-sm text-neutral-400 mb-4">
              This will convert {recordedCount} selected take{recordedCount !== 1 ? "s" : ""} to MP3, run word alignment, and update the project audio. The downstream pipeline (subtitles, FX, Eli) will use these recordings.
            </p>

            {/* Audio processing options */}
            <div className="mb-4 p-3 bg-neutral-800/50 rounded-lg">
              <div className="text-xs font-medium text-neutral-300 mb-2">Audio Processing</div>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={normalizeLoudness}
                  onChange={(e) => setNormalizeLoudness(e.target.checked)}
                  className="w-3.5 h-3.5 rounded border-neutral-600 text-violet-500 focus:ring-violet-500 bg-neutral-700"
                />
                <span className="text-xs text-neutral-400">Normalize loudness (-16 LUFS)</span>
              </label>
            </div>

            {error && <p className="text-sm text-red-400 mb-4">{error}</p>}
            <div className="flex items-center gap-3">
              <button
                onClick={handleExport}
                disabled={exporting}
                className="flex-1 py-2.5 bg-violet-500 text-white rounded-lg font-medium text-sm hover:bg-violet-600 transition-colors disabled:opacity-60"
              >
                {exporting ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="w-3.5 h-3.5 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                    Exporting...
                  </span>
                ) : (
                  "Export Voiceover"
                )}
              </button>
              <button
                onClick={onClose}
                disabled={exporting}
                className="px-4 py-2.5 text-neutral-400 hover:text-neutral-200 rounded-lg text-sm transition-colors"
              >
                Cancel
              </button>
            </div>
          </>
        ) : (
          <>
            <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-lg p-4 mb-4">
              <div className="text-emerald-300 font-medium mb-1">Export Complete</div>
              <div className="text-sm text-neutral-400">
                {result.scenes_exported} scene{result.scenes_exported !== 1 ? "s" : ""} exported ({Math.round(result.total_duration_seconds)}s total)
              </div>
              <div className="text-xs text-neutral-500 mt-1">Word timestamps aligned. Return to timeline to verify.</div>
            </div>

            {/* Duration change warnings */}
            {result.duration_changed_scenes.length > 0 && (
              <div className="bg-amber-500/10 border border-amber-500/20 rounded-lg p-3 mb-4">
                <div className="text-xs font-medium text-amber-300 mb-1">
                  Duration changed in {result.duration_changed_scenes.length} scene{result.duration_changed_scenes.length !== 1 ? "s" : ""}
                </div>
                <div className="text-xs text-neutral-400 mb-2">
                  Micro-timeline timings (frame_timings, visual in/out) may need rescaling.
                </div>
                {result.duration_changed_scenes.slice(0, 5).map((ch) => (
                  <div key={ch.scene_id} className="text-[11px] text-neutral-500 tabular-nums">
                    {ch.scene_id.slice(0, 8)}... {ch.old_duration.toFixed(1)}s → {ch.new_duration.toFixed(1)}s
                  </div>
                ))}
              </div>
            )}

            <button
              onClick={onExported}
              className="w-full py-2.5 bg-neutral-800 border border-neutral-700 text-neutral-200 rounded-lg font-medium text-sm hover:bg-neutral-700 transition-colors"
            >
              Return to Timeline
            </button>
          </>
        )}
      </div>
    </div>
  );
}
