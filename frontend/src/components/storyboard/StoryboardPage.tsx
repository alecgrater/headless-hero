import { useCallback, useEffect, useRef, useState } from "react";
import api from "../../api";
import type { ScriptContent } from "../../types/script";
import type { ScriptRead } from "../../types/script";
import type { BrandProfile } from "../../types/brand";
import type { VoiceInfo, VoiceListResponse } from "../../types/audio";
import ExportPanel from "./ExportPanel";
import PropertiesPanel from "./PropertiesPanel";
import SceneGrid from "./SceneGrid";
import SegmentList from "./SegmentList";
import VideoPreviewModal from "./VideoPreviewModal";
import VoiceSetupModal from "../brand/VoiceSetupModal";
import { usePublishState } from "./usePublishState";
import { useRenderState } from "./useRenderState";
import { useStoryboardState } from "./useStoryboardState";
import { useKeyboardShortcuts, ShortcutHelpOverlay } from "./useKeyboardShortcuts";
import PreviewStrip from "./PreviewStrip";

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

  return <StoryboardEditor scriptId={scriptId} brandId={script.brand_id} initialContent={script.script} title={script.topic_title} contentFormat={script.content_format || "youtube"} onBack={onBack} />;
}

interface BatchProgressProps {
  progress: {
    total: number;
    completed: number;
    failed: number;
    currentSceneName: string | null;
    startedAt: number | null;
  };
  label: string;
}

function BatchProgressBar({ progress, label }: BatchProgressProps) {
  if (progress.total === 0) return null;
  const done = progress.completed + progress.failed;
  const pct = done / progress.total;
  const elapsed = progress.startedAt ? (Date.now() - progress.startedAt) / 1000 : 0;
  const avgPerScene = done > 0 ? elapsed / done : 0;
  const remaining = (progress.total - done) * avgPerScene;
  const etaStr = done > 0 && remaining > 0
    ? remaining < 60
      ? `~${Math.round(remaining)}s left`
      : `~${Math.round(remaining / 60)}m left`
    : "";
  const allDone = done >= progress.total;

  return (
    <div className={`px-4 py-2 border-b border-neutral-800 shrink-0 ${allDone ? "bg-emerald-500/10" : "bg-violet-500/10"}`}>
      <div className="flex items-center gap-3 text-xs">
        {!allDone && (
          <span className="w-3 h-3 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
        )}
        <span className="text-neutral-300">
          {allDone ? (
            progress.failed > 0 ? (
              <>Done &middot; {progress.completed} of {progress.total} generated, {progress.failed} failed</>
            ) : (
              <>All {progress.total} {label} generated &#10003;</>
            )
          ) : (
            <>Generating {label} &middot; {done} of {progress.total} done{progress.currentSceneName && <span className="text-neutral-500 ml-1">({progress.currentSceneName})</span>}</>
          )}
        </span>
        {etaStr && <span className="text-neutral-500">{etaStr}</span>}
        <div className="flex-1 h-1.5 bg-neutral-800 rounded-full overflow-hidden ml-2">
          <div
            className={`h-full rounded-full transition-all duration-300 ${allDone ? "bg-emerald-500" : "bg-violet-500"}`}
            style={{ width: `${pct * 100}%` }}
          />
        </div>
      </div>
    </div>
  );
}

function StoryboardEditor({
  scriptId,
  brandId,
  initialContent,
  title,
  contentFormat,
  onBack,
}: {
  scriptId: string;
  brandId: string;
  initialContent: ScriptContent;
  title: string;
  contentFormat: string;
  onBack: () => void;
}) {
  const isShortform = contentFormat === "shortform";
  const state = useStoryboardState(scriptId, initialContent);
  const render = useRenderState(scriptId, title);
  const publish = usePublishState(scriptId, brandId);
  const [activeSegmentIdx, setActiveSegmentIdx] = useState<number | null>(null);
  const [showExport, setShowExport] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [showVoiceSetup, setShowVoiceSetup] = useState(false);
  const [pendingAudioAction, setPendingAudioAction] = useState<"all" | string | null>(null);
  const [previewMode, setPreviewMode] = useState(false);

  // Fetch render estimate when export panel or preview modal opens
  useEffect(() => {
    if (!showExport && !showPreview) return;
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
  }, [showExport, showPreview]);
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

  // Parse active modifier IDs from brand
  const activeModifierIds: string[] = (() => {
    try {
      const raw = brand?.content_modifiers;
      if (!raw) return ["title_cards"];
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) && parsed.length > 0 ? parsed : ["title_cards"];
    } catch {
      return ["title_cards"];
    }
  })();

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

  // Auto-render preview when scene changes in preview mode
  useEffect(() => {
    if (!previewMode || !state.selectedSceneId) return;
    const scene = (() => {
      for (const seg of state.content.segments) {
        const sc = seg.scenes.find((s) => s.id === state.selectedSceneId);
        if (sc) return sc;
      }
      return null;
    })();
    if (scene?.image_url && scene?.audio_url) {
      render.previewScene(state.selectedSceneId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewMode, state.selectedSceneId]);

  const handleSegmentClick = (idx: number) => {
    setActiveSegmentIdx(idx);
    const el = segmentRefs.current.get(idx);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  // Build flat scene list for keyboard navigation
  const allSceneIds = state.content.segments.flatMap((seg) =>
    seg.scenes.map((sc) => sc.id),
  );

  const selectPrevScene = useCallback(() => {
    const idx = state.selectedSceneId ? allSceneIds.indexOf(state.selectedSceneId) : -1;
    if (idx > 0) state.selectScene(allSceneIds[idx - 1]);
    else if (allSceneIds.length > 0) state.selectScene(allSceneIds[allSceneIds.length - 1]);
  }, [allSceneIds, state]);

  const selectNextScene = useCallback(() => {
    const idx = state.selectedSceneId ? allSceneIds.indexOf(state.selectedSceneId) : -1;
    if (idx < allSceneIds.length - 1) state.selectScene(allSceneIds[idx + 1]);
    else if (allSceneIds.length > 0) state.selectScene(allSceneIds[0]);
  }, [allSceneIds, state]);

  const toggleAudioPreview = useCallback(() => {
    const audioEl = document.querySelector("aside audio") as HTMLAudioElement | null;
    if (audioEl) {
      if (audioEl.paused) audioEl.play();
      else audioEl.pause();
    }
  }, []);

  const deleteScene = useCallback(() => {
    // We don't actually delete scenes — split/merge is the pattern. No-op for safety.
  }, []);

  const { showHelp, setShowHelp } = useKeyboardShortcuts({
    selectPrevScene,
    selectNextScene,
    undo: state.undo,
    save: state.save,
    generateImage: () => {
      if (state.selectedSceneId) state.generateImage(state.selectedSceneId, artStyle);
    },
    generateAllImages: () => state.generateAllImages(artStyle),
    openExport: () => setShowExport(true),
    toggleAudioPreview,
    deleteScene,
  });

  const saveStatusLabel =
    state.saveStatus === "saved"
      ? "Saved"
      : state.saveStatus === "saving"
        ? "Saving..."
        : "Unsaved";

  const saveDotColor =
    state.saveStatus === "saved"
      ? "bg-emerald-400"
      : state.saveStatus === "saving"
        ? "bg-yellow-400"
        : "bg-red-400 animate-pulse";

  // Tweak #1 + #10: scene stats + word count
  const allScenes = state.content.segments.flatMap((seg) => seg.scenes);
  const sceneCount = allScenes.length;
  const segmentCount = state.content.segments.length;
  const totalDurationSec = allScenes.reduce(
    (sum, sc) => sum + (sc.duration_estimate_seconds ?? 0),
    0,
  );
  const durationMin = Math.floor(totalDurationSec / 60);
  const durationSec = Math.round(totalDurationSec % 60);
  const durationStr = `${durationMin}:${String(durationSec).padStart(2, "0")}`;
  const totalWords = allScenes.reduce(
    (sum, sc) => sum + (sc.narration ? sc.narration.split(/\s+/).filter(Boolean).length : 0),
    0,
  );
  const statsStr = `${sceneCount} scene${sceneCount !== 1 ? "s" : ""} \u00B7 ${segmentCount} segment${segmentCount !== 1 ? "s" : ""} \u00B7 ${durationStr}${totalWords > 0 ? ` \u00B7 ${totalWords.toLocaleString()} words` : ""}`;

  return (
    <div className="flex flex-col h-[calc(100vh-105px)]">
      {/* Row 1 — Navigation + Title + Save */}
      <div className="flex items-center gap-4 px-5 py-2.5 border-b border-neutral-800/60 shrink-0">
        <button
          onClick={onBack}
          className="text-sm px-3 py-1.5 text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 rounded-lg transition-colors"
        >
          &larr; Back
        </button>
        <h2 className="text-base font-semibold truncate">{title}</h2>
        <span className="text-[11px] text-neutral-500 bg-neutral-800/60 px-2 py-0.5 rounded-full">
          {statsStr}
        </span>

        <div className="ml-auto flex items-center gap-2">
          <span className={`w-1.5 h-1.5 rounded-full ${saveDotColor}`} />
          <span className="text-[11px] text-neutral-500">{saveStatusLabel}</span>
          {state.canUndo && (
            <button
              onClick={state.undo}
              className="text-[11px] px-2 py-1 text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800 rounded-md transition-colors"
              title="Undo (Cmd+Z)"
            >
              Undo
            </button>
          )}
          <button
            onClick={state.save}
            disabled={!state.isDirty}
            className={`text-sm px-3 py-1 rounded-lg font-medium transition-colors ${
              state.isDirty
                ? "bg-neutral-200 text-neutral-900 hover:bg-white"
                : "bg-neutral-800 text-neutral-500 cursor-default"
            }`}
            title="Cmd+S"
          >
            Save
          </button>
        </div>
      </div>

      {/* Row 2 — Action Bar */}
      <div className="flex items-center gap-1.5 px-5 py-2 border-b border-neutral-800/60 bg-neutral-900/40 shrink-0">
        {/* Group 1 — Media Generation */}
        <div className="bg-neutral-800/50 rounded-lg p-1 flex items-center gap-1.5">
          <button
            onClick={() => state.generateAllImages(artStyle)}
            disabled={state.batchGenerating}
            className="text-sm px-3 py-1.5 text-emerald-400 hover:bg-emerald-500/15 disabled:opacity-40 disabled:cursor-not-allowed rounded-md font-medium transition-colors flex items-center gap-2"
            title="Generate images for all scenes with visual prompts"
          >
            {state.batchGenerating ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-emerald-400/50 border-t-transparent rounded-full animate-spin" />
                Generating...
              </>
            ) : (
              "Generate Images"
            )}
          </button>
          {/* Fetch Media button — only shown when script has real-media scenes */}
          {state.content.segments.some((seg) =>
            seg.scenes.some((sc) => sc.media_type && sc.media_type !== "ai_generated" && sc.search_query)
          ) && (
            <>
              <div className="w-px h-5 bg-neutral-700" />
              <button
                onClick={() => state.fetchAllMedia()}
                disabled={state.batchFetchingMedia}
                className="text-sm px-3 py-1.5 text-red-400 hover:bg-red-500/15 disabled:opacity-40 disabled:cursor-not-allowed rounded-md font-medium transition-colors flex items-center gap-2"
                title="Fetch real media (gameplay clips + hardware images) from YouTube"
              >
                {state.batchFetchingMedia ? (
                  <>
                    <span className="w-3.5 h-3.5 border-2 border-red-400/50 border-t-transparent rounded-full animate-spin" />
                    Fetching...
                  </>
                ) : (
                  "Fetch Media"
                )}
              </button>
            </>
          )}
          <div className="w-px h-5 bg-neutral-700" />
          <select
            value={selectedVoiceId}
            onChange={(e) => setSelectedVoiceId(e.target.value)}
            className="text-xs bg-transparent text-neutral-400 border-none rounded px-2 py-1.5 focus:outline-none max-w-[120px]"
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
            className="text-sm px-3 py-1.5 text-sky-400 hover:bg-sky-500/15 disabled:opacity-40 disabled:cursor-not-allowed rounded-md font-medium transition-colors flex items-center gap-2"
            title="Generate audio for all scenes with narration"
          >
            {state.batchGeneratingAudio ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-sky-400/50 border-t-transparent rounded-full animate-spin" />
                Generating...
              </>
            ) : (
              "Generate Audio"
            )}
          </button>
        </div>

        {/* Divider */}
        <div className="w-px h-5 bg-neutral-700/50 mx-1.5" />

        {/* Group 2 — Preview */}
        <div className="bg-neutral-800/50 rounded-lg p-1 flex items-center gap-1">
          <button
            onClick={() => setPreviewMode((prev) => !prev)}
            className={`text-sm px-3 py-1.5 rounded-md font-medium transition-colors ${
              previewMode
                ? "bg-violet-500/20 text-violet-300"
                : "text-neutral-400 hover:bg-neutral-700/60"
            }`}
            title="Toggle scene preview mode (P)"
          >
            Preview
          </button>
          <button
            onClick={() => setShowPreview(true)}
            className="text-sm px-3 py-1.5 text-neutral-400 hover:bg-neutral-700/60 rounded-md font-medium transition-colors"
            title="Preview full rendered video"
          >
            Full Preview
          </button>
        </div>

        {/* Divider */}
        <div className="w-px h-5 bg-neutral-700/50 mx-1.5" />

        {/* Shortform duration meter */}
        {isShortform && (() => {
          const totalDur = state.content.segments.reduce(
            (sum, seg) => sum + seg.scenes.reduce((s, sc) => s + (sc.audio_duration_seconds || sc.duration_estimate_seconds), 0),
            0,
          );
          const color = totalDur <= 45 ? "text-emerald-400" : totalDur <= 60 ? "text-yellow-400" : "text-red-400";
          return (
            <span className={`text-xs font-mono ${color} mr-2`} title="Total duration">
              {Math.round(totalDur)}s
            </span>
          );
        })()}

        {isShortform && (
          <span className="text-xs bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded-full mr-2">
            Short-Form
          </span>
        )}

        {/* Export CTA — the ONLY solid-color button */}
        <button
          onClick={() => setShowExport(true)}
          className="text-sm px-4 py-1.5 bg-violet-600 hover:bg-violet-500 rounded-lg font-semibold transition-colors shadow-sm shadow-violet-500/20"
          title="Export & Render (⌘E)"
        >
          Export
        </button>
      </div>

      {/* Batch Progress Bar */}
      <BatchProgressBar progress={state.batchImageProgress} label="images" />
      <BatchProgressBar progress={state.batchAudioProgress} label="audio" />
      <BatchProgressBar progress={state.batchMediaProgress} label="media" />

      {/* Three-panel layout */}
      <div className="flex flex-1 overflow-hidden">
        {!isShortform && (
          <SegmentList
            content={state.content}
            activeSegmentIdx={activeSegmentIdx}
            onSegmentClick={handleSegmentClick}
          />
        )}

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
          batchImageStatuses={state.batchImageProgress.statuses}
          onRetryImage={(sceneId) => state.generateImage(sceneId, artStyle)}
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
            onDuplicate={() => state.duplicateScene(selectedScene.scene.id)}
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
            previewMode={previewMode}
            onPrevScene={selectPrevScene}
            onNextScene={selectNextScene}
            onFetchMedia={() =>
              state.fetchMedia(selectedScene.scene.id)
            }
            isFetchingMedia={state.fetchingMediaSceneIds.has(selectedScene.scene.id)}
            contentFormat={contentFormat}
          />
        ) : (
          <aside className="w-[320px] shrink-0 border-l border-neutral-800/60 p-4 flex items-center justify-center">
            <p className="text-sm text-neutral-600 text-center">
              Select a scene to edit its properties
            </p>
          </aside>
        )}
      </div>

      {/* Preview Strip */}
      {previewMode && (
        <PreviewStrip
          content={state.content}
          selectedSceneId={state.selectedSceneId}
          onSelectScene={state.selectScene}
        />
      )}

      {showPreview && (
        <VideoPreviewModal
          youtubeStatus={render.youtubeStatus}
          youtubeUrl={render.youtubeUrl}
          estimatedSeconds={render.estimatedSeconds}
          onStartRender={render.startYoutubeRender}
          onClose={() => setShowPreview(false)}
        />
      )}

      {showExport && (
        <ExportPanel
          youtubeStatus={render.youtubeStatus}
          youtubeUrl={render.youtubeUrl}
          onStartYoutubeRender={render.startYoutubeRender}
          autoEditStatus={render.autoEditStatus}
          autoEditUrl={render.autoEditUrl}
          onStartAutoEditRender={render.startAutoEditRender}
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
          activeModifierIds={activeModifierIds}
          contentFormat={contentFormat}
          scriptId={scriptId}
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

      {showHelp && <ShortcutHelpOverlay onClose={() => setShowHelp(false)} />}
    </div>
  );
}
