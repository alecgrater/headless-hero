import { useCallback, useEffect, useRef, useState } from "react";
import api, { assetUrl, generateFX, generateEli, exportTest } from "../../api";
import type { ExportTestOptions } from "../../api";
import type { ScriptContent } from "../../types/script";
import type { ScriptRead } from "../../types/script";
import type { VoiceInfo, VoiceListResponse } from "../../types/audio";
import type { ThumbnailConcept } from "../../types/render";
import ExportPanel from "./ExportPanel";
import ExportTestModal from "./ExportTestModal";
import PropertiesPanel from "./PropertiesPanel";
import TimelineLanes from "./TimelineLanes";
import VideoPreviewModal from "./VideoPreviewModal";
import VoiceSetupModal from "../brand/VoiceSetupModal";
import { usePublishState } from "./usePublishState";
import { useRenderState } from "./useRenderState";
import { useTimelineState } from "./useTimelineState";
import { useKeyboardShortcuts, ShortcutHelpOverlay } from "./useKeyboardShortcuts";

interface Props {
  scriptId: string;
  onBack: () => void;
}

export default function TimelinePage({ scriptId, onBack }: Props) {
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

  return <TimelineEditor scriptId={scriptId} initialContent={script.script} title={script.topic_title} onBack={onBack} />;
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
}: {
  scriptId: string;
  initialContent: ScriptContent;
  title: string;
  onBack: () => void;
}) {
  const state = useTimelineState(scriptId, initialContent);
  const render = useRenderState(scriptId, title);
  const publish = usePublishState(scriptId);
  const [showExport, setShowExport] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const [showVoiceSetup, setShowVoiceSetup] = useState(false);
  const [pendingAudioAction, setPendingAudioAction] = useState<"all" | string | null>(null);
  const [previewMode, setPreviewMode] = useState(false);
  const [generatingFX, setGeneratingFX] = useState(false);
  const [generatingEli, setGeneratingEli] = useState(false);
  const [confirmOverwrite, setConfirmOverwrite] = useState<"images" | "audio" | "fx" | "eli" | null>(null);
  const [pixelsPerSecond, setPixelsPerSecond] = useState(40);
  const [exportTestJobId, setExportTestJobId] = useState<string | null>(null);
  const [exportTestStep, setExportTestStep] = useState("");
  const [exportTestProgress, setExportTestProgress] = useState(0);
  const [showExportTestModal, setShowExportTestModal] = useState(false);
  const [titleCardGenerating, setTitleCardGenerating] = useState(false);
  const [titleCardGenerated, setTitleCardGenerated] = useState(false);
  const [titleCardTimestamp, setTitleCardTimestamp] = useState(0);
  const [thumbnailsInline, setThumbnailsInline] = useState<ThumbnailConcept[]>([]);
  const [thumbnailsInlineGenerating, setThumbnailsInlineGenerating] = useState(false);
  const [thumbnailsInlineGenerated, setThumbnailsInlineGenerated] = useState(false);
  const [showVoicePicker, setShowVoicePicker] = useState(false);
  const voicePickerRef = useRef<HTMLDivElement>(null);

  // Close voice picker on outside click
  useEffect(() => {
    if (!showVoicePicker) return;
    const handler = (e: MouseEvent) => {
      if (voicePickerRef.current && !voicePickerRef.current.contains(e.target as Node)) {
        setShowVoicePicker(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showVoicePicker]);

  // Cancel refs for single async operations
  const fxCancelledRef = useRef(false);
  const eliCancelledRef = useRef(false);
  const titleCardCancelledRef = useRef(false);
  const thumbnailsCancelledRef = useRef(false);

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
  const [voices, setVoices] = useState<VoiceInfo[]>([]);
  const [selectedVoiceId, setSelectedVoiceId] = useState<string>("");

  // Fetch default brand voice
  useEffect(() => {
    api.get("/api/brand").then((res) => {
      if (res.ok) {
        const b = res.data as { voice_id: string };
        if (b.voice_id) setSelectedVoiceId(b.voice_id);
      }
    });
  }, []);

  // Fetch available voices
  useEffect(() => {
    api.get("/api/voice/voices").then((res) => {
      if (res.ok) {
        const data = res.data as VoiceListResponse;
        setVoices(data.voices);
        // Default to brand voice, then "Social Media" voice, then first voice
        if (!selectedVoiceId && data.voices.length > 0) {
          const social = data.voices.find((v) =>
            v.name.toLowerCase().includes("social media"),
          );
          setSelectedVoiceId(social?.voice_id ?? data.voices[0].voice_id);
        }
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);



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

  const handleGenerateThumbnailsInline = async () => {
    thumbnailsCancelledRef.current = false;
    setThumbnailsInlineGenerating(true);
    try {
      const res = await api.post("/api/thumbnail/generate", {
        script_id: scriptId,
        bar_color: "0x9333EA",
        title,
      });
      if (res.ok && !thumbnailsCancelledRef.current) {
        const data = res.data as { concepts: ThumbnailConcept[] };
        setThumbnailsInline(data.concepts);
        setThumbnailsInlineGenerated(true);
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
      {/* Row 1 — Navigation + Title + Zoom + Save */}
      <div className="flex items-center gap-4 px-5 py-2.5 border-b border-neutral-800/60 shrink-0">
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

        {/* Zoom slider */}
        <div className="flex items-center gap-2 ml-2">
          <span className="text-[11px] text-neutral-500">Zoom:</span>
          <input
            type="range"
            min={20}
            max={100}
            value={pixelsPerSecond}
            onChange={(e) => setPixelsPerSecond(parseInt(e.target.value, 10))}
            className="w-20 accent-violet-500"
          />
          <span className="text-[11px] text-neutral-500 font-mono w-8">{pixelsPerSecond}</span>
        </div>

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

      {/* Row 2 — Action Bar: Sequential Pipeline */}
      <div className="flex items-center gap-1.5 px-5 py-2 border-b border-neutral-800/60 bg-neutral-900/40 shrink-0">
        {/* Pipeline Steps */}
        <div className="flex items-center gap-1.5">

          {/* Step 1 — Title Cards + Thumbnails */}
          <div className="flex items-center gap-1.5">
            <span className={`w-5 h-5 rounded-full border text-[10px] font-bold flex items-center justify-center shrink-0 ${
              titleCardGenerating || thumbnailsInlineGenerating
                ? "border-violet-400 text-violet-300 shadow-[0_0_6px_rgba(139,92,246,0.4)]"
                : (titleCardGenerated || !state.hasTitleCards) && thumbnailsInlineGenerated
                  ? "border-emerald-400 text-emerald-300 shadow-[0_0_6px_rgba(52,211,153,0.3)]"
                  : "border-neutral-600 text-neutral-500"
            }`}>1</span>
            {state.hasTitleCards && (
              <button
                onClick={titleCardGenerating ? () => { titleCardCancelledRef.current = true; setTitleCardGenerating(false); } : () => handleGenerateTitleCards(titleCardGenerated)}
                className={`text-sm px-3 py-1.5 border rounded-md font-medium transition-colors flex items-center gap-2 ${
                  titleCardGenerating
                    ? "bg-neutral-800 border-red-500/30 text-neutral-200 hover:border-red-500/50"
                    : titleCardGenerated
                      ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20"
                      : "bg-neutral-800 border-neutral-700 text-neutral-200 hover:bg-neutral-700"
                }`}
                title={titleCardGenerating ? "Cancel title card generation" : "Generate composite title card images for all segments"}
              >
                {titleCardGenerating ? (
                  <>
                    <span className="w-3.5 h-3.5 border-2 border-neutral-400/50 border-t-transparent rounded-full animate-spin" />
                    Cancel
                  </>
                ) : titleCardGenerated ? (
                  "Title Cards \u2713"
                ) : (
                  "Title Cards"
                )}
              </button>
            )}
            <button
              onClick={thumbnailsInlineGenerating ? () => { thumbnailsCancelledRef.current = true; setThumbnailsInlineGenerating(false); } : handleGenerateThumbnailsInline}
              className={`text-sm px-3 py-1.5 border rounded-md font-medium transition-colors flex items-center gap-2 ${
                thumbnailsInlineGenerating
                  ? "bg-neutral-800 border-red-500/30 text-neutral-200 hover:border-red-500/50"
                  : thumbnailsInlineGenerated
                    ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400 hover:bg-emerald-500/20"
                    : "bg-neutral-800 border-neutral-700 text-neutral-200 hover:bg-neutral-700"
              }`}
              title={thumbnailsInlineGenerating ? "Cancel thumbnail generation" : "Generate 3 YouTube thumbnail concepts"}
            >
              {thumbnailsInlineGenerating ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-neutral-400/50 border-t-transparent rounded-full animate-spin" />
                  Cancel
                </>
              ) : thumbnailsInlineGenerated ? (
                "Thumbnails \u2713"
              ) : (
                "Thumbnails"
              )}
            </button>
          </div>

          {/* Arrow connector */}
          <span className="text-neutral-600 text-sm font-medium select-none">\u203A</span>

          {/* Step 2 — Generate Images */}
          <div className="flex items-center gap-1.5">
            <span className={`w-5 h-5 rounded-full border text-[10px] font-bold flex items-center justify-center shrink-0 ${
              state.batchGenerating
                ? "border-violet-400 text-violet-300 shadow-[0_0_6px_rgba(139,92,246,0.4)]"
                : "border-neutral-600 text-neutral-500"
            }`}>2</span>
            <button
              onClick={state.batchGenerating ? () => state.cancelImageGeneration() : confirmAndGenerateImages}
              className={`text-sm px-3 py-1.5 bg-neutral-800 border border-neutral-700 text-neutral-200 hover:bg-neutral-700 rounded-md font-medium transition-colors flex items-center gap-2 ${
                state.batchGenerating ? "border-red-500/30 hover:border-red-500/50" : ""
              }`}
              title={state.batchGenerating ? "Cancel image generation" : "Generate images for all scenes with visual prompts"}
            >
              {state.batchGenerating ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-neutral-400/50 border-t-transparent rounded-full animate-spin" />
                  Cancel
                </>
              ) : (
                "Generate Images"
              )}
            </button>
          </div>

          {/* Arrow connector */}
          <span className="text-neutral-600 text-sm font-medium select-none">\u203A</span>

          {/* Step 3 — Generate Audio (split-button with voice picker) */}
          <div className="flex items-center gap-1.5">
            <span className={`w-5 h-5 rounded-full border text-[10px] font-bold flex items-center justify-center shrink-0 ${
              state.batchGeneratingAudio
                ? "border-violet-400 text-violet-300 shadow-[0_0_6px_rgba(139,92,246,0.4)]"
                : "border-neutral-600 text-neutral-500"
            }`}>3</span>
            <div ref={voicePickerRef} className="relative flex items-stretch">
              <button
                onClick={state.batchGeneratingAudio ? () => state.cancelAudioGeneration() : confirmAndGenerateAudio}
                disabled={!state.batchGeneratingAudio && !selectedVoiceId && voices.length > 0}
                className={`text-sm pl-3 pr-2 py-1.5 bg-neutral-800 border border-r-0 border-neutral-700 text-neutral-200 hover:bg-neutral-700 disabled:opacity-40 disabled:cursor-not-allowed rounded-l-md font-medium transition-colors flex flex-col items-start gap-0 ${
                  state.batchGeneratingAudio ? "border-red-500/30 hover:border-red-500/50" : ""
                }`}
                title={state.batchGeneratingAudio ? "Cancel audio generation" : "Generate audio for all scenes with narration"}
              >
                {state.batchGeneratingAudio ? (
                  <span className="flex items-center gap-2">
                    <span className="w-3.5 h-3.5 border-2 border-neutral-400/50 border-t-transparent rounded-full animate-spin" />
                    Cancel
                  </span>
                ) : (
                  <>
                    <span>Generate Audio</span>
                    {voices.find((v) => v.voice_id === selectedVoiceId)?.name && (
                      <span className="text-[10px] text-neutral-500 leading-tight">{voices.find((v) => v.voice_id === selectedVoiceId)?.name}</span>
                    )}
                  </>
                )}
              </button>
              {!state.batchGeneratingAudio && (
                <button
                  onClick={() => setShowVoicePicker((prev) => !prev)}
                  className="text-sm px-1.5 bg-neutral-800 border border-l-0 border-neutral-700 text-neutral-400 hover:bg-neutral-700 hover:text-neutral-200 rounded-r-md transition-colors flex items-center"
                  title="Select voice"
                >
                  <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none">
                    <path d="M3 5L6 8L9 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </button>
              )}
              {state.batchGeneratingAudio && (
                <span className="text-sm px-1.5 bg-neutral-800 border border-l-0 border-red-500/30 rounded-r-md flex items-center">
                  <svg className="w-3 h-3 text-neutral-600" viewBox="0 0 12 12" fill="none">
                    <path d="M3 5L6 8L9 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </span>
              )}
              {/* Voice picker popover */}
              {showVoicePicker && (
                <div className="absolute top-full left-0 mt-1 w-56 bg-neutral-800 border border-neutral-700 rounded-lg shadow-xl z-50 py-1 max-h-60 overflow-y-auto">
                  {voices.length === 0 ? (
                    <div className="px-3 py-2 text-xs text-neutral-500">No voices available</div>
                  ) : (
                    voices.map((v) => (
                      <button
                        key={v.voice_id}
                        onClick={() => { setSelectedVoiceId(v.voice_id); setShowVoicePicker(false); }}
                        className={`w-full text-left px-3 py-1.5 text-sm transition-colors flex items-center justify-between ${
                          v.voice_id === selectedVoiceId
                            ? "bg-violet-500/15 text-violet-300"
                            : "text-neutral-300 hover:bg-neutral-700"
                        }`}
                      >
                        <span>{v.name}</span>
                        {v.voice_id === selectedVoiceId && (
                          <svg className="w-3.5 h-3.5 text-violet-400" viewBox="0 0 14 14" fill="none">
                            <path d="M2 7L5.5 10.5L12 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                          </svg>
                        )}
                      </button>
                    ))
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Arrow connector */}
          <span className="text-neutral-600 text-sm font-medium select-none">\u203A</span>

          {/* Step 4 — Add Eli */}
          <div className="flex items-center gap-1.5">
            <span className={`w-5 h-5 rounded-full border text-[10px] font-bold flex items-center justify-center shrink-0 ${
              generatingEli
                ? "border-violet-400 text-violet-300 shadow-[0_0_6px_rgba(139,92,246,0.4)]"
                : "border-neutral-600 text-neutral-500"
            }`}>4</span>
            <button
              onClick={generatingEli ? () => { eliCancelledRef.current = true; setGeneratingEli(false); } : confirmAndGenerateEli}
              className={`text-sm px-3 py-1.5 bg-neutral-800 border border-neutral-700 text-neutral-200 hover:bg-neutral-700 rounded-md font-medium transition-colors flex items-center gap-2 ${
                generatingEli ? "border-red-500/30 hover:border-red-500/50" : ""
              }`}
              title={generatingEli ? "Cancel Eli generation" : "Add Eli character overlay to all scenes (requires voiceover)"}
            >
              {generatingEli ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-neutral-400/50 border-t-transparent rounded-full animate-spin" />
                  Cancel
                </>
              ) : (
                "Add Eli"
              )}
            </button>
          </div>

          {/* Divider + Generate FX (supplementary, unnumbered) */}
          <div className="w-px h-5 bg-neutral-700/50 mx-1" />
          <button
            onClick={generatingFX ? () => { fxCancelledRef.current = true; setGeneratingFX(false); } : confirmAndGenerateFX}
            className={`text-sm px-3 py-1.5 border rounded-md font-medium transition-colors flex items-center gap-2 ${
              generatingFX
                ? "bg-neutral-800 border-red-500/30 text-neutral-200 hover:border-red-500/50"
                : "bg-neutral-800/60 border-neutral-700/50 text-neutral-500 hover:bg-neutral-700/40 hover:text-neutral-400"
            }`}
            title={generatingFX ? "Cancel FX generation" : "Use AI to assign visual effects to all scenes"}
          >
            {generatingFX ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-neutral-400/50 border-t-transparent rounded-full animate-spin" />
                Cancel
              </>
            ) : (
              "Generate FX"
            )}
          </button>
        </div>

        {/* Push preview + export to the right */}
        <div className="ml-auto flex items-center gap-1.5">
          {/* Preview group */}
          <div className="flex items-center gap-1">
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

          {/* Export Test */}
          <button
            onClick={exportTestJobId ? () => setExportTestJobId(null) : () => setShowExportTestModal(true)}
            className={`text-sm px-3 py-1.5 border rounded-lg font-semibold transition-colors flex items-center gap-2 ${
              exportTestJobId
                ? "bg-rose-500/10 border-red-500/30 text-rose-400 hover:border-red-500/50"
                : "bg-rose-500/10 border-rose-500/20 text-rose-400 hover:bg-rose-500/15"
            }`}
            title={exportTestJobId ? "Cancel export test" : "Run full pipeline for scene 1 and copy to Downloads"}
          >
            {exportTestJobId ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-rose-400/50 border-t-transparent rounded-full animate-spin" />
                Cancel
              </>
            ) : (
              "Export Test"
            )}
          </button>

          {/* Export CTA */}
          <button
            onClick={() => setShowExport(true)}
            className="btn-primary text-sm px-4 py-1.5 rounded-lg font-semibold"
            title="Export & Render (Cmd+E)"
          >
            Export
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
      {thumbnailsInlineGenerating && (
        <div className="px-4 py-2 border-b border-neutral-800 shrink-0 bg-amber-500/10">
          <div className="flex items-center gap-3 text-xs">
            <span className="w-3 h-3 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-neutral-300">
              Generating thumbnail concepts...
            </span>
            <div className="flex-1 h-1.5 bg-neutral-800 rounded-full overflow-hidden ml-2">
              <div className="h-full rounded-full bg-amber-500 animate-pulse" style={{ width: "60%" }} />
            </div>
          </div>
        </div>
      )}
      {thumbnailsInlineGenerated && !thumbnailsInlineGenerating && thumbnailsInline.length > 0 && (
        <div className="px-4 py-2 border-b border-neutral-800 shrink-0 bg-neutral-900/60">
          <div className="flex items-center gap-4">
            <span className="text-xs text-neutral-500 shrink-0">Thumbnails:</span>
            <div className="flex gap-3">
              {thumbnailsInline.map((t) => (
                <div key={t.idx} className="space-y-0.5">
                  {t.image_url ? (
                    <img
                      src={assetUrl(t.image_url)}
                      alt={t.title_text}
                      className="h-16 aspect-video object-cover rounded border border-neutral-700 cursor-pointer hover:border-violet-500 transition-colors"
                    />
                  ) : t.error ? (
                    <div className="h-16 aspect-video bg-red-500/10 rounded flex items-center justify-center text-[10px] text-red-400 px-1">
                      Error
                    </div>
                  ) : null}
                  <p className="text-[10px] text-neutral-500 truncate max-w-[120px]">{t.title_text}</p>
                </div>
              ))}
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
            onPreviewScene={() =>
              render.previewScene(selectedScene.scene.id)
            }
            isPreviewingScene={render.previewingSceneId === selectedScene.scene.id}
            previewVideoUrl={render.previewVideoUrl}
            previewMode={previewMode}
            onPrevScene={selectPrevScene}
            onNextScene={selectNextScene}
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
