import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";
import type { MediaAssignment } from "../../api";
import { applyMediaAssignments } from "../../api";
import type { Scene } from "../../types/script";

interface Props {
  scriptId: string;
  assignments: MediaAssignment[];
  frameCounts?: Record<string, number>;
  fullHeight?: boolean;
  scenes?: Record<string, Scene>;
  sceneSegments?: Record<string, string>;
  canAnalyze?: boolean;
  analyzeBlockedReason?: string;
  onBeforeApply?: () => Promise<boolean | void> | boolean | void;
  onSaved?: (assignments: MediaAssignment[]) => Promise<void> | void;
  onApproved: () => void;
  onReanalyze: () => void;
}

const SOURCE_LABELS: Record<string, { label: string; color: string }> = {
  ai: { label: "AI", color: "bg-violet-500/20 text-violet-300" },
  ai_video: { label: "AI Video", color: "bg-fuchsia-500/20 text-fuchsia-300" },
};

export default function MediaReviewPanel({ scriptId, assignments: initial, frameCounts, fullHeight, scenes, sceneSegments, canAnalyze = true, analyzeBlockedReason, onBeforeApply, onSaved, onApproved, onReanalyze }: Props) {
  const [assignments, setAssignments] = useState<MediaAssignment[]>(initial);
  const [saving, setSaving] = useState(false);
  const [applying, setApplying] = useState(false);
  const [saveState, setSaveState] = useState<"idle" | "saved" | "error">("idle");
  const [expandedSceneIds, setExpandedSceneIds] = useState<Set<string>>(new Set());

  const summary = assignments.reduce<Record<string, number>>((acc, a) => {
    acc[a.media_source] = (acc[a.media_source] || 0) + 1;
    return acc;
  }, {});

  const totalScenes = assignments.length;

  const handleSourceChange = (sceneId: string, newSource: MediaAssignment["media_source"]) => {
    setSaveState("idle");
    setAssignments((prev) =>
      prev.map((a) =>
        a.scene_id === sceneId
          ? { ...a, media_source: newSource, game_name: null, search_query: null }
          : a,
      ),
    );
  };

  const toggleExpanded = (sceneId: string) => {
    setExpandedSceneIds((prev) => {
      const next = new Set(prev);
      if (next.has(sceneId)) {
        next.delete(sceneId);
      } else {
        next.add(sceneId);
      }
      return next;
    });
  };

  const applyAssignments = async () => {
    try {
      const readyToApply = await onBeforeApply?.();
      if (readyToApply === false) return false;
      const res = await applyMediaAssignments(scriptId, assignments);
      if (res.ok) {
        await onSaved?.(assignments);
      }
      return res.ok;
    } catch {
      return false;
    }
  };

  const handleSave = async () => {
    setSaving(true);
    setSaveState("idle");
    const ok = await applyAssignments();
    setSaving(false);
    setSaveState(ok ? "saved" : "error");
  };

  const handleApprove = async () => {
    setApplying(true);
    setSaveState("idle");
    const ok = await applyAssignments();
    setApplying(false);
    if (ok) onApproved();
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
            disabled={!canAnalyze}
            title={!canAnalyze ? analyzeBlockedReason : undefined}
            className="px-3 py-1.5 text-xs bg-neutral-800 hover:bg-neutral-700 disabled:hover:bg-neutral-800 disabled:opacity-50 rounded-lg transition-colors text-neutral-300"
          >
            Re-analyze
          </button>
          <button
            onClick={handleSave}
            disabled={saving || applying}
            className="px-3 py-1.5 text-xs bg-neutral-800 hover:bg-neutral-700 disabled:opacity-50 rounded-lg transition-colors text-neutral-200"
          >
            {saving ? "Saving..." : "Save Changes"}
          </button>
          <button
            onClick={handleApprove}
            disabled={applying || saving}
            className="px-3 py-1.5 text-xs bg-violet-600 hover:bg-violet-500 disabled:opacity-50 rounded-lg transition-colors text-white font-medium"
          >
            {applying ? "Applying..." : "Approve & Generate Images"}
          </button>
        </div>
      </div>
      {saveState !== "idle" && (
        <div className={`px-4 py-2 text-xs border-b border-neutral-800 ${saveState === "saved" ? "text-emerald-300 bg-emerald-500/10" : "text-red-300 bg-red-500/10"}`}>
          {saveState === "saved" ? "Media source edits saved." : "Could not save media source edits."}
        </div>
      )}

      {/* Scene list */}
      <div className={`divide-y divide-neutral-800 ${fullHeight ? "overflow-y-auto" : "max-h-96 overflow-y-auto"}`}>
        {assignments.map((a, idx) => {
          const sourceInfo = SOURCE_LABELS[a.media_source] ?? { label: a.media_source, color: "bg-neutral-700 text-neutral-300" };
          const scene = scenes?.[a.scene_id];
          const isVideoSource = a.media_source === "ai_video";
          const isExpanded = expandedSceneIds.has(a.scene_id);
          const visualPrompt = sceneVisualPrompt(scene);
          const durationLabel = sceneDurationLabel(scene);
          return (
            <div key={a.scene_id} className="px-4 py-3 flex items-start gap-3 text-sm">
              <span className="text-neutral-500 w-6 text-right shrink-0 pt-1">{idx + 1}</span>
              <div className="flex flex-col gap-2 w-64 shrink-0">
                <select
                  value={a.media_source}
                  onChange={(e) => handleSourceChange(a.scene_id, e.target.value as MediaAssignment["media_source"])}
                  className="w-full bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200"
                >
                  <option value="ai">AI</option>
                  <option value="ai_video">AI Video</option>
                </select>
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium shrink-0 ${sourceInfo.color}`}>
                    {sourceInfo.label}
                  </span>
                  <span className={`px-1.5 py-0.5 rounded text-xs shrink-0 ${durationLabel ? "text-neutral-300 bg-neutral-800" : "text-amber-300 bg-amber-500/10"}`}>
                    {durationLabel ?? "no voiceover"}
                  </span>
                  {!isVideoSource && frameCounts && frameCounts[a.scene_id] && (
                    <span className="px-1.5 py-0.5 rounded text-xs text-neutral-400 bg-neutral-800 shrink-0">
                      {frameCounts[a.scene_id]} photos
                    </span>
                  )}
                  {isVideoSource && (
                    <span className="px-1.5 py-0.5 rounded text-xs text-fuchsia-200 bg-fuchsia-500/10 shrink-0">
                      video scene
                    </span>
                  )}
                </div>
              </div>
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex items-center gap-2 text-xs text-neutral-500">
                  {sceneSegments?.[a.scene_id] && <span className="truncate">{sceneSegments[a.scene_id]}</span>}
                  {scene?.is_title_card && <span className="text-neutral-600">Title card</span>}
                </div>
                <p
                  className={`${isExpanded ? "whitespace-pre-wrap break-words" : "truncate"} text-sm text-neutral-200`}
                  title={isExpanded ? undefined : scene?.narration || ""}
                >
                  {scene?.narration || "No narration for this scene."}
                </p>
                <p
                  className={`${isExpanded ? "whitespace-pre-wrap break-words leading-5" : "truncate"} text-xs text-neutral-500`}
                  title={isExpanded ? undefined : visualPrompt}
                >
                  {visualPrompt || "No visual prompt."}
                </p>
              </div>
              <button
                onClick={() => toggleExpanded(a.scene_id)}
                className="w-7 h-7 flex items-center justify-center rounded-md text-neutral-400 hover:text-neutral-200 hover:bg-neutral-700 transition-colors shrink-0"
                title={isExpanded ? "Collapse scene text" : "Expand scene text"}
                aria-label={isExpanded ? `Collapse scene ${idx + 1} text` : `Expand scene ${idx + 1} text`}
                aria-expanded={isExpanded}
              >
                {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function sceneVisualPrompt(scene?: Scene): string {
  return scene?.original_visual_prompt || scene?.visual_prompt || "";
}

function sceneDurationLabel(scene?: Scene): string | null {
  const duration = scene?.audio_duration_seconds ?? 0;
  if (duration <= 0) return null;
  return `${duration.toFixed(duration < 10 ? 1 : 0)}s`;
}
