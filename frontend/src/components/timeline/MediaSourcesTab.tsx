import type { MediaAssignment } from "../../api";
import type { Scene, ScriptContent } from "../../types/script";
import MediaReviewPanel from "./MediaReviewPanel";

function buildFrameCounts(content: ScriptContent): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const seg of content.segments) {
    for (const scene of seg.scenes) {
      const directives = scene.frame_directives ?? [];
      if (directives.length > 1 && !["ai_video", "gameplay_video", "user_upload"].includes(scene.media_source ?? "")) {
        counts[scene.id] = directives.length;
      }
    }
  }
  return counts;
}

function buildScenesMap(content: ScriptContent): Record<string, Scene> {
  const map: Record<string, Scene> = {};
  for (const seg of content.segments) {
    for (const scene of seg.scenes) {
      map[scene.id] = scene;
    }
  }
  return map;
}

function buildSceneSegments(content: ScriptContent): Record<string, string> {
  const map: Record<string, string> = {};
  for (const seg of content.segments) {
    for (const scene of seg.scenes) {
      map[scene.id] = seg.name;
    }
  }
  return map;
}

function scenesMissingVoiceover(content: ScriptContent): Scene[] {
  return content.segments
    .flatMap((seg) => seg.scenes)
    .filter((scene) => (scene.audio_duration_seconds ?? 0) <= 0);
}

function voiceoverBlockedReason(missingCount: number): string {
  if (missingCount <= 0) return "";
  return `Generate voiceover first. ${missingCount} scene${missingCount === 1 ? "" : "s"} still missing duration timing.`;
}

interface Props {
  scriptId: string;
  content: ScriptContent;
  mediaAssignments: MediaAssignment[] | null;
  mediaAnalyzing: boolean;
  mediaReviewDismissed: boolean;
  onAnalyzeMedia: () => void;
  onBeforeAssignmentsApply: () => Promise<boolean | void> | boolean | void;
  onAssignmentsSaved: (assignments: MediaAssignment[]) => Promise<void> | void;
  onApproved: () => void;
}

export default function MediaSourcesTab({
  scriptId,
  content,
  mediaAssignments,
  mediaAnalyzing,
  mediaReviewDismissed,
  onAnalyzeMedia,
  onBeforeAssignmentsApply,
  onAssignmentsSaved,
  onApproved,
}: Props) {
  const missingVoiceoverScenes = scenesMissingVoiceover(content);
  const canAnalyzeMedia = missingVoiceoverScenes.length === 0;
  const analyzeBlockedReason = voiceoverBlockedReason(missingVoiceoverScenes.length);

  if (mediaAnalyzing) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <span className="w-6 h-6 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm text-neutral-400">Analyzing media sources...</span>
        </div>
      </div>
    );
  }

  if (mediaAssignments && !mediaReviewDismissed) {
    const frameCounts = buildFrameCounts(content);
    const scenes = buildScenesMap(content);
    const sceneSegments = buildSceneSegments(content);
    return (
      <div className="flex-1 overflow-auto p-4 space-y-4">
        <MediaReviewPanel
          scriptId={scriptId}
          assignments={mediaAssignments}
          frameCounts={frameCounts}
          scenes={scenes}
          sceneSegments={sceneSegments}
          canAnalyze={canAnalyzeMedia}
          analyzeBlockedReason={analyzeBlockedReason}
          fullHeight
          onBeforeApply={onBeforeAssignmentsApply}
          onSaved={onAssignmentsSaved}
          onApproved={onApproved}
          onReanalyze={onAnalyzeMedia}
        />
      </div>
    );
  }

  if (mediaReviewDismissed) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="text-sm text-neutral-400">
            Media sources have been approved. Images are generating.
          </div>
          <button
            onClick={onAnalyzeMedia}
            disabled={!canAnalyzeMedia}
            title={!canAnalyzeMedia ? analyzeBlockedReason : undefined}
            className="px-4 py-2 text-sm bg-neutral-800 hover:bg-neutral-700 disabled:hover:bg-neutral-800 disabled:opacity-50 rounded-lg transition-colors text-neutral-300"
          >
            Re-analyze Media Sources
          </button>
        </div>
      </div>
    );
  }

  const gameplayEnabled = content.gameplay_enabled;
  const stockEnabled = content.stock_photo_enabled;
  const aiVideoEnabled = content.ai_video_enabled;
  const enabledSources = [
    aiVideoEnabled && "AI Video",
    gameplayEnabled && "Gameplay Video",
    stockEnabled && "Stock Photos",
  ].filter(Boolean);

  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="flex flex-col items-center gap-5 max-w-2xl text-center px-6">
        <div className="space-y-3">
          <p className="text-sm text-neutral-400">
            {enabledSources.length > 0
              ? `This project has ${enabledSources.join(" and ")} enabled. Analyze your script to assign media sources per scene.`
              : "Analyze your script to assign media sources (AI, AI video, gameplay, stock photos) per scene."}
          </p>
        </div>
        <button
          onClick={onAnalyzeMedia}
          disabled={!canAnalyzeMedia}
          title={!canAnalyzeMedia ? analyzeBlockedReason : undefined}
          className="px-5 py-2 text-sm bg-violet-600 hover:bg-violet-500 disabled:hover:bg-violet-600 disabled:opacity-50 rounded-lg transition-colors text-white font-medium"
        >
          Analyze Media Sources
        </button>
        {!canAnalyzeMedia && (
          <p className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2">
            {analyzeBlockedReason}
          </p>
        )}
      </div>
    </div>
  );
}
