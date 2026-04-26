import { useState } from "react";
import type { MediaAssignment } from "../../api";
import { applyMediaAssignments } from "../../api";

interface Props {
  scriptId: string;
  assignments: MediaAssignment[];
  fullHeight?: boolean;
  onApproved: () => void;
  onReanalyze: () => void;
}

const SOURCE_LABELS: Record<string, { label: string; color: string }> = {
  ai: { label: "AI", color: "bg-violet-500/20 text-violet-300" },
  gameplay_video: { label: "Gameplay", color: "bg-emerald-500/20 text-emerald-300" },
  stock_photo: { label: "Stock Photo", color: "bg-sky-500/20 text-sky-300" },
};

export default function MediaReviewPanel({ scriptId, assignments: initial, fullHeight, onApproved, onReanalyze }: Props) {
  const [assignments, setAssignments] = useState<MediaAssignment[]>(initial);
  const [applying, setApplying] = useState(false);

  const summary = assignments.reduce<Record<string, number>>((acc, a) => {
    acc[a.media_source] = (acc[a.media_source] || 0) + 1;
    return acc;
  }, {});

  const totalScenes = assignments.length;

  const handleSourceChange = (sceneId: string, newSource: "ai" | "gameplay_video" | "stock_photo") => {
    setAssignments((prev) =>
      prev.map((a) =>
        a.scene_id === sceneId
          ? { ...a, media_source: newSource, game_name: newSource === "gameplay_video" ? a.game_name : null, search_query: newSource === "stock_photo" ? a.search_query : null }
          : a,
      ),
    );
  };

  const handleFieldChange = (sceneId: string, field: "game_name" | "search_query", value: string) => {
    setAssignments((prev) =>
      prev.map((a) => (a.scene_id === sceneId ? { ...a, [field]: value || null } : a)),
    );
  };

  const handleApprove = async () => {
    setApplying(true);
    const res = await applyMediaAssignments(scriptId, assignments);
    setApplying(false);
    if (res.ok) {
      onApproved();
    }
  };

  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-neutral-800 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-neutral-200">Media Source Review</h3>
          <p className="text-xs text-neutral-500 mt-0.5">
            {totalScenes} scenes: {Object.entries(summary).map(([src, count]) => `${count} ${SOURCE_LABELS[src]?.label ?? src}`).join(", ")}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onReanalyze}
            className="px-3 py-1.5 text-xs bg-neutral-800 hover:bg-neutral-700 rounded-lg transition-colors text-neutral-300"
          >
            Re-analyze
          </button>
          <button
            onClick={handleApprove}
            disabled={applying}
            className="px-3 py-1.5 text-xs bg-violet-600 hover:bg-violet-500 disabled:opacity-50 rounded-lg transition-colors text-white font-medium"
          >
            {applying ? "Applying..." : "Approve & Generate Images"}
          </button>
        </div>
      </div>

      {/* Scene list */}
      <div className={`divide-y divide-neutral-800 ${fullHeight ? "overflow-y-auto" : "max-h-96 overflow-y-auto"}`}>
        {assignments.map((a, idx) => {
          const sourceInfo = SOURCE_LABELS[a.media_source] ?? { label: a.media_source, color: "bg-neutral-700 text-neutral-300" };
          return (
            <div key={a.scene_id} className="px-4 py-2.5 flex items-center gap-3 text-sm">
              <span className="text-neutral-500 w-6 text-right shrink-0">{idx + 1}</span>
              <select
                value={a.media_source}
                onChange={(e) => handleSourceChange(a.scene_id, e.target.value as "ai" | "gameplay_video" | "stock_photo")}
                className="bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200 shrink-0"
              >
                <option value="ai">AI</option>
                <option value="gameplay_video">Gameplay</option>
                <option value="stock_photo">Stock Photo</option>
              </select>
              <span className={`px-2 py-0.5 rounded text-xs font-medium shrink-0 ${sourceInfo.color}`}>
                {sourceInfo.label}
              </span>
              {a.media_source === "gameplay_video" && (
                <input
                  type="text"
                  value={a.game_name ?? ""}
                  onChange={(e) => handleFieldChange(a.scene_id, "game_name", e.target.value)}
                  placeholder="Game name"
                  className="bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200 placeholder-neutral-600 w-40"
                />
              )}
              {a.media_source === "stock_photo" && (
                <input
                  type="text"
                  value={a.search_query ?? ""}
                  onChange={(e) => handleFieldChange(a.scene_id, "search_query", e.target.value)}
                  placeholder="Search query"
                  className="bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200 placeholder-neutral-600 w-48"
                />
              )}
              <span className="text-neutral-500 text-xs truncate flex-1" title={a.reasoning}>
                {a.reasoning}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
