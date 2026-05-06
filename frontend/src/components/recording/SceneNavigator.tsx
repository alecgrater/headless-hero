import type { ScriptContent } from "../../types/script";

interface SceneItem {
  segmentIndex: number;
  sceneIndex: number;
  sceneId: string;
  narration: string;
}

export interface SceneScore {
  overall: number;
  dimensions: Record<string, { score: number; note: string }>;
  recommendation: string;
}

interface Props {
  content: ScriptContent;
  activeSceneId: string | null;
  onSelectScene: (sceneId: string) => void;
  recordedScenes: Set<string>;
  flaggedScenes: Set<string>;
  filter: "all" | "unrecorded" | "flagged" | "low-score";
  onFilterChange: (filter: "all" | "unrecorded" | "flagged" | "low-score") => void;
  scores?: Record<string, SceneScore>;
}

function ScoreBadge({ score }: { score: number }) {
  let color: string;
  if (score >= 8) color = "text-emerald-400 bg-emerald-500/10";
  else if (score >= 6) color = "text-amber-400 bg-amber-500/10";
  else color = "text-red-400 bg-red-500/10";

  return (
    <span className={`text-[9px] font-bold tabular-nums px-1 py-0.5 rounded ${color}`}>
      {score}
    </span>
  );
}

export default function SceneNavigator({ content, activeSceneId, onSelectScene, recordedScenes, flaggedScenes, filter, onFilterChange, scores }: Props) {
  const scenes: SceneItem[] = [];
  content.segments.forEach((seg, si) => {
    seg.scenes.forEach((sc, sci) => {
      if (sc.narration) {
        scenes.push({ segmentIndex: si + 1, sceneIndex: sci + 1, sceneId: sc.id, narration: sc.narration });
      }
    });
  });

  const filtered = scenes.filter((s) => {
    if (filter === "unrecorded") return !recordedScenes.has(s.sceneId);
    if (filter === "flagged") return flaggedScenes.has(s.sceneId);
    if (filter === "low-score") return scores?.[s.sceneId] && scores[s.sceneId].overall < 7;
    return true;
  });

  // Sort by score ascending when in low-score filter (worst first)
  const sorted = filter === "low-score"
    ? [...filtered].sort((a, b) => (scores?.[a.sceneId]?.overall ?? 10) - (scores?.[b.sceneId]?.overall ?? 10))
    : filtered;

  return (
    <div className="w-[220px] shrink-0 border-r border-neutral-800 flex flex-col h-full overflow-hidden">
      <div className="px-3 py-2 border-b border-neutral-800 flex items-center gap-1 flex-wrap">
        {(["all", "unrecorded", "flagged", "low-score"] as const).map((f) => (
          <button
            key={f}
            onClick={() => onFilterChange(f)}
            className={`text-[11px] px-2 py-1 rounded-md transition-colors capitalize ${
              filter === f ? "bg-violet-500/15 text-violet-300" : "text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800"
            }`}
          >
            {f === "low-score" ? "Needs Work" : f}
          </button>
        ))}
      </div>
      <div className="flex-1 overflow-y-auto">
        {sorted.map((s) => {
          const sceneScore = scores?.[s.sceneId];
          return (
            <button
              key={s.sceneId}
              onClick={() => onSelectScene(s.sceneId)}
              className={`w-full text-left px-3 py-2.5 border-b border-neutral-800/50 transition-colors ${
                s.sceneId === activeSceneId ? "bg-violet-500/10 border-l-2 border-l-violet-400" : "hover:bg-neutral-800/50"
              }`}
            >
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-[10px] text-neutral-500 tabular-nums">S{s.segmentIndex}.{s.sceneIndex}</span>
                {recordedScenes.has(s.sceneId) ? (
                  <svg className="w-3 h-3 text-emerald-400" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3z" />
                    <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
                  </svg>
                ) : (
                  <svg className="w-3 h-3 text-neutral-600" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z" />
                  </svg>
                )}
                {flaggedScenes.has(s.sceneId) && (
                  <svg className="w-3 h-3 text-amber-400" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M14.4 6L14 4H5v17h2v-7h5.6l.4 2h7V6h-5.6z" />
                  </svg>
                )}
                <span className="flex-1" />
                {sceneScore && <ScoreBadge score={sceneScore.overall} />}
              </div>
              <div className="text-xs text-neutral-400 truncate">{s.narration.slice(0, 50)}</div>
              {sceneScore && sceneScore.overall < 7 && (
                <div className="text-[10px] text-neutral-500 mt-0.5 truncate">{sceneScore.recommendation}</div>
              )}
            </button>
          );
        })}
        {sorted.length === 0 && (
          <div className="px-3 py-6 text-center text-xs text-neutral-600">
            {filter === "unrecorded" ? "All scenes recorded!" : filter === "flagged" ? "No flagged scenes" : filter === "low-score" ? "All scenes scored 7+ (or not yet scored)" : "No narrated scenes"}
          </div>
        )}
      </div>
      <div className="px-3 py-2 border-t border-neutral-800 text-[11px] text-neutral-500 tabular-nums">
        {recordedScenes.size}/{scenes.length} recorded
      </div>
    </div>
  );
}
