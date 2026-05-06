import { useCallback, useEffect, useState } from "react";
import api from "../../api";

interface RhythmData {
  avg_wpm: number;
  pace_variance: number;
  gaps: Array<{ start_ms: number; end_ms: number; duration_ms: number }>;
  fastest_5s_wpm: number;
  slowest_5s_wpm: number;
}

interface Props {
  scriptId: string;
  sceneId: string;
  takeNumber: number;
}

export default function RhythmAnalysis({ scriptId, sceneId, takeNumber }: Props) {
  const [data, setData] = useState<RhythmData | null>(null);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const fetchRhythm = useCallback(async () => {
    setLoading(true);
    const res = await api.get(`/api/recording/rhythm/${scriptId}/${sceneId}/${takeNumber}`);
    if (res.ok) {
      setData(res.data as RhythmData);
    }
    setLoading(false);
  }, [scriptId, sceneId, takeNumber]);

  useEffect(() => {
    if (expanded && !data) {
      fetchRhythm();
    }
  }, [expanded, data, fetchRhythm]);

  return (
    <div className="border-t border-neutral-800">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full px-3 py-2 text-[11px] text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800/50 transition-colors text-left flex items-center justify-between"
      >
        <span>Rhythm Analysis</span>
        <svg className={`w-3 h-3 transition-transform ${expanded ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {expanded && (
        <div className="px-3 pb-3">
          {loading && (
            <div className="flex items-center gap-2 py-2">
              <span className="w-3 h-3 border-2 border-neutral-600 border-t-neutral-300 rounded-full animate-spin" />
              <span className="text-[11px] text-neutral-500">Analyzing...</span>
            </div>
          )}

          {data && !loading && (
            <div className="space-y-2">
              {/* Stats */}
              <div className="grid grid-cols-2 gap-1.5">
                <div className="bg-neutral-800/50 rounded px-2 py-1.5">
                  <div className="text-[10px] text-neutral-500">Avg WPM</div>
                  <div className={`text-xs font-medium tabular-nums ${
                    data.avg_wpm >= 130 && data.avg_wpm <= 160 ? "text-emerald-400" : "text-neutral-300"
                  }`}>
                    {data.avg_wpm}
                  </div>
                </div>
                <div className="bg-neutral-800/50 rounded px-2 py-1.5">
                  <div className="text-[10px] text-neutral-500">Variance</div>
                  <div className="text-xs font-medium text-neutral-300 tabular-nums">{data.pace_variance}ms</div>
                </div>
                <div className="bg-neutral-800/50 rounded px-2 py-1.5">
                  <div className="text-[10px] text-neutral-500">Fastest 5s</div>
                  <div className={`text-xs font-medium tabular-nums ${data.fastest_5s_wpm > 180 ? "text-red-400" : "text-neutral-300"}`}>
                    {data.fastest_5s_wpm} wpm
                  </div>
                </div>
                <div className="bg-neutral-800/50 rounded px-2 py-1.5">
                  <div className="text-[10px] text-neutral-500">Slowest 5s</div>
                  <div className={`text-xs font-medium tabular-nums ${data.slowest_5s_wpm < 100 ? "text-sky-400" : "text-neutral-300"}`}>
                    {data.slowest_5s_wpm} wpm
                  </div>
                </div>
              </div>

              {/* Gaps */}
              {data.gaps.length > 0 && (
                <div>
                  <div className="text-[10px] text-neutral-500 mb-1">Gaps ({data.gaps.length})</div>
                  <div className="space-y-0.5 max-h-20 overflow-y-auto">
                    {data.gaps.map((gap, i) => (
                      <div
                        key={i}
                        className={`text-[10px] tabular-nums px-1.5 py-0.5 rounded ${
                          gap.duration_ms > 1000 ? "bg-red-500/10 text-red-400" : "bg-amber-500/10 text-amber-400"
                        }`}
                      >
                        {(gap.start_ms / 1000).toFixed(1)}s — {gap.duration_ms}ms
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {data.gaps.length === 0 && (
                <div className="text-[10px] text-emerald-400">No long gaps detected</div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
