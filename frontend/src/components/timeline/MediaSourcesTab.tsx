import type { MediaAssignment } from "../../api";
import type { Scene, ScriptContent } from "../../types/script";
import MediaReviewPanel from "./MediaReviewPanel";

function buildFrameCounts(content: ScriptContent): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const seg of content.segments) {
    for (const scene of seg.scenes) {
      const directives = scene.frame_directives ?? [];
      if (directives.length > 1) {
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

interface Props {
  scriptId: string;
  content: ScriptContent;
  mediaAssignments: MediaAssignment[] | null;
  mediaAnalyzing: boolean;
  mediaReviewDismissed: boolean;
  onAnalyzeMedia: () => void;
  onAssignmentsSaved: (assignments: MediaAssignment[]) => Promise<void> | void;
  onApproved: () => void;
}

function DescriptionText() {
  return (
    <div className="space-y-2 text-sm leading-6 text-neutral-400">
      <p>
        Media sources decide where each scene gets its visuals before generation starts.
        Use this tab to route scenes between AI-generated imagery, gameplay clips, and
        stock photos so the final video uses the best source for each beat instead of
        treating the whole script the same way.
      </p>
      <p>
        After analysis, review each scene, adjust the selected source, and edit the
        gameplay game name or stock search query when needed. Saving preserves those
        choices for later; approving saves them and starts generating the visuals from
        the selected sources.
      </p>
    </div>
  );
}

export default function MediaSourcesTab({
  scriptId,
  content,
  mediaAssignments,
  mediaAnalyzing,
  mediaReviewDismissed,
  onAnalyzeMedia,
  onAssignmentsSaved,
  onApproved,
}: Props) {
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
    return (
      <div className="flex-1 overflow-auto p-4 space-y-4">
        <div className="rounded-lg border border-neutral-800 bg-neutral-900 px-4 py-3">
          <DescriptionText />
        </div>
        <MediaReviewPanel
          scriptId={scriptId}
          assignments={mediaAssignments}
          frameCounts={frameCounts}
          scenes={scenes}
          fullHeight
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
            className="px-4 py-2 text-sm bg-neutral-800 hover:bg-neutral-700 rounded-lg transition-colors text-neutral-300"
          >
            Re-analyze Media Sources
          </button>
        </div>
      </div>
    );
  }

  const gameplayEnabled = content.gameplay_enabled;
  const stockEnabled = content.stock_photo_enabled;
  const enabledSources = [
    gameplayEnabled && "Gameplay Video",
    stockEnabled && "Stock Photos",
  ].filter(Boolean);

  return (
    <div className="flex-1 flex items-center justify-center">
      <div className="flex flex-col items-center gap-5 max-w-2xl text-center px-6">
        <div className="space-y-3">
          <DescriptionText />
          <p className="text-sm text-neutral-400">
          {enabledSources.length > 0
            ? `This project has ${enabledSources.join(" and ")} enabled. Analyze your script to assign media sources per scene.`
            : "Analyze your script to assign media sources (AI, gameplay, stock photos) per scene."}
          </p>
        </div>
        <button
          onClick={onAnalyzeMedia}
          className="px-5 py-2 text-sm bg-violet-600 hover:bg-violet-500 rounded-lg transition-colors text-white font-medium"
        >
          Analyze Media Sources
        </button>
      </div>
    </div>
  );
}
