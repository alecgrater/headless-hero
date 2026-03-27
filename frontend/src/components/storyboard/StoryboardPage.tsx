import { useEffect, useRef, useState } from "react";
import api from "../../api";
import type { ScriptContent } from "../../types/script";
import type { ScriptRead } from "../../types/script";
import PropertiesPanel from "./PropertiesPanel";
import SceneGrid from "./SceneGrid";
import SegmentList from "./SegmentList";
import { useStoryboardState } from "./useStoryboardState";

interface Props {
  scriptId: string;
  onBack: () => void;
}

export default function StoryboardPage({ scriptId, onBack }: Props) {
  const [script, setScript] = useState<ScriptRead | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const fetch = async () => {
      setLoading(true);
      try {
        const res = await api.get(`/api/scripts/${scriptId}`);
        if (cancelled) return;
        if (res.ok) {
          setScript(res.data as ScriptRead);
        } else {
          setError("Failed to load script");
        }
      } catch {
        if (!cancelled) setError("Could not reach the backend.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetch();
    return () => {
      cancelled = true;
    };
  }, [scriptId]);

  if (loading) {
    return (
      <div className="text-center py-20 space-y-4">
        <div className="inline-block w-8 h-8 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
        <p className="text-neutral-400">Loading storyboard...</p>
      </div>
    );
  }

  if (error || !script) {
    return (
      <div className="text-center py-20 space-y-4">
        <div className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300 inline-block">
          {error ?? "Script not found"}
        </div>
        <div>
          <button
            onClick={onBack}
            className="text-sm px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 rounded-lg transition-colors text-neutral-300"
          >
            &larr; Go Back
          </button>
        </div>
      </div>
    );
  }

  return <StoryboardEditor scriptId={scriptId} initialContent={script.script} title={script.topic_title} onBack={onBack} />;
}

function StoryboardEditor({
  scriptId,
  initialContent,
  title,
  onBack,
}: {
  scriptId: string;
  initialContent: ScriptContent;
  title: string;
  onBack: () => void;
}) {
  const state = useStoryboardState(scriptId, initialContent);
  const [activeSegmentIdx, setActiveSegmentIdx] = useState<number | null>(null);
  const segmentRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  // Find which segment the selected scene is in
  const selectedScene = state.selectedSceneId
    ? (() => {
        for (let si = 0; si < state.content.segments.length; si++) {
          const sc = state.content.segments[si].scenes.find(
            (s) => s.id === state.selectedSceneId,
          );
          if (sc) {
            const isLast =
              state.content.segments[si].scenes.indexOf(sc) ===
              state.content.segments[si].scenes.length - 1;
            return {
              scene: sc,
              segIdx: si,
              segName: state.content.segments[si].name,
              isLast,
            };
          }
        }
        return null;
      })()
    : null;

  const handleSegmentClick = (idx: number) => {
    setActiveSegmentIdx(idx);
    const el = segmentRefs.current.get(idx);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const saveStatusLabel =
    state.saveStatus === "saved"
      ? "Saved"
      : state.saveStatus === "saving"
        ? "Saving..."
        : "Unsaved";

  const saveStatusColor =
    state.saveStatus === "saved"
      ? "text-emerald-400"
      : state.saveStatus === "saving"
        ? "text-yellow-400"
        : "text-red-400";

  return (
    <div className="flex flex-col h-[calc(100vh-73px)]">
      {/* Header */}
      <div className="flex items-center gap-3 px-4 py-3 border-b border-neutral-800 shrink-0">
        <button
          onClick={onBack}
          className="text-sm px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 rounded-lg transition-colors text-neutral-300"
        >
          &larr; Back
        </button>
        <h2 className="text-lg font-bold truncate">{title}</h2>
        <span className="text-xs text-neutral-500">Storyboard Editor</span>

        <div className="ml-auto flex items-center gap-3">
          {state.canUndo && (
            <button
              onClick={state.undo}
              className="text-xs px-2 py-1 bg-neutral-800 hover:bg-neutral-700 rounded transition-colors text-neutral-400"
              title="Undo (Ctrl+Z)"
            >
              Undo
            </button>
          )}
          <span className={`text-xs ${saveStatusColor}`}>{saveStatusLabel}</span>
          <button
            onClick={state.save}
            disabled={!state.isDirty}
            className="text-sm px-4 py-1.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg font-medium transition-colors"
          >
            Save
          </button>
        </div>
      </div>

      {/* Three-panel layout */}
      <div className="flex flex-1 overflow-hidden">
        <SegmentList
          content={state.content}
          activeSegmentIdx={activeSegmentIdx}
          onSegmentClick={handleSegmentClick}
        />

        <SceneGrid
          content={state.content}
          selectedSceneId={state.selectedSceneId}
          segmentRefs={segmentRefs}
          onSelectScene={state.selectScene}
          onNarrationChange={(id, narr) =>
            state.updateScene(id, { narration: narr })
          }
          onMoveScene={state.moveScene}
        />

        {selectedScene ? (
          <PropertiesPanel
            scene={selectedScene.scene}
            segmentIdx={selectedScene.segIdx}
            segmentName={selectedScene.segName}
            isLastInSegment={selectedScene.isLast}
            onUpdate={(updates) =>
              state.updateScene(selectedScene.scene.id, updates)
            }
            onSplit={() => state.splitScene(selectedScene.scene.id)}
            onMerge={() => state.mergeWithNext(selectedScene.scene.id)}
          />
        ) : (
          <aside className="w-[320px] shrink-0 border-l border-neutral-800 p-4 flex items-center justify-center">
            <p className="text-sm text-neutral-600 text-center">
              Select a scene to edit its properties
            </p>
          </aside>
        )}
      </div>
    </div>
  );
}
