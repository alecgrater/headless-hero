import { useEffect, useRef, useState } from "react";
import api from "../../api";
import type { ScriptContent } from "../../types/script";
import type { ScriptRead } from "../../types/script";
import type { BrandProfile } from "../../types/brand";
import type { VoiceInfo, VoiceListResponse } from "../../types/audio";
import ExportPanel from "./ExportPanel";
import PropertiesPanel from "./PropertiesPanel";
import SceneGrid from "./SceneGrid";
import SegmentList from "./SegmentList";
import VoiceSetupModal from "../brand/VoiceSetupModal";
import { usePublishState } from "./usePublishState";
import { useRenderState } from "./useRenderState";
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

  return <StoryboardEditor scriptId={scriptId} brandId={script.brand_id} initialContent={script.script} title={script.topic_title} onBack={onBack} />;
}

function StoryboardEditor({
  scriptId,
  brandId,
  initialContent,
  title,
  onBack,
}: {
  scriptId: string;
  brandId: string;
  initialContent: ScriptContent;
  title: string;
  onBack: () => void;
}) {
  const state = useStoryboardState(scriptId, initialContent);
  const render = useRenderState(scriptId);
  const publish = usePublishState(scriptId, brandId);
  const [activeSegmentIdx, setActiveSegmentIdx] = useState<number | null>(null);
  const [showExport, setShowExport] = useState(false);
  const [showVoiceSetup, setShowVoiceSetup] = useState(false);
  const [pendingAudioAction, setPendingAudioAction] = useState<"all" | string | null>(null);

  // Fetch render estimate when export panel opens
  useEffect(() => {
    if (!showExport) return;
    const scenes = state.content.segments.flatMap((seg) => seg.scenes);
    const sceneCount = scenes.length;
    const totalAudioDuration = scenes.reduce(
      (sum, sc) => sum + (sc.audio_duration_seconds ?? 0),
      0,
    );
    if (sceneCount > 0) {
      render.fetchEstimate(sceneCount, totalAudioDuration);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showExport]);
  const [brand, setBrand] = useState<BrandProfile | null>(null);
  const [voices, setVoices] = useState<VoiceInfo[]>([]);
  const [selectedVoiceId, setSelectedVoiceId] = useState<string>("");
  const segmentRefs = useRef<Map<number, HTMLDivElement>>(new Map());

  // Fetch brand profile for art_style
  useEffect(() => {
    api.get(`/api/brands/${brandId}`).then((res) => {
      if (res.ok) {
        const b = res.data as BrandProfile;
        setBrand(b);
        if (b.voice_id) setSelectedVoiceId(b.voice_id);
      }
    });
  }, [brandId]);

  // Fetch available voices
  useEffect(() => {
    api.get("/api/voice/voices").then((res) => {
      if (res.ok) {
        const data = res.data as VoiceListResponse;
        setVoices(data.voices);
        // Default to brand voice or first voice
        if (!selectedVoiceId && data.voices.length > 0) {
          setSelectedVoiceId(data.voices[0].voice_id);
        }
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const artStyle = brand?.art_style ?? "";

  // JIT voice check: if no voice selected and no voices available, show modal
  const tryGenerateAudio = (action: "all" | string) => {
    if (!selectedVoiceId && voices.length === 0) {
      setPendingAudioAction(action);
      setShowVoiceSetup(true);
      return;
    }
    if (action === "all") {
      state.generateAllAudio(selectedVoiceId);
    } else {
      state.generateAudio(action, selectedVoiceId);
    }
  };

  const handleVoiceSelected = (voiceId: string) => {
    setSelectedVoiceId(voiceId);
    setShowVoiceSetup(false);
    if (pendingAudioAction === "all") {
      state.generateAllAudio(voiceId);
    } else if (pendingAudioAction) {
      state.generateAudio(pendingAudioAction, voiceId);
    }
    setPendingAudioAction(null);
  };

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
          <button
            onClick={() => state.generateAllImages(artStyle)}
            disabled={state.batchGenerating}
            className="text-sm px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg font-medium transition-colors flex items-center gap-2"
          >
            {state.batchGenerating ? (
              <>
                <span className="w-4 h-4 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />
                Generating...
              </>
            ) : (
              "Generate All Images"
            )}
          </button>
          <div className="flex items-center gap-1.5">
            <select
              value={selectedVoiceId}
              onChange={(e) => setSelectedVoiceId(e.target.value)}
              className="text-xs bg-neutral-800 text-neutral-300 border border-neutral-700 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-sky-500 max-w-[140px]"
            >
              {voices.length === 0 && <option value="">No voices</option>}
              {voices.map((v) => (
                <option key={v.voice_id} value={v.voice_id}>
                  {v.name}
                </option>
              ))}
            </select>
            <button
              onClick={() => tryGenerateAudio("all")}
              disabled={state.batchGeneratingAudio || (!selectedVoiceId && voices.length > 0)}
              className="text-sm px-4 py-1.5 bg-sky-600 hover:bg-sky-500 disabled:opacity-40 disabled:cursor-not-allowed rounded-lg font-medium transition-colors flex items-center gap-2"
            >
              {state.batchGeneratingAudio ? (
                <>
                  <span className="w-4 h-4 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />
                  Generating...
                </>
              ) : (
                "Generate All Audio"
              )}
            </button>
          </div>
          <button
            onClick={() => setShowExport(true)}
            className="text-sm px-4 py-1.5 bg-orange-600 hover:bg-orange-500 rounded-lg font-medium transition-colors"
          >
            Export
          </button>
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
          onGenerateImage={(sceneId) => state.generateImage(sceneId, artStyle)}
          generatingSceneIds={state.generatingSceneIds}
          onGenerateAudio={(sceneId) => tryGenerateAudio(sceneId)}
          generatingAudioSceneIds={state.generatingAudioSceneIds}
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
            onGenerateImage={() =>
              state.generateImage(selectedScene.scene.id, artStyle)
            }
            isGenerating={state.generatingSceneIds.has(selectedScene.scene.id)}
            onGenerateAudio={() =>
              tryGenerateAudio(selectedScene.scene.id)
            }
            isGeneratingAudio={state.generatingAudioSceneIds.has(selectedScene.scene.id)}
            onPreviewScene={() =>
              render.previewScene(selectedScene.scene.id)
            }
            isPreviewingScene={render.previewingSceneId === selectedScene.scene.id}
            previewVideoUrl={render.previewVideoUrl}
          />
        ) : (
          <aside className="w-[320px] shrink-0 border-l border-neutral-800 p-4 flex items-center justify-center">
            <p className="text-sm text-neutral-600 text-center">
              Select a scene to edit its properties
            </p>
          </aside>
        )}
      </div>

      {showExport && (
        <ExportPanel
          youtubeStatus={render.youtubeStatus}
          youtubeUrl={render.youtubeUrl}
          onStartYoutubeRender={render.startYoutubeRender}
          tiktokStatus={render.tiktokStatus}
          tiktokUrls={render.tiktokUrls}
          onStartTiktokRender={render.startTiktokRender}
          audioUrl={render.audioUrl}
          audioExporting={render.audioExporting}
          onExportAudio={render.exportAudio}
          thumbnails={render.thumbnails}
          thumbnailsGenerating={render.thumbnailsGenerating}
          onGenerateThumbnails={() => render.generateThumbnails(artStyle)}
          seoMetadata={render.seoMetadata}
          seoGenerating={render.seoGenerating}
          onGenerateSEO={render.generateSEO}
          youtubeConnected={publish.youtubeConnected}
          youtubeChannelName={publish.youtubeChannelName}
          onConnectYouTube={() => publish.connectPlatform("youtube")}
          connecting={publish.connecting}
          publishStatus={publish.publishStatus}
          onStartPublish={publish.startPublish}
          publishHistory={publish.publishHistory}
          estimatedSeconds={render.estimatedSeconds}
          onClose={() => setShowExport(false)}
        />
      )}

      {showVoiceSetup && (
        <VoiceSetupModal
          brandName={brand?.name ?? ""}
          onVoiceSelected={handleVoiceSelected}
          onClose={() => {
            setShowVoiceSetup(false);
            setPendingAudioAction(null);
          }}
        />
      )}
    </div>
  );
}
