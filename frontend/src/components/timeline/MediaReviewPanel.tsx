import { useState } from "react";
import type { MediaAssignment } from "../../api";
import { applyMediaAssignments } from "../../api";
import type { Scene } from "../../types/script";
import ScenePreviewModal from "./ScenePreviewModal";

interface Props {
  scriptId: string;
  assignments: MediaAssignment[];
  frameCounts?: Record<string, number>;
  fullHeight?: boolean;
  scenes?: Record<string, Scene>;
  sceneSegments?: Record<string, string>;
  onBeforeApply?: () => Promise<boolean | void> | boolean | void;
  onSaved?: (assignments: MediaAssignment[]) => Promise<void> | void;
  onApproved: () => void;
  onReanalyze: () => void;
}

const SOURCE_LABELS: Record<string, { label: string; color: string }> = {
  ai: { label: "AI", color: "bg-violet-500/20 text-violet-300" },
  ai_video: { label: "AI Video", color: "bg-fuchsia-500/20 text-fuchsia-300" },
  gameplay_video: { label: "Gameplay", color: "bg-emerald-500/20 text-emerald-300" },
  stock_photo: { label: "Stock Photo", color: "bg-sky-500/20 text-sky-300" },
  user_upload: { label: "Upload", color: "bg-emerald-500/20 text-emerald-300" },
};

export default function MediaReviewPanel({ scriptId, assignments: initial, frameCounts, fullHeight, scenes, sceneSegments, onBeforeApply, onSaved, onApproved, onReanalyze }: Props) {
  const [assignments, setAssignments] = useState<MediaAssignment[]>(initial);
  const [saving, setSaving] = useState(false);
  const [applying, setApplying] = useState(false);
  const [saveState, setSaveState] = useState<"idle" | "saved" | "error">("idle");
  const [previewSceneId, setPreviewSceneId] = useState<string | null>(null);

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
          ? { ...a, media_source: newSource, game_name: newSource === "gameplay_video" ? a.game_name : null, search_query: newSource === "stock_photo" ? a.search_query : null }
          : a,
      ),
    );
  };

  const handleFieldChange = (sceneId: string, field: "game_name" | "search_query", value: string) => {
    setSaveState("idle");
    setAssignments((prev) =>
      prev.map((a) => (a.scene_id === sceneId ? { ...a, [field]: field === "search_query" ? value : value || null } : a)),
    );
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
            className="px-3 py-1.5 text-xs bg-neutral-800 hover:bg-neutral-700 rounded-lg transition-colors text-neutral-300"
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
          const isUploadedVideo = a.media_source === "user_upload" && !!scene?.video_url;
          const isVideoSource = a.media_source === "ai_video" || a.media_source === "gameplay_video" || isUploadedVideo;
          return (
            <div key={a.scene_id} className="px-4 py-3 flex items-start gap-3 text-sm">
              <span className="text-neutral-500 w-6 text-right shrink-0 pt-1">{idx + 1}</span>
              <div className="flex flex-wrap items-center gap-2 w-64 shrink-0">
                <select
                  value={a.media_source}
                  onChange={(e) => handleSourceChange(a.scene_id, e.target.value as MediaAssignment["media_source"])}
                  className="bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200 shrink-0"
                >
                  <option value="ai">AI</option>
                  <option value="ai_video">AI Video</option>
                  <option value="gameplay_video">Gameplay</option>
                  <option value="stock_photo">Stock Photo</option>
                  {a.media_source === "user_upload" && <option value="user_upload">Upload</option>}
                </select>
                <span className={`px-2 py-0.5 rounded text-xs font-medium shrink-0 ${sourceInfo.color}`}>
                  {sourceInfo.label}
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
              <div className="min-w-0 flex-1 space-y-1">
                <div className="flex items-center gap-2 text-xs text-neutral-500">
                  {sceneSegments?.[a.scene_id] && <span className="truncate">{sceneSegments[a.scene_id]}</span>}
                  {scene?.is_title_card && <span className="text-neutral-600">Title card</span>}
                </div>
                <p className="truncate text-sm text-neutral-200" title={scene?.narration || ""}>
                  {scene?.narration || "No narration for this scene."}
                </p>
                <p className="truncate text-xs text-neutral-500" title={sceneVisualPrompt(scene)}>
                  {sceneVisualPrompt(scene) || "No visual prompt."}
                </p>
                {a.media_source === "gameplay_video" && (
                  <input
                    type="text"
                    value={a.game_name ?? ""}
                    onChange={(e) => handleFieldChange(a.scene_id, "game_name", e.target.value)}
                    placeholder="Game name"
                    className="mt-1 w-full bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200 placeholder-neutral-600"
                  />
                )}
                {a.media_source === "stock_photo" && (
                  <input
                    type="text"
                    value={a.search_query ?? ""}
                    onChange={(e) => handleFieldChange(a.scene_id, "search_query", e.target.value)}
                    placeholder="Search query"
                    className="mt-1 w-full bg-neutral-800 border border-neutral-700 rounded px-2 py-1 text-xs text-neutral-200 placeholder-neutral-600"
                  />
                )}
              </div>
              {scenes && scenes[a.scene_id] && (
                <button
                  onClick={() => setPreviewSceneId(a.scene_id)}
                  disabled={!hasPreviewableAssets(scenes[a.scene_id])}
                  className="w-7 h-7 flex items-center justify-center rounded-md text-neutral-400 hover:text-neutral-200 hover:bg-neutral-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors shrink-0"
                  title="Preview scene"
                >
                  <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.5">
                    <path d="M1 8s2.5-5 7-5 7 5 7 5-2.5 5-7 5-7-5-7-5Z" />
                    <circle cx="8" cy="8" r="2" />
                  </svg>
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* Preview modal */}
      {previewSceneId && scenes && scenes[previewSceneId] && (
        <ScenePreviewModal
          scene={scenes[previewSceneId]}
          sceneIndex={Math.max(0, assignments.findIndex((a) => a.scene_id === previewSceneId))}
          scriptId={scriptId}
          onClose={() => setPreviewSceneId(null)}
        />
      )}
    </div>
  );
}

function hasPreviewableAssets(scene: Scene): boolean {
  return !!(scene.image_url || (scene.frame_urls && scene.frame_urls.length > 0) || scene.audio_url || scene.video_url);
}

function sceneVisualPrompt(scene?: Scene): string {
  return scene?.original_visual_prompt || scene?.visual_prompt || "";
}
