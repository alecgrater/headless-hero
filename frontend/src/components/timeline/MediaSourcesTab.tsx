import type { MediaAssignment, VisualTreatmentAssignment } from "../../api";
import type { Scene, ScriptContent } from "../../types/script";
import MediaReviewPanel from "./MediaReviewPanel";
import VisualTreatmentReviewPanel from "./VisualTreatmentReviewPanel";

function buildFrameCounts(content: ScriptContent): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const seg of content.segments) {
    for (const scene of seg.scenes) {
      const directives = scene.frame_directives ?? [];
      if (directives.length > 1 && scene.visual_mode !== "video") {
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

function scenesMissingVisualTreatmentTiming(content: ScriptContent) {
  const nonTitleScenes = content.segments
    .flatMap((seg) => seg.scenes)
    .filter((scene) => !scene.is_title_card);
  const missingAudioCount = nonTitleScenes.filter((scene) => (scene.audio_duration_seconds ?? 0) <= 0).length;
  const missingWordTimingCount = nonTitleScenes.filter((scene) => (scene.word_timestamps?.length ?? 0) <= 0).length;
  return { missingAudioCount, missingWordTimingCount };
}

function voiceoverBlockedReason(missingCount: number): string {
  if (missingCount <= 0) return "";
  return `Generate voiceover first. ${missingCount} scene${missingCount === 1 ? "" : "s"} still missing duration timing.`;
}

function visualTreatmentBlockedReason(missingAudioCount: number, missingWordTimingCount: number): string {
  const parts: string[] = [];
  if (missingAudioCount > 0) {
    parts.push(`${missingAudioCount} non-title scene${missingAudioCount === 1 ? "" : "s"} missing duration timing`);
  }
  if (missingWordTimingCount > 0) {
    parts.push(`${missingWordTimingCount} non-title scene${missingWordTimingCount === 1 ? "" : "s"} missing word timing`);
  }
  if (parts.length === 0) return "";
  return `Generate voiceover first. ${parts.join(" and ")}.`;
}

interface Props {
  scriptId: string;
  content: ScriptContent;
  mediaAssignments: MediaAssignment[] | null;
  mediaAnalyzing: boolean;
  mediaReviewDismissed: boolean;
  visualTreatmentAssignments: VisualTreatmentAssignment[] | null;
  visualTreatmentAnalyzing: boolean;
  onAnalyzeVisualTreatments: () => void;
  onApplyVisualTreatments: (assignments: VisualTreatmentAssignment[]) => void;
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
  visualTreatmentAssignments,
  visualTreatmentAnalyzing,
  onAnalyzeVisualTreatments,
  onApplyVisualTreatments,
  onAnalyzeMedia,
  onBeforeAssignmentsApply,
  onAssignmentsSaved,
  onApproved,
}: Props) {
  const missingVoiceoverScenes = scenesMissingVoiceover(content);
  const canAnalyzeMedia = missingVoiceoverScenes.length === 0;
  const analyzeBlockedReason = voiceoverBlockedReason(missingVoiceoverScenes.length);
  const visualTreatmentTiming = scenesMissingVisualTreatmentTiming(content);
  const canAnalyzeVisualTreatments =
    visualTreatmentTiming.missingAudioCount === 0 && visualTreatmentTiming.missingWordTimingCount === 0;
  const visualTreatmentAnalyzeBlockedReason = visualTreatmentBlockedReason(
    visualTreatmentTiming.missingAudioCount,
    visualTreatmentTiming.missingWordTimingCount,
  );
  const scenes = buildScenesMap(content);
  const hasExistingVisualModeReview = Boolean(visualTreatmentAssignments || mediaAssignments || mediaReviewDismissed);
  const visualTreatmentAnalyzeLabel = hasExistingVisualModeReview ? "Re-analyze Visual Modes" : "Analyze Visual Modes";
  const handleAnalyzeVisualModeReview = () => {
    if (canAnalyzeVisualTreatments) {
      onAnalyzeVisualTreatments();
    }
    if (canAnalyzeMedia) {
      onAnalyzeMedia();
    }
  };
  const canAnalyzeAnyVisualModes =
    canAnalyzeVisualTreatments || canAnalyzeMedia;
  const visualModeAnalyzeBlockedReason = canAnalyzeVisualTreatments
    ? analyzeBlockedReason
    : visualTreatmentAnalyzeBlockedReason || analyzeBlockedReason;

  const visualTreatmentSection = (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-neutral-100">Visual Mode Review</h3>
          <p className="text-xs text-neutral-500">Reassess scene visual modes inside the unified visual mode system.</p>
        </div>
        <button
          type="button"
          onClick={handleAnalyzeVisualModeReview}
          disabled={!canAnalyzeAnyVisualModes || visualTreatmentAnalyzing || mediaAnalyzing}
          title={!canAnalyzeAnyVisualModes ? visualModeAnalyzeBlockedReason : undefined}
          className="rounded-lg bg-neutral-800 px-4 py-2 text-xs font-medium text-neutral-200 transition-colors hover:bg-neutral-700 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-neutral-800"
        >
          {visualTreatmentAnalyzing || mediaAnalyzing ? "Analyzing..." : visualTreatmentAnalyzeLabel}
        </button>
      </div>
      {visualTreatmentAssignments ? (
        <VisualTreatmentReviewPanel
          assignments={visualTreatmentAssignments}
          scenes={scenes}
          onApply={onApplyVisualTreatments}
        />
      ) : (
        <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
          <p className="max-w-2xl text-xs leading-5 text-neutral-400">
            Analyze scenes after voiceover timing exists to populate the review with route, variety, and layered-asset decisions.
          </p>
          {!canAnalyzeVisualTreatments && (
            <p className="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/10 px-3 py-2 text-xs text-amber-300">
              {visualTreatmentAnalyzeBlockedReason}
            </p>
          )}
        </div>
      )}
    </div>
  );

  if (mediaAnalyzing) {
    return (
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {visualTreatmentSection}
        <div className="flex items-center justify-center py-16">
          <div className="flex flex-col items-center gap-3">
            <span className="w-6 h-6 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-sm text-neutral-400">Analyzing visual modes...</span>
          </div>
        </div>
      </div>
    );
  }

  if (mediaAssignments && !mediaReviewDismissed) {
    const frameCounts = buildFrameCounts(content);
    const sceneSegments = buildSceneSegments(content);
    return (
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {visualTreatmentSection}
        <MediaReviewPanel
          scriptId={scriptId}
          assignments={mediaAssignments}
          frameCounts={frameCounts}
          scenes={scenes}
          sceneSegments={sceneSegments}
          fullHeight
          onBeforeApply={onBeforeAssignmentsApply}
          onSaved={onAssignmentsSaved}
          onApproved={onApproved}
        />
      </div>
    );
  }

  if (mediaReviewDismissed) {
    return (
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {visualTreatmentSection}
        <div className="flex items-center justify-center py-16">
          <div className="flex flex-col items-center gap-4">
            <div className="text-sm text-neutral-400">
              Visual modes have been approved. Assets are generating.
            </div>
          </div>
        </div>
      </div>
    );
  }

  const aiVideoEnabled = content.ai_video_enabled;
  const enabledSources = [
    aiVideoEnabled && "AI Video",
  ].filter(Boolean);

  return (
    <div className="flex-1 overflow-auto p-4 space-y-4">
      {visualTreatmentSection}
      <div className="flex items-center justify-center py-12">
        <div className="flex flex-col items-center gap-5 max-w-2xl text-center px-6">
          <div className="space-y-3">
            <p className="text-sm text-neutral-400">
              {enabledSources.length > 0
                ? `This project has ${enabledSources.join(" and ")} enabled. Analyze your script to assign visual modes per scene.`
                : "Analyze your script to assign full-frame and video modes per scene."}
            </p>
          </div>
          {!canAnalyzeMedia && (
            <p className="text-xs text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded-lg px-3 py-2">
              {analyzeBlockedReason}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
