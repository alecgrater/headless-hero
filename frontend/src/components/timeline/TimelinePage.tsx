import { useCallback, useEffect, useRef, useState } from "react";
import api, { assetUrl, generateFX, generateEli, exportTest } from "../../api";
import type { ExportTestOptions } from "../../api";
import type { ScriptContent } from "../../types/script";
import type { ScriptRead } from "../../types/script";
import type { ThumbnailConcept } from "../../types/render";
import type { SaveState } from "../../App";
import ExportPanel from "./ExportPanel";
import ExportTestModal from "./ExportTestModal";
import PipelineSteps from "./PipelineSteps";
import PropertiesPanel from "./PropertiesPanel";
import ThumbnailModal from "./ThumbnailModal";
import TimelineLanes from "./TimelineLanes";
import VoiceSetupModal from "../brand/VoiceSetupModal";
import { useEliPosition } from "./useEliPosition";
import { usePublishState } from "./usePublishState";
import { useRenderState } from "./useRenderState";
import { useTimelineState } from "./useTimelineState";
import { useVoicePicker } from "./useVoicePicker";
import { useKeyboardShortcuts, ShortcutHelpOverlay } from "./useKeyboardShortcuts";
import { DEFAULT_BAR_COLOR } from "./constants";

interface Props {
  scriptId: string;
  onBack: () => void;
  onSaveStateChange?: (state: SaveState) => void;
}

export default function TimelinePage({ scriptId, onBack, onSaveStateChange }: Props) {
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
        <p className="text-neutral-400">Loading timeline...</p>
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

  return <TimelineEditor scriptId={scriptId} initialContent={script.script} title={script.topic_title} onBack={onBack} onSaveStateChange={onSaveStateChange} />;
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

function TimelineEditor({
  scriptId,
  initialContent,
  title,
  onBack,
  onSaveStateChange,
}: {
  scriptId: string;
  initialContent: ScriptContent;
  title: string;
  onBack: () => void;
  onSaveStateChange?: (state: SaveState) => void;
}) {
  const state = useTimelineState(scriptId, initialContent);
  const render = useRenderState(scriptId, title);
  const publish = usePublishState(scriptId);

  // Voice picker hook
  const voicePicker = useVoicePicker();

  // Eli position hook
  const eliPosition = useEliPosition(initialContent);

  const [showExport, setShowExport] = useState(false);
  const [showVoiceSetup, setShowVoiceSetup] = useState(false);
  const [pendingAudioAction, setPendingAudioAction] = useState<"all" | string | null>(null);
  const [generatingFX, setGeneratingFX] = useState(false);
  const [generatingEli, setGeneratingEli] = useState(false);
  const [confirmOverwrite, setConfirmOverwrite] = useState<"images" | "audio" | "fx" | "eli" | null>(null);
  const [pixelsPerSecond, setPixelsPerSecond] = useState(5);
  const [exportTestJobId, setExportTestJobId] = useState<string | null>(null);
  const [exportTestStep, setExportTestStep] = useState("");
  const [exportTestProgress, setExportTestProgress] = useState(0);
  const [showExportTestModal, setShowExportTestModal] = useState(false);
  const [titleCardGenerating, setTitleCardGenerating] = useState(false);
  const [titleCardGenerated, setTitleCardGenerated] = useState(false);
  const [titleCardTimestamp, setTitleCardTimestamp] = useState(0);
  const [thumbnailsInline, setThumbnailsInline] = useState<ThumbnailConcept[]>([]);
  const [thumbnailsInlineGenerating, setThumbnailsInlineGenerating] = useState(false);
  const [showThumbnailModal, setShowThumbnailModal] = useState(false);

  // Export split-button dropdown state
  const [showExportDropdown, setShowExportDropdown] = useState(false);
  const exportDropdownRef = useRef<HTMLDivElement>(null);

  // Auto-load thumbnails from disk on mount
  useEffect(() => {
    (async () => {
      try {
        const res = await api.get(`/api/thumbnail/${scriptId}`);
        if (res.ok) {
          const data = res.data as { concepts: ThumbnailConcept[] };
          if (data.concepts.length > 0) setThumbnailsInline(data.concepts);
        }
      } catch (_) { /* thumbnails are optional */ }
    })();
  }, [scriptId]);

  // Close export dropdown on outside click
  useEffect(() => {
    if (!showExportDropdown) return;
    const handler = (e: MouseEvent) => {
      if (exportDropdownRef.current && !exportDropdownRef.current.contains(e.target as Node)) {
        setShowExportDropdown(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showExportDropdown]);

  // Cancel refs for single async operations
  const fxCancelledRef = useRef(false);
  const eliCancelledRef = useRef(false);
  const titleCardCancelledRef = useRef(false);
  const thumbnailsCancelledRef = useRef(false);

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

  // Surface save state to App top bar
  useEffect(() => {
    onSaveStateChange?.({
      isDirty: state.isDirty,
      saveStatus: state.saveStatus,
      save: state.save,
      canUndo: state.canUndo,
      undo: state.undo,
    });
  }, [state.isDirty, state.saveStatus, state.canUndo, state.save, state.undo, onSaveStateChange]);

  // JIT voice check: if no voice selected and no voices available, show modal
  const tryGenerateAudio = (action: "all" | "missing" | string) => {
    if (!voicePicker.selectedVoiceId && voicePicker.voices.length === 0) {
      setPendingAudioAction(action);
      setShowVoiceSetup(true);
      return;
    }
    if (action === "all") {
      state.generateAllAudio(voicePicker.selectedVoiceId);
    } else if (action === "missing") {
      state.generateAllAudio(voicePicker.selectedVoiceId, true);
    } else {
      state.generateAudio(action, voicePicker.selectedVoiceId);
    }
  };

  const handleVoiceSelected = (voiceId: string) => {
    voicePicker.setSelectedVoiceId(voiceId);
    setShowVoiceSetup(false);
    if (pendingAudioAction === "all") {
      state.generateAllAudio(voiceId);
    } else if (pendingAudioAction === "missing") {
      state.generateAllAudio(voiceId, true);
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
            return {
              scene: sc,
              segIdx: si,
              segName: state.content.segments[si].name,
            };
          }
        }
        return null;
      })()
    : null;

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
      if (state.selectedSceneId) state.generateImage(state.selectedSceneId);
    },
    generateAllImages: () => state.generateAllImages(),
    openExport: () => setShowExport(true),
    toggleAudioPreview,
    deleteScene,
  });

  // Scene stats
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

  // Check if assets already exist for overwrite confirmation
  const hasExistingImages = allScenes.some((sc) => !sc.is_title_card && (sc.image_url || sc.frame_urls?.length));
  const hasExistingAudio = allScenes.some((sc) => sc.audio_url);
  const hasExistingFX = allScenes.some((sc) => sc.fx);
  const hasExistingEli = allScenes.some((sc) => sc.eli_overlay);

  // Check if ALL scenes are complete for each step (for completion checkmarks)
  const nonTitleScenes = allScenes.filter((sc) => !sc.is_title_card);
  // Narrated non-title scenes: the set that gets audio, Eli, and FX generated
  const narratedScenes = nonTitleScenes.filter((sc) => sc.narration);
  // Image scenes: non-title scenes that have a visual_prompt (excludes aha_subtitle which are text-on-black)
  const imageScenes = nonTitleScenes.filter((sc) => sc.visual_prompt);
  const allImagesGenerated = imageScenes.length > 0 && imageScenes.every((sc) => sc.image_url || sc.frame_urls?.length);
  const allAudioGenerated = narratedScenes.length > 0 && narratedScenes.every((sc) => sc.audio_url);
  const allFXGenerated = nonTitleScenes.length > 0 && nonTitleScenes.every((sc) => sc.fx);
  const allEliGenerated = narratedScenes.length > 0 && narratedScenes.every((sc) => sc.eli_overlay);

  const confirmAndGenerateImages = () => {
    if (hasExistingImages) {
      setConfirmOverwrite("images");
    } else {
      state.generateAllImages();
    }
  };

  const confirmAndGenerateAudio = () => {
    if (hasExistingAudio) {
      setConfirmOverwrite("audio");
    } else {
      tryGenerateAudio("all");
    }
  };

  const confirmAndGenerateFX = () => {
    if (hasExistingFX) {
      setConfirmOverwrite("fx");
    } else {
      handleGenerateFX();
    }
  };

  const handleGenerateFX = async () => {
    fxCancelledRef.current = false;
    setGeneratingFX(true);
    try {
      const res = await generateFX(scriptId);
      if (fxCancelledRef.current) return;
      if (res.ok) {
        const refreshed = await api.get(`/api/scripts/${scriptId}`);
        if (refreshed.ok && !fxCancelledRef.current) {
          const data = refreshed.data as { script: ScriptContent };
          state.setContent(data.script);
        }
      }
    } finally {
      setGeneratingFX(false);
    }
  };

  const handleGenerateEli = async () => {
    eliCancelledRef.current = false;
    setGeneratingEli(true);
    try {
      const res = await generateEli(scriptId);
      if (eliCancelledRef.current) return;
      if (res.ok) {
        const refreshed = await api.get(`/api/scripts/${scriptId}`);
        if (refreshed.ok && !eliCancelledRef.current) {
          const data = refreshed.data as { script: ScriptContent };
          state.setContent(data.script);
        }
      }
    } finally {
      setGeneratingEli(false);
    }
  };

  const confirmAndGenerateEli = () => {
    if (hasExistingEli) {
      setConfirmOverwrite("eli");
    } else {
      handleGenerateEli();
    }
  };

  const generateMissingImages = () => state.generateAllImages(true);
  const generateMissingAudio = () => tryGenerateAudio("missing");
  const generateMissingFX = async () => {
    fxCancelledRef.current = false;
    setGeneratingFX(true);
    try {
      const res = await generateFX(scriptId, true);
      if (fxCancelledRef.current) return;
      if (res.ok) {
        const refreshed = await api.get(`/api/scripts/${scriptId}`);
        if (refreshed.ok && !fxCancelledRef.current) {
          const data = refreshed.data as { script: ScriptContent };
          state.setContent(data.script);
        }
      }
    } finally {
      setGeneratingFX(false);
    }
  };
  const generateMissingEli = async () => {
    eliCancelledRef.current = false;
    setGeneratingEli(true);
    try {
      const res = await generateEli(scriptId, true);
      if (eliCancelledRef.current) return;
      if (res.ok) {
        const refreshed = await api.get(`/api/scripts/${scriptId}`);
        if (refreshed.ok && !eliCancelledRef.current) {
          const data = refreshed.data as { script: ScriptContent };
          state.setContent(data.script);
        }
      }
    } finally {
      setGeneratingEli(false);
    }
  };

  const handleGenerateTitleCards = async (force = false) => {
    titleCardCancelledRef.current = false;
    setTitleCardGenerating(true);
    try {
      await state.generateTitleCardsStandalone(force);
      if (!titleCardCancelledRef.current) {
        setTitleCardGenerated(true);
        setTitleCardTimestamp(Date.now());
      }
    } finally {
      setTitleCardGenerating(false);
    }
  };

  const cancelTitleCards = () => {
    titleCardCancelledRef.current = true;
    setTitleCardGenerating(false);
  };

  const handleGenerateThumbnailsInline = async () => {
    thumbnailsCancelledRef.current = false;
    setThumbnailsInlineGenerating(true);
    try {
      const res = await api.post("/api/thumbnail/generate", {
        script_id: scriptId,
        bar_color: DEFAULT_BAR_COLOR,
        title,
      });
      if (res.ok && !thumbnailsCancelledRef.current) {
        const data = res.data as { concepts: ThumbnailConcept[] };
        setThumbnailsInline(data.concepts);
      }
    } finally {
      setThumbnailsInlineGenerating(false);
    }
  };

  // Export test: start + poll
  const handleExportTest = async (options: ExportTestOptions) => {
    setShowExportTestModal(false);
    try {
      const { job_id } = await exportTest(scriptId, options);
      setExportTestJobId(job_id);
      setExportTestStep("Starting...");
      setExportTestProgress(0);
    } catch {
      setExportTestJobId(null);
      setExportTestStep("");
      setExportTestProgress(0);
    }
  };

  useEffect(() => {
    if (!exportTestJobId) return;
    let cancelled = false;
    const poll = async () => {
      while (!cancelled) {
        await new Promise((r) => setTimeout(r, 1500));
        if (cancelled) break;
        const res = await api.get(`/api/render/status/${exportTestJobId}`);
        if (!res.ok || cancelled) break;
        const data = res.data as { status: string; progress: number; current_step: string; error: string | null };
        setExportTestStep(data.current_step);
        setExportTestProgress(data.progress);
        if (data.status === "completed") {
          setExportTestJobId(null);
          setExportTestStep("");
          setExportTestProgress(0);
          // Reload script to pick up new assets
          const refreshed = await api.get(`/api/scripts/${scriptId}`);
          if (refreshed.ok) {
            const d = refreshed.data as { script: ScriptContent };
            state.setContent(d.script);
          }
          break;
        }
        if (data.status === "failed") {
          setExportTestJobId(null);
          setExportTestStep("");
          setExportTestProgress(0);
          break;
        }
      }
    };
    poll();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [exportTestJobId]);

  // Handle scene selection
  const handleSelectScene = (sceneId: string) => {
    state.selectScene(sceneId);
  };

  return (
    <div className="flex flex-col h-[calc(100vh-105px)]">
      {/* Header — Title + Pipeline + Thumbnail */}
      <div className="flex border-b border-neutral-800/60 shrink-0">
        {/* Left — Title, Pipeline, Export */}
        <div className="flex flex-col flex-1 min-w-0">
          {/* Row 1 — Navigation + Title */}
          <div className="flex items-center gap-4 px-5 py-2.5 border-b border-neutral-800/60">
            <button
              onClick={onBack}
              className="text-sm px-3 py-1.5 text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 rounded-lg transition-colors"
            >
              &larr; Back
            </button>
            <h2 className="text-base font-semibold truncate" title={title}>{title}</h2>
            <div className="flex items-center gap-1.5">
              <span className="text-[11px] text-neutral-500 border border-neutral-700/40 px-2 py-0.5 rounded-full">
                {sceneCount} scene{sceneCount !== 1 ? "s" : ""}
              </span>
              <span className="text-[11px] text-neutral-500 border border-neutral-700/40 px-2 py-0.5 rounded-full">
                {segmentCount} segment{segmentCount !== 1 ? "s" : ""}
              </span>
              <span className="text-[11px] text-neutral-500 border border-neutral-700/40 px-2 py-0.5 rounded-full">
                {durationStr}
              </span>
              {totalWords > 0 && (
                <span className="text-[11px] text-neutral-500 border border-neutral-700/40 px-2 py-0.5 rounded-full">
                  {totalWords.toLocaleString()} words
                </span>
              )}
            </div>
          </div>

          {/* Row 2 — Pipeline Steps */}
          <PipelineSteps
            titleCardGenerating={titleCardGenerating}
            titleCardGenerated={titleCardGenerated}
            allImagesGenerated={allImagesGenerated}
            allAudioGenerated={allAudioGenerated}
            allFXGenerated={allFXGenerated}
            allEliGenerated={allEliGenerated}
            batchGenerating={state.batchGenerating}
            batchGeneratingAudio={state.batchGeneratingAudio}
            hasTitleCards={state.hasTitleCards}
            generatingFX={generatingFX}
            setGeneratingFX={setGeneratingFX}
            generatingEli={generatingEli}
            setGeneratingEli={setGeneratingEli}
            handleGenerateTitleCards={handleGenerateTitleCards}
            cancelTitleCards={cancelTitleCards}
            confirmAndGenerateImages={confirmAndGenerateImages}
            confirmAndGenerateAudio={confirmAndGenerateAudio}
            confirmAndGenerateFX={confirmAndGenerateFX}
            confirmAndGenerateEli={confirmAndGenerateEli}
            generateMissingImages={generateMissingImages}
            generateMissingAudio={generateMissingAudio}
            generateMissingFX={generateMissingFX}
            generateMissingEli={generateMissingEli}
            hasExistingImages={hasExistingImages}
            hasExistingAudio={hasExistingAudio}
            hasExistingFX={hasExistingFX}
            hasExistingEli={hasExistingEli}
            cancelImageGeneration={state.cancelImageGeneration}
            cancelAudioGeneration={state.cancelAudioGeneration}
            fxCancelledRef={fxCancelledRef}
            eliCancelledRef={eliCancelledRef}
            showVoicePicker={voicePicker.showVoicePicker}
            setShowVoicePicker={voicePicker.setShowVoicePicker}
            voices={voicePicker.voices}
            selectedVoiceId={voicePicker.selectedVoiceId}
            setSelectedVoiceId={voicePicker.setSelectedVoiceId}
            voicePickerRef={voicePicker.voicePickerRef}
            showEliPositionPicker={eliPosition.showEliPositionPicker}
            setShowEliPositionPicker={eliPosition.setShowEliPositionPicker}
            eliPositionMode={eliPosition.eliPositionMode}
            setEliPositionMode={eliPosition.setEliPositionMode}
            brandEliPosition={eliPosition.brandEliPosition}
            customEliPosition={eliPosition.customEliPosition}
            setCustomEliPosition={eliPosition.setCustomEliPosition}
            eliPositionRef={eliPosition.eliPositionRef}
            content={state.content}
            setContent={state.setContent}
            exportTestJobId={exportTestJobId}
            setExportTestJobId={setExportTestJobId}
            showExportDropdown={showExportDropdown}
            setShowExportDropdown={setShowExportDropdown}
            exportDropdownRef={exportDropdownRef}
            setShowExport={setShowExport}
            setShowExportTestModal={setShowExportTestModal}
            pixelsPerSecond={pixelsPerSecond}
            setPixelsPerSecond={setPixelsPerSecond}
          />
        </div>

        {/* Right — Thumbnail Preview */}
        <div className="shrink-0 border-l border-neutral-800/60 px-4 py-2.5 flex items-center justify-center">
          <button
            onClick={() => setShowThumbnailModal(true)}
            className="relative group"
            title="Click to manage thumbnails"
          >
            {thumbnailsInline.length > 0 && thumbnailsInline[0].image_url ? (
              <div className="relative">
                <img
                  src={assetUrl(thumbnailsInline[0].image_url)}
                  alt="Thumbnail preview"
                  className="h-36 aspect-video object-cover rounded-lg border border-neutral-700 group-hover:border-violet-500 transition-colors"
                />
                {thumbnailsInlineGenerating && (
                  <div className="absolute inset-0 bg-black/50 rounded-lg flex items-center justify-center">
                    <span className="w-5 h-5 border-2 border-violet-400 border-t-transparent rounded-full animate-spin" />
                  </div>
                )}
                <span className="absolute bottom-1 right-1 text-[10px] bg-black/70 text-neutral-300 px-1.5 py-0.5 rounded">
                  {thumbnailsInline.length} thumbnail{thumbnailsInline.length !== 1 ? "s" : ""}
                </span>
              </div>
            ) : (
              <div className={`h-36 aspect-video rounded-lg border border-dashed flex items-center justify-center transition-colors ${
                thumbnailsInlineGenerating
                  ? "border-violet-500/50 bg-violet-500/5"
                  : "border-neutral-700 bg-neutral-900/40 group-hover:border-violet-500/50"
              }`}>
                {thumbnailsInlineGenerating ? (
                  <span className="w-5 h-5 border-2 border-violet-400 border-t-transparent rounded-full animate-spin" />
                ) : (
                  <span className="text-[11px] text-neutral-600">No Thumbnail</span>
                )}
              </div>
            )}
          </button>
        </div>
      </div>

      {/* Batch Progress Bars */}
      <BatchProgressBar progress={state.batchImageProgress} label="images" />
      <BatchProgressBar progress={state.batchAudioProgress} label="audio" />
      {generatingFX && (
        <div className="px-4 py-2 border-b border-neutral-800 shrink-0 bg-amber-500/10">
          <div className="flex items-center gap-3 text-xs">
            <span className="w-3 h-3 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-neutral-300">
              Generating FX assignments with AI...
            </span>
            <div className="flex-1 h-1.5 bg-neutral-800 rounded-full overflow-hidden ml-2">
              <div className="h-full rounded-full bg-amber-500 animate-pulse" style={{ width: "60%" }} />
            </div>
          </div>
        </div>
      )}
      {generatingEli && (
        <div className="px-4 py-2 border-b border-neutral-800 shrink-0 bg-amber-500/10">
          <div className="flex items-center gap-3 text-xs">
            <span className="w-3 h-3 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-neutral-300">
              Generating Eli animation keyframes with AI...
            </span>
            <div className="flex-1 h-1.5 bg-neutral-800 rounded-full overflow-hidden ml-2">
              <div className="h-full rounded-full bg-amber-500 animate-pulse" style={{ width: "60%" }} />
            </div>
          </div>
        </div>
      )}
      {exportTestJobId && (
        <div className="px-4 py-2 border-b border-neutral-800 shrink-0 bg-rose-500/10">
          <div className="flex items-center gap-3 text-xs">
            <span className="w-3 h-3 border-2 border-rose-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-neutral-300">
              Export Test &middot; {exportTestStep || "Starting..."}
            </span>
            <div className="flex-1 h-1.5 bg-neutral-800 rounded-full overflow-hidden ml-2">
              <div
                className="h-full rounded-full bg-rose-500 transition-all duration-500"
                style={{ width: `${exportTestProgress * 100}%` }}
              />
            </div>
            <span className="text-neutral-500 tabular-nums">{Math.round(exportTestProgress * 100)}%</span>
          </div>
        </div>
      )}
      {titleCardGenerating && (
        <div className="px-4 py-2 border-b border-neutral-800 shrink-0 bg-violet-500/10">
          <div className="flex items-center gap-3 text-xs">
            <span className="w-3 h-3 border-2 border-violet-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-neutral-300">
              Generating title card composites...
            </span>
            <div className="flex-1 h-1.5 bg-neutral-800 rounded-full overflow-hidden ml-2">
              <div className="h-full rounded-full bg-violet-500 animate-pulse" style={{ width: "60%" }} />
            </div>
          </div>
        </div>
      )}
      {titleCardGenerated && !titleCardGenerating && (
        <div className="px-4 py-2 border-b border-neutral-800 shrink-0 bg-neutral-900/60">
          <div className="flex items-center gap-4">
            <span className="text-xs text-neutral-500 shrink-0">Title Cards:</span>
            <div className="flex gap-3">
              <div className="space-y-0.5">
                <img
                  src={assetUrl(`/static/projects/${scriptId}/images/composite_title_card.png`) + `?t=${titleCardTimestamp}`}
                  alt="Thumbnail"
                  className="h-16 aspect-video object-cover rounded border border-neutral-700"
                />
                <p className="text-[10px] text-neutral-500">With title</p>
              </div>
              <div className="space-y-0.5">
                <img
                  src={assetUrl(`/static/projects/${scriptId}/images/composite_title_card_notitle.png`) + `?t=${titleCardTimestamp}`}
                  alt="Title Slide"
                  className="h-16 aspect-video object-cover rounded border border-neutral-700"
                />
                <p className="text-[10px] text-neutral-500">No title</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Vertical layout: Timeline on top (full width), Properties below */}
      <div className="flex flex-col flex-1 overflow-hidden">
        {/* Main timeline area — full width */}
        <div className="overflow-auto p-4 shrink-0">
          <TimelineLanes
            content={state.content}
            selectedSceneId={state.selectedSceneId}
            onSelectScene={handleSelectScene}
            pixelsPerSecond={pixelsPerSecond}
          />
        </div>

        {/* Bottom panel: Properties */}
        {selectedScene ? (
          <PropertiesPanel
            scene={selectedScene.scene}
            segmentIdx={selectedScene.segIdx}
            segmentName={selectedScene.segName}
            scriptId={scriptId}
            onUpdate={(updates) =>
              state.updateScene(selectedScene.scene.id, updates)
            }
            onGenerateImage={() =>
              state.generateImage(selectedScene.scene.id)
            }
            isGenerating={state.generatingSceneIds.has(selectedScene.scene.id)}
            onGenerateAudio={() =>
              tryGenerateAudio(selectedScene.scene.id)
            }
            isGeneratingAudio={state.generatingAudioSceneIds.has(selectedScene.scene.id)}
          />
        ) : (
          <div className="flex-1 border-t border-neutral-800/60 px-4 py-3 flex items-center justify-center">
            <p className="text-sm text-neutral-600">
              Select a scene to edit its properties
            </p>
          </div>
        )}
      </div>

      {showExportTestModal && (
        <ExportTestModal
          onRun={handleExportTest}
          onClose={() => setShowExportTestModal(false)}
        />
      )}

      {showThumbnailModal && (
        <ThumbnailModal
          thumbnails={thumbnailsInline}
          generating={thumbnailsInlineGenerating}
          onGenerate={handleGenerateThumbnailsInline}
          onClose={() => setShowThumbnailModal(false)}
        />
      )}

      {showExport && (
        <ExportPanel
          youtubeStatus={render.youtubeStatus}
          youtubeUrl={render.youtubeUrl}
          onStartYoutubeRender={render.startYoutubeRender}
          audioUrl={render.audioUrl}
          audioExporting={render.audioExporting}
          onExportAudio={render.exportAudio}
          thumbnails={render.thumbnails}
          thumbnailsGenerating={render.thumbnailsGenerating}
          onGenerateThumbnails={() => render.generateThumbnails()}
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
          brandName=""
          onVoiceSelected={handleVoiceSelected}
          onClose={() => {
            setShowVoiceSetup(false);
            setPendingAudioAction(null);
          }}
        />
      )}

      {confirmOverwrite && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-neutral-900 border border-neutral-700 rounded-xl shadow-2xl p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold text-neutral-100 mb-2">
              Overwrite existing {confirmOverwrite}?
            </h3>
            <p className="text-sm text-neutral-400 mb-6">
              {confirmOverwrite === "images" && "Some scenes already have generated images. Regenerating will overwrite them."}
              {confirmOverwrite === "audio" && "Some scenes already have generated audio. Regenerating will overwrite them."}
              {confirmOverwrite === "fx" && "Some scenes already have FX assignments. Regenerating will overwrite them."}
              {confirmOverwrite === "eli" && "Some scenes already have Eli overlays. Regenerating will overwrite them."}
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setConfirmOverwrite(null)}
                className="px-4 py-2 text-sm rounded-lg text-neutral-300 hover:bg-neutral-800 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  const action = confirmOverwrite;
                  setConfirmOverwrite(null);
                  if (action === "images") state.generateAllImages();
                  else if (action === "audio") tryGenerateAudio("all");
                  else if (action === "fx") handleGenerateFX();
                  else if (action === "eli") handleGenerateEli();
                }}
                className="px-4 py-2 text-sm rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-medium transition-colors"
              >
                Overwrite & Regenerate
              </button>
            </div>
          </div>
        </div>
      )}

      {showHelp && <ShortcutHelpOverlay onClose={() => setShowHelp(false)} />}
    </div>
  );
}
