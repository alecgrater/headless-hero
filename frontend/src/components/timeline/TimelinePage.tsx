import { useCallback, useEffect, useRef, useState } from "react";
import { Zap } from "lucide-react";
import api, { assetUrl, generateFX, pollFXJob, generateEli, pollEliJob, exportTest, fetchScriptCost, getYouTubeOAuthStatus } from "../../api";
import type { ExportTestOptions } from "../../api";
import type { ScriptContent } from "../../types/script";
import type { ScriptRead } from "../../types/script";
import type { ThumbnailConcept } from "../../types/render";
import type { ExportBundleResponse } from "../../types/render";
import type { SaveState } from "../../App";
import type { MicroTimelineHandle } from "./SceneMicroTimeline";
import ExportPanel from "./ExportPanel";
import ExportTestModal from "./ExportTestModal";
import MediaSourcesTab from "./MediaSourcesTab";
import SegmentsTab from "./SegmentsTab";
import PipelineSteps from "./PipelineSteps";
import PropertiesPanel from "./PropertiesPanel";
import ThumbnailModal from "./ThumbnailModal";
import TimelineLanes from "./TimelineLanes";
import VoiceSetupModal from "../brand/VoiceSetupModal";
import { usePublishState } from "./usePublishState";
import { useRenderState } from "./useRenderState";
import { useTimelineState } from "./useTimelineState";
import { useMediaReview } from "./useMediaReview";
import { useOperationProgress } from "../../hooks/useOperationProgress";

import { useVoicePicker } from "./useVoicePicker";
import { useKeyboardShortcuts, ShortcutHelpOverlay } from "./useKeyboardShortcuts";

interface Props {
  scriptId: string;
  onBack: () => void;
  onSaveStateChange?: (state: SaveState) => void;
  onNavigateToSettings?: () => void;
  onRecordVoiceover?: () => void;
}

export default function TimelinePage({ scriptId, onBack, onSaveStateChange, onNavigateToSettings, onRecordVoiceover }: Props) {
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

  return <TimelineEditor scriptId={scriptId} initialContent={script.script} title={script.topic_title} onBack={onBack} onSaveStateChange={onSaveStateChange} onNavigateToSettings={onNavigateToSettings} onRecordVoiceover={onRecordVoiceover} />;
}

interface BatchProgressProps {
  progress: {
    total: number;
    completed: number;
    failed: number;
    currentSceneName: string | null;
    startedAt: number | null;
    initialEstimatedSeconds?: number | null;
  };
  label: string;
}

function BatchProgressBar({ progress, label }: BatchProgressProps) {
  if (progress.total === 0) return null;
  const done = progress.completed + progress.failed;
  const pct = done / progress.total;
  const elapsed = progress.startedAt ? (Date.now() - progress.startedAt) / 1000 : 0;
  const avgPerScene = done > 0 ? elapsed / done : 0;
  const perSceneRemaining = (progress.total - done) * avgPerScene;

  // Use per-scene average once scenes start completing; fall back to initial estimate
  let etaStr = "";
  if (done > 0 && perSceneRemaining > 0) {
    etaStr = perSceneRemaining < 60
      ? `~${Math.round(perSceneRemaining)}s left`
      : `~${Math.round(perSceneRemaining / 60)}m left`;
  } else if (done === 0 && progress.initialEstimatedSeconds && progress.initialEstimatedSeconds > 0) {
    const initRemaining = Math.max(0, progress.initialEstimatedSeconds - elapsed);
    if (initRemaining > 0) {
      etaStr = initRemaining < 60
        ? `~${Math.round(initRemaining)}s left`
        : `~${Math.round(initRemaining / 60)}m left`;
    }
  }

  // For progress bar: use per-scene pct when available, else time-based from initial estimate
  let barPct = pct;
  if (done === 0 && progress.initialEstimatedSeconds && progress.initialEstimatedSeconds > 0) {
    barPct = Math.min(0.95, Math.pow(elapsed / progress.initialEstimatedSeconds, 2));
  }

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
            style={{ width: `${barPct * 100}%` }}
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
  onNavigateToSettings,
  onRecordVoiceover,
}: {
  scriptId: string;
  initialContent: ScriptContent;
  title: string;
  onBack: () => void;
  onSaveStateChange?: (state: SaveState) => void;
  onNavigateToSettings?: () => void;
  onRecordVoiceover?: () => void;
}) {
  const state = useTimelineState(scriptId, initialContent);
  const render = useRenderState(scriptId, title, initialContent.seo_metadata);
  const publish = usePublishState(scriptId);

  // Operation progress tracking
  const fxProgress = useOperationProgress("fx_generation");
  const eliProgress = useOperationProgress("eli_generation");
  const titleCardProgress = useOperationProgress("title_card_generation");

  // Voice picker hook
  const voicePicker = useVoicePicker();

  const [showExport, setShowExport] = useState(false);
  const [showVoiceSetup, setShowVoiceSetup] = useState(false);
  const [pendingAudioAction, setPendingAudioAction] = useState<"all" | string | null>(null);
  const [generatingFX, setGeneratingFX] = useState(false);
  const [generatingEli, setGeneratingEli] = useState(false);
  const [eliStep, setEliStep] = useState<string>("");
  const [eliProgressPct, setEliProgressPct] = useState<number>(0);
  const [confirmOverwrite, setConfirmOverwrite] = useState<"images" | "audio" | "fx" | "eli" | null>(null);
  const [pixelsPerSecond, setPixelsPerSecond] = useState(20);
  const [exportTestJobId, setExportTestJobId] = useState<string | null>(null);
  const [exportTestStep, setExportTestStep] = useState("");
  const [exportTestProgress, setExportTestProgress] = useState(0);
  const [exportTestEstimatedSeconds, setExportTestEstimatedSeconds] = useState<number | null>(null);
  const [showExportTestModal, setShowExportTestModal] = useState(false);
  const [titleCardGenerating, setTitleCardGenerating] = useState(false);
  const [titleCardGenerated, setTitleCardGenerated] = useState(false);
  const [titleCardTimestamp, setTitleCardTimestamp] = useState(0);
  const [thumbnailsInline, setThumbnailsInline] = useState<ThumbnailConcept[]>([]);
  const [thumbnailsInlineGenerating, setThumbnailsInlineGenerating] = useState(false);
  const [showThumbnailModal, setShowThumbnailModal] = useState(false);
  const [totalCost, setTotalCost] = useState<number>(0);
  const [lastAudioGenTimestamp, setLastAudioGenTimestamp] = useState(0);
  const [lastFXGenTimestamp, setLastFXGenTimestamp] = useState(0);
  const [yoloRunning, setYoloRunning] = useState(false);
  const [youtubeConnected, setYoutubeConnected] = useState(false);
  const [yoloStep, setYoloStep] = useState<string | null>(null);
  const [yoloError, setYoloError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"timeline" | "media-sources" | "segments">("timeline");
  const yoloCancelledRef = useRef(false);
  const microTimelineRef = useRef<MicroTimelineHandle>(null);

  const media = useMediaReview({ scriptId, content: state.content });

  // Auto-switch to Media Sources tab when new assignments arrive
  useEffect(() => {
    if (media.hasPendingReview) setActiveTab("media-sources");
  }, [media.hasPendingReview]);

  const refreshCost = useCallback(async () => {
    const data = await fetchScriptCost(scriptId);
    setTotalCost(data.total_cost);
  }, [scriptId]);

  // Fetch cost on mount
  useEffect(() => { refreshCost(); }, [refreshCost]);

  // Check YouTube connection on mount
  useEffect(() => {
    getYouTubeOAuthStatus().then((s) => setYoutubeConnected(s.youtube.connected));
  }, []);

  // Refresh cost when image or audio batch generation completes
  const imgDone = state.batchImageProgress.total > 0 && (state.batchImageProgress.completed + state.batchImageProgress.failed) >= state.batchImageProgress.total;
  const audioDone = state.batchAudioProgress.total > 0 && (state.batchAudioProgress.completed + state.batchAudioProgress.failed) >= state.batchAudioProgress.total;
  useEffect(() => { if (imgDone) refreshCost(); }, [imgDone, refreshCost]);
  useEffect(() => { if (audioDone) refreshCost(); }, [audioDone, refreshCost]);

  // Track audio/FX generation timestamps for staleness detection
  const prevBatchAudio = useRef(false);
  const prevSingleAudioCount = useRef(0);
  useEffect(() => {
    // Detect batch audio completion (was generating, now done)
    if (prevBatchAudio.current && !state.batchGeneratingAudio) {
      setLastAudioGenTimestamp(Date.now());
    }
    prevBatchAudio.current = state.batchGeneratingAudio;
  }, [state.batchGeneratingAudio]);
  useEffect(() => {
    // Detect single-scene audio completion (generating set was non-empty, now empty)
    const count = state.generatingAudioSceneIds.size;
    if (prevSingleAudioCount.current > 0 && count === 0) {
      setLastAudioGenTimestamp(Date.now());
    }
    prevSingleAudioCount.current = count;
  }, [state.generatingAudioSceneIds]);

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
    splitAtPlayhead: () => {
      // Split is available via waveform click in SceneMicroTimeline — no direct
      // playhead access from TimelinePage, so this remains a no-op here.
    },
    placeMarker: () => {
      microTimelineRef.current?.placeMarkerAtPlayhead();
    },
    nudgeBack: (large: boolean) => {
      microTimelineRef.current?.nudge(large ? -10 : -1);
    },
    nudgeForward: (large: boolean) => {
      microTimelineRef.current?.nudge(large ? 10 : 1);
    },
    selectLane: (lane: number) => {
      const lanes: Array<"images" | "fx" | "inout"> = ["images", "fx", "inout"];
      microTimelineRef.current?.setSelectedLane(lanes[lane - 1] ?? null);
    },
    deselectMicroTimeline: () => {
      microTimelineRef.current?.setSelectedLane(null);
    },
    deleteMarker: () => {
      if (microTimelineRef.current?.hasSelectedMarker()) {
        microTimelineRef.current.deleteSelectedMarker();
      }
      // If no marker selected, intentionally do nothing
    },
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

  // Media source counts (exclude title cards)
  const mediaCounts = allScenes
    .filter((sc) => !sc.is_title_card)
    .reduce(
      (acc, sc) => {
        const src = sc.media_source ?? "ai";
        acc[src] = (acc[src] ?? 0) + 1;
        return acc;
      },
      {} as Record<string, number>,
    );

  // Check if assets already exist for overwrite confirmation
  const hasExistingImages = allScenes.some((sc) => !sc.is_title_card && (sc.image_url || sc.frame_urls?.length));
  const hasExistingAudio = allScenes.some((sc) => sc.audio_url);
  const hasExistingFX = allScenes.some((sc) => sc.fx);

  // Check if ALL scenes are complete for each step (for completion checkmarks)
  const nonTitleScenes = allScenes.filter((sc) => !sc.is_title_card);
  const titleScenes = allScenes.filter((sc) => sc.is_title_card);
  // Audio generates for ALL scenes with narration (including title cards)
  const narratedScenes = allScenes.filter((sc) => sc.narration);
  // Image scenes: non-title scenes that have a visual_prompt (excludes aha_subtitle which are text-on-black)
  const imageScenes = nonTitleScenes.filter((sc) => sc.visual_prompt);
  // Title cards complete when all title card scenes have an image
  const allTitleCardsGenerated = titleScenes.length > 0 && titleScenes.every((sc) => sc.image_url);
  const allImagesGenerated = imageScenes.length > 0 && imageScenes.every((sc) => sc.image_url || sc.frame_urls?.length);
  const allAudioGenerated = narratedScenes.length > 0 && narratedScenes.every((sc) => sc.audio_url);
  const allFXGenerated = nonTitleScenes.length > 0 && nonTitleScenes.every((sc) => sc.fx);

  // Missing counts for "Generate Missing (N)" labels
  const missingImageCount = imageScenes.filter((sc) => !sc.image_url && !sc.frame_urls?.length).length;
  const missingAudioCount = narratedScenes.filter((sc) => !sc.audio_url).length;
  const missingFXCount = nonTitleScenes.filter((sc) => !sc.fx).length;

  // Eli generates for narrated non-title scenes without a person (backend skips contains_person)
  const eliScenes = nonTitleScenes.filter((sc) => sc.narration && !sc.contains_person);
  const allEliGenerated = eliScenes.length > 0 && eliScenes.every((sc) => sc.eli_overlay);
  const hasExistingEli = allScenes.some((sc) => sc.eli_overlay);
  const missingEliCount = eliScenes.filter((sc) => !sc.eli_overlay).length;

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
    const sceneCount = state.content.segments.reduce((n, seg) => n + seg.scenes.length, 0);
    fxCancelledRef.current = false;
    setGeneratingFX(true);
    fxProgress.start(sceneCount);
    try {
      const res = await generateFX(scriptId);
      if (fxCancelledRef.current) return;
      if (res.ok) {
        const { job_id } = res.data as { job_id: string };
        await pollFXJob(job_id);
        if (fxCancelledRef.current) return;
        const refreshed = await api.get(`/api/scripts/${scriptId}`);
        if (refreshed.ok && !fxCancelledRef.current) {
          const data = refreshed.data as { script: ScriptContent };
          state.setContent(data.script);
        }
      }
    } finally {
      setGeneratingFX(false);
      fxProgress.end(sceneCount);
      setLastFXGenTimestamp(Date.now());
      refreshCost();
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
        const { job_id } = res.data as { job_id: string };
        await pollFXJob(job_id);
        if (fxCancelledRef.current) return;
        const refreshed = await api.get(`/api/scripts/${scriptId}`);
        if (refreshed.ok && !fxCancelledRef.current) {
          const data = refreshed.data as { script: ScriptContent };
          state.setContent(data.script);
        }
      }
    } finally {
      setGeneratingFX(false);
      setLastFXGenTimestamp(Date.now());
    }
  };

  const handleGenerateEli = async () => {
    const sceneCount = state.content.segments.reduce((n, seg) => n + seg.scenes.length, 0);
    eliCancelledRef.current = false;
    setGeneratingEli(true);
    setEliStep("");
    setEliProgressPct(0);
    eliProgress.start(sceneCount);
    try {
      const res = await generateEli(scriptId);
      if (eliCancelledRef.current) return;
      if (!res.ok) return;
      const { job_id } = res.data as { job_id: string };
      await pollEliJob(job_id, (status) => {
        if (status.current_step) setEliStep(status.current_step);
        if (typeof status.progress === "number") setEliProgressPct(status.progress);
      });
      if (eliCancelledRef.current) return;
      const refreshed = await api.get(`/api/scripts/${scriptId}`);
      if (refreshed.ok && !eliCancelledRef.current) {
        const data = refreshed.data as { script: ScriptContent };
        state.setContent(data.script);
      }
    } finally {
      setGeneratingEli(false);
      setEliStep("");
      setEliProgressPct(0);
      eliProgress.end(sceneCount);
      refreshCost();
    }
  };

  const confirmAndGenerateEli = () => {
    if (hasExistingEli) {
      setConfirmOverwrite("eli");
    } else {
      handleGenerateEli();
    }
  };

  const generateMissingEli = async () => {
    eliCancelledRef.current = false;
    setGeneratingEli(true);
    setEliStep("");
    setEliProgressPct(0);
    try {
      const res = await generateEli(scriptId, true);
      if (eliCancelledRef.current) return;
      if (!res.ok) return;
      const { job_id } = res.data as { job_id: string };
      await pollEliJob(job_id, (status) => {
        if (status.current_step) setEliStep(status.current_step);
        if (typeof status.progress === "number") setEliProgressPct(status.progress);
      });
      if (eliCancelledRef.current) return;
      const refreshed = await api.get(`/api/scripts/${scriptId}`);
      if (refreshed.ok && !eliCancelledRef.current) {
        const data = refreshed.data as { script: ScriptContent };
        state.setContent(data.script);
      }
    } finally {
      setGeneratingEli(false);
      setEliStep("");
      setEliProgressPct(0);
      refreshCost();
    }
  };

  const cancelYolo = () => {
    yoloCancelledRef.current = true;
    titleCardCancelledRef.current = true;
    thumbnailsCancelledRef.current = true;
    fxCancelledRef.current = true;
    eliCancelledRef.current = true;
    state.cancelImageGeneration();
    state.cancelAudioGeneration();
    setYoloRunning(false);
    setYoloStep(null);
  };

  const handleYolo = async () => {
    if (!voicePicker.selectedVoiceId && voicePicker.voices.length === 0) {
      setYoloError("Select a voice in settings before running YOLO");
      return;
    }

    setYoloError(null);
    setYoloRunning(true);
    yoloCancelledRef.current = false;
    let currentStep = "";

    try {
      // 1. Title Cards (+thumbnail)
      if (!allTitleCardsGenerated && state.hasTitleCards) {
        currentStep = "Title Cards";
        setYoloStep(currentStep);
        titleCardCancelledRef.current = false;
        setTitleCardGenerating(true);
        try {
          await state.generateTitleCardsStandalone();
          if (yoloCancelledRef.current) return;
          setTitleCardGenerated(true);
          setTitleCardTimestamp(Date.now());
          await handleRecompositeThumbnailInline();
        } finally {
          setTitleCardGenerating(false);
        }
        if (yoloCancelledRef.current) return;
      }

      // 2. Audio
      if (!allAudioGenerated) {
        currentStep = "Audio";
        setYoloStep(currentStep);
        await state.generateAllAudio(voicePicker.selectedVoiceId);
        if (yoloCancelledRef.current) return;
      }

      // 3. Images
      if (!allImagesGenerated) {
        currentStep = "Images";
        setYoloStep(currentStep);
        await state.generateAllImages();
        if (yoloCancelledRef.current) return;
      }

      // 4. FX
      if (!allFXGenerated) {
        currentStep = "FX";
        setYoloStep(currentStep);
        fxCancelledRef.current = false;
        setGeneratingFX(true);
        try {
          const res = await generateFX(scriptId);
          if (yoloCancelledRef.current) return;
          if (!res.ok) throw new Error("FX generation request failed");
          const { job_id } = res.data as { job_id: string };
          await pollFXJob(job_id);
          if (yoloCancelledRef.current) return;
          const refreshed = await api.get(`/api/scripts/${scriptId}`);
          if (refreshed.ok && !yoloCancelledRef.current) {
            const data = refreshed.data as { script: ScriptContent };
            state.setContent(data.script);
          }
        } finally {
          setGeneratingFX(false);
          setLastFXGenTimestamp(Date.now());
          refreshCost();
        }
        if (yoloCancelledRef.current) return;
      }

      // 5. Eli
      if (!allEliGenerated) {
        currentStep = "Eli";
        setYoloStep(currentStep);
        eliCancelledRef.current = false;
        setGeneratingEli(true);
        try {
          const res = await generateEli(scriptId);
          if (!res.ok) throw new Error("Eli generation request failed");
          if (yoloCancelledRef.current) return;
          const { job_id } = res.data as { job_id: string };
          await pollEliJob(job_id);
          if (yoloCancelledRef.current) return;
          const refreshed = await api.get(`/api/scripts/${scriptId}`);
          if (refreshed.ok && !yoloCancelledRef.current) {
            const data = refreshed.data as { script: ScriptContent };
            state.setContent(data.script);
          }
        } finally {
          setGeneratingEli(false);
          refreshCost();
        }
      }
    } catch (err) {
      if (!yoloCancelledRef.current) {
        setYoloError(`Failed during ${currentStep}: ${err instanceof Error ? err.message : "Unknown error"}`);
      }
    } finally {
      if (!yoloCancelledRef.current) {
        setYoloRunning(false);
        setYoloStep(null);
      }
    }
  };

  const handleGenerateTitleCards = async (force = false) => {
    const segCount = state.content.segments.length;
    titleCardCancelledRef.current = false;
    setTitleCardGenerating(true);
    titleCardProgress.start(segCount);
    try {
      await state.generateTitleCardsStandalone(force);
      if (!titleCardCancelledRef.current) {
        setTitleCardGenerated(true);
        setTitleCardTimestamp(Date.now());
        await handleRecompositeThumbnailInline();
      }
    } finally {
      setTitleCardGenerating(false);
      titleCardProgress.end(segCount);
    }
  };

  const cancelTitleCards = () => {
    titleCardCancelledRef.current = true;
    setTitleCardGenerating(false);
  };

  const handleRecompositeThumbnailInline = async () => {
    thumbnailsCancelledRef.current = false;
    setThumbnailsInlineGenerating(true);
    try {
      const res = await api.post("/api/thumbnail/recomposite", {
        script_id: scriptId,
      });
      if (res.ok && !thumbnailsCancelledRef.current) {
        const data = res.data as { concepts: ThumbnailConcept[] };
        setThumbnailsInline(data.concepts);
      }
    } finally {
      setThumbnailsInlineGenerating(false);
    }
  };

  const handleSmartExport = useCallback(() => {
    render.smartExportBundle(async (_result: ExportBundleResponse) => {
      await new Promise((r) => setTimeout(r, 1500));
      await api.delete(`/api/scripts/${scriptId}`);
      onBack();
    }).catch(() => {
      // Errors already surfaced via global toast interceptor
    });
  }, [render, scriptId, onBack]);

  // Export test: start + poll
  const handleExportTest = async (options: ExportTestOptions) => {
    setShowExportTestModal(false);
    try {
      const { job_id } = await exportTest(scriptId, options);
      setExportTestJobId(job_id);
      setExportTestStep("Starting...");
      setExportTestProgress(0);
      setExportTestEstimatedSeconds(null);
    } catch {
      setExportTestJobId(null);
      setExportTestStep("");
      setExportTestProgress(0);
      setExportTestEstimatedSeconds(null);
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
        const data = res.data as { status: string; progress: number; current_step: string; error: string | null; estimated_seconds: number | null };
        setExportTestStep(data.current_step);
        setExportTestProgress(data.progress);
        if (data.estimated_seconds != null) setExportTestEstimatedSeconds(data.estimated_seconds);
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

  // Handle time-based scene split via backend
  const handleSplitSceneAtTime = useCallback(async (splitTimeMs: number) => {
    if (!state.selectedSceneId) return;
    // Clear debounce to prevent auto-save race condition
    state.save();
    const res = await api.post(`/api/scripts/${scriptId}/split-scene`, {
      scene_id: state.selectedSceneId,
      split_time_ms: splitTimeMs,
    });
    if (res.ok) {
      const data = res.data as { script: ScriptContent };
      state.setContent(data.script);
    }
  }, [scriptId, state]);

  // Handle global timer toggle
  const handleToggleTimer = () => {
    const updated = {
      ...state.content,
      segment_timer_enabled: !state.content.segment_timer_enabled,
    };
    state.setContent(updated);
    // Persist immediately since setContent doesn't trigger auto-save
    api.put(`/api/scripts/${scriptId}`, { script: updated });
  };

  // Handle global subtitle highlight toggle
  const handleToggleHighlight = () => {
    const updated = {
      ...state.content,
      subtitle_highlight_enabled: state.content.subtitle_highlight_enabled === false ? true : false,
    };
    state.setContent(updated);
    api.put(`/api/scripts/${scriptId}`, { script: updated });
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
          </div>

          {/* Row 2 — Pipeline Steps */}
          <PipelineSteps
            titleCardGenerating={titleCardGenerating}
            titleCardGenerated={titleCardGenerated || allTitleCardsGenerated}
            allImagesGenerated={allImagesGenerated}
            allAudioGenerated={allAudioGenerated}
            allFXGenerated={allFXGenerated}
            batchGenerating={state.batchGenerating}
            batchGeneratingAudio={state.batchGeneratingAudio}
            hasTitleCards={state.hasTitleCards}
            generatingFX={generatingFX}
            setGeneratingFX={setGeneratingFX}
            handleGenerateTitleCards={handleGenerateTitleCards}
            cancelTitleCards={cancelTitleCards}
            confirmAndGenerateImages={confirmAndGenerateImages}
            confirmAndGenerateAudio={confirmAndGenerateAudio}
            confirmAndGenerateFX={confirmAndGenerateFX}
            generateMissingImages={generateMissingImages}
            generateMissingAudio={generateMissingAudio}
            generateMissingFX={generateMissingFX}
            hasExistingImages={hasExistingImages}
            hasExistingAudio={hasExistingAudio}
            hasExistingFX={hasExistingFX}
            missingImageCount={missingImageCount}
            missingAudioCount={missingAudioCount}
            missingFXCount={missingFXCount}
            cancelImageGeneration={state.cancelImageGeneration}
            cancelAudioGeneration={state.cancelAudioGeneration}
            fxCancelledRef={fxCancelledRef}
            showVoicePicker={voicePicker.showVoicePicker}
            setShowVoicePicker={voicePicker.setShowVoicePicker}
            voices={voicePicker.voices}
            selectedVoiceId={voicePicker.selectedVoiceId}
            setSelectedVoiceId={voicePicker.setSelectedVoiceId}
            voicePickerRef={voicePicker.voicePickerRef}
            content={state.content}
            setContent={state.setContent}
            onRecordVoiceover={onRecordVoiceover}
            exportTestJobId={exportTestJobId}
            setExportTestJobId={setExportTestJobId}
            showExportDropdown={showExportDropdown}
            setShowExportDropdown={setShowExportDropdown}
            exportDropdownRef={exportDropdownRef}
            setShowExport={setShowExport}
            setShowExportTestModal={setShowExportTestModal}
            fxPotentiallyStale={lastAudioGenTimestamp > 0 && lastAudioGenTimestamp > lastFXGenTimestamp}
            allEliGenerated={allEliGenerated}
            generatingEli={generatingEli}
            setGeneratingEli={setGeneratingEli}
            confirmAndGenerateEli={confirmAndGenerateEli}
            generateMissingEli={generateMissingEli}
            hasExistingEli={hasExistingEli}
            missingEliCount={missingEliCount}
            eliCancelledRef={eliCancelledRef}
            fxEstimatedSeconds={fxProgress.estimatedSeconds}
            fxProgressActive={fxProgress.active}
            eliEstimatedSeconds={eliProgress.estimatedSeconds}
            eliProgressActive={eliProgress.active}
            titleCardEstimatedSeconds={titleCardProgress.estimatedSeconds}
            titleCardProgressActive={titleCardProgress.active}
          />

          {/* YOLO / Stats Row */}
          {(() => {
            const remaining: string[] = [];
            if (!allTitleCardsGenerated && state.hasTitleCards) remaining.push("Title Cards");
            if (!allAudioGenerated) remaining.push("Audio");
            if (!allImagesGenerated) remaining.push("Images");
            if (!allFXGenerated) remaining.push("FX");
            if (!allEliGenerated) remaining.push("Eli");
            const allDone = remaining.length === 0;

            const statsBlock = (
              <div className="ml-auto flex items-center gap-1.5 shrink-0">
                <span className="text-xs text-neutral-400 bg-neutral-800/60 px-4 py-1 rounded-md tabular-nums">
                  {sceneCount} scene{sceneCount !== 1 ? "s" : ""}
                </span>
                <span className="text-xs text-neutral-400 bg-neutral-800/60 px-4 py-1 rounded-md tabular-nums">
                  {segmentCount} seg{segmentCount !== 1 ? "s" : ""}
                </span>
                <span className="text-xs text-neutral-400 bg-neutral-800/60 px-4 py-1 rounded-md tabular-nums font-mono">
                  {durationStr}
                </span>
                {totalWords > 0 && (
                  <span className="text-xs text-neutral-400 bg-neutral-800/60 px-4 py-1 rounded-md tabular-nums">
                    {totalWords.toLocaleString()} words
                  </span>
                )}
                <span className="text-xs text-emerald-400 bg-emerald-500/10 px-4 py-1 rounded-md tabular-nums font-medium">
                  ${totalCost.toFixed(2)}
                </span>
                {Object.keys(mediaCounts).length > 0 && (
                  <>
                    <span className="w-px h-4 bg-neutral-700/50" />
                    {mediaCounts.ai && (
                      <span className="text-xs text-violet-300 bg-violet-500/10 px-4 py-1 rounded-md tabular-nums">
                        {mediaCounts.ai} AI
                      </span>
                    )}
                    {mediaCounts.gameplay_video && (
                      <span className="text-xs text-sky-300 bg-sky-500/10 px-4 py-1 rounded-md tabular-nums">
                        {mediaCounts.gameplay_video} gameplay
                      </span>
                    )}
                    {mediaCounts.stock_photo && (
                      <span className="text-xs text-amber-300 bg-amber-500/10 px-4 py-1 rounded-md tabular-nums">
                        {mediaCounts.stock_photo} stock
                      </span>
                    )}
                    {mediaCounts.user_upload && (
                      <span className="text-xs text-emerald-300 bg-emerald-500/10 px-4 py-1 rounded-md tabular-nums">
                        {mediaCounts.user_upload} upload{mediaCounts.user_upload !== 1 ? "s" : ""}
                      </span>
                    )}
                  </>
                )}
              </div>
            );

            if (yoloRunning) {
              return (
                <div className="px-5 py-2 border-t border-neutral-800/60 shrink-0 bg-fuchsia-500/5">
                  <div className="flex items-center gap-3">
                    <button
                      onClick={cancelYolo}
                      className="px-4 py-1.5 text-xs font-semibold rounded-lg bg-red-500/70 hover:bg-red-500/90 text-white transition-colors"
                    >
                      Cancel YOLO
                    </button>
                    <span className="w-3 h-3 border-2 border-fuchsia-400/60 border-t-transparent rounded-full animate-spin" />
                    <span className="text-xs text-fuchsia-300/70 font-medium">{yoloStep}</span>
                    {statsBlock}
                  </div>
                </div>
              );
            }

            if (allDone) {
              return (
                <div className="px-5 py-2 border-t border-neutral-800/60 shrink-0">
                  <div className="flex items-center gap-2">
                    {statsBlock}
                  </div>
                </div>
              );
            }

            return (
              <div className="px-5 py-2 border-t border-neutral-800/60 shrink-0">
                <div className="flex items-center gap-3">
                  <button
                    onClick={handleYolo}
                    className="group relative px-5 py-1.5 text-xs font-bold rounded-lg transition-all overflow-hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 bg-gradient-to-r from-violet-500/80 via-fuchsia-400/70 to-amber-400/70 text-white/95 shadow-[0_0_15px_rgba(168,85,247,0.2)] hover:shadow-[0_0_22px_rgba(168,85,247,0.35)] hover:scale-[1.02]"
                  >
                    <span className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent animate-[shimmer_2s_ease-in-out_infinite]" />
                    <span className="relative flex items-center gap-1.5">
                      <Zap size={12} />
                      YOLO MODE
                    </span>
                  </button>
                  <span className="text-[11px] text-neutral-500">
                    {remaining.length} step{remaining.length !== 1 ? "s" : ""} remaining: {remaining.join(" → ")}
                  </span>
                  {yoloError && (
                    <span className="text-[11px] text-red-400">{yoloError}</span>
                  )}
                  {statsBlock}
                </div>
              </div>
            );
          })()}
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
        <div className="px-4 py-2 border-b border-neutral-800 shrink-0 bg-teal-500/10">
          <div className="flex items-center gap-3 text-xs">
            <span className="w-3 h-3 border-2 border-teal-500 border-t-transparent rounded-full animate-spin" />
            <span className="text-neutral-300">
              Generating Eli animation keyframes with AI{eliStep ? ` · ${eliStep}` : "..."}
            </span>
            <div className="flex-1 h-1.5 bg-neutral-800 rounded-full overflow-hidden ml-2">
              <div
                className="h-full rounded-full bg-teal-500 transition-all"
                style={{ width: `${Math.max(4, Math.round(eliProgressPct * 100))}%` }}
              />
            </div>
          </div>
        </div>
      )}
      {exportTestJobId && (() => {
        const remaining = exportTestEstimatedSeconds && exportTestProgress > 0 && exportTestProgress < 1
          ? Math.max(0, Math.round(exportTestEstimatedSeconds * (1 - exportTestProgress)))
          : null;
        const etaStr = remaining !== null && remaining > 0
          ? remaining >= 60
            ? `~${Math.ceil(remaining / 60)}m left`
            : `~${remaining}s left`
          : "";
        return (
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
            {etaStr && <span className="text-neutral-500">{etaStr}</span>}
            <span className="text-neutral-500 tabular-nums">{Math.round(exportTestProgress * 100)}%</span>
          </div>
        </div>
        );
      })()}
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

      {/* Tab Bar */}
      <div className="px-5 py-2 border-b border-neutral-800/60 shrink-0">
        <div className="inline-flex items-center p-1 bg-neutral-800/60 rounded-xl border border-neutral-700/40">
          <button
            onClick={() => setActiveTab("timeline")}
            className={`px-4 py-1.5 text-xs font-medium rounded-lg transition-all duration-200 ${
              activeTab === "timeline"
                ? "bg-neutral-700/80 text-white shadow-sm"
                : "text-neutral-400 hover:text-neutral-200"
            }`}
          >
            Timeline
          </button>
          <button
            onClick={() => setActiveTab("media-sources")}
            className={`relative px-4 py-1.5 text-xs font-medium rounded-lg transition-all duration-200 ${
              activeTab === "media-sources"
                ? "bg-neutral-700/80 text-white shadow-sm"
                : "text-neutral-400 hover:text-neutral-200"
            }`}
          >
            Media Sources
            {media.hasPendingReview && (
              <span className="absolute -top-1 -right-1 w-2 h-2 bg-violet-500 rounded-full" />
            )}
          </button>
          <button
            onClick={() => setActiveTab("segments")}
            className={`px-4 py-1.5 text-xs font-medium rounded-lg transition-all duration-200 ${
              activeTab === "segments"
                ? "bg-neutral-700/80 text-white shadow-sm"
                : "text-neutral-400 hover:text-neutral-200"
            }`}
          >
            Segments
          </button>
        </div>
      </div>

      {/* Tab content */}
      {activeTab === "media-sources" ? (
        <MediaSourcesTab
          scriptId={scriptId}
          content={state.content}
          mediaAssignments={media.mediaAssignments}
          mediaAnalyzing={media.mediaAnalyzing}
          mediaReviewDismissed={media.mediaReviewDismissed}
          onAnalyzeMedia={media.handleAnalyzeMedia}
          onApproved={() => {
            media.setMediaReviewDismissed(true);
            state.generateAllImages();
            setActiveTab("timeline");
          }}
        />
      ) : activeTab === "segments" ? (
        <SegmentsTab
          content={state.content}
          scriptId={scriptId}
          selectedSceneId={state.selectedSceneId}
          onSelectScene={(id) => state.selectScene(id)}
          onUpdateScene={(id, updates) => state.updateScene(id, updates)}
          onGenerateImage={(id) => state.generateImage(id)}
          onGenerateAudio={(id) => tryGenerateAudio(id)}
          generatingSceneIds={state.generatingSceneIds}
          generatingAudioSceneIds={state.generatingAudioSceneIds}
        />
      ) : (
      /* Vertical layout: Timeline on top (full width), Properties below */
      <div className="flex flex-col flex-1 overflow-hidden">
        {/* Zoom slider — always visible above timeline */}
        <div className="px-5 py-1.5 border-b border-neutral-800/60 shrink-0">
          <div className="flex items-center gap-3 w-full">
            <span className="text-[11px] text-neutral-500 shrink-0">Zoom</span>
            <input
              type="range"
              min={0}
              max={100}
              value={pixelsPerSecond}
              onChange={(e) => setPixelsPerSecond(parseInt(e.target.value, 10))}
              className="flex-1 w-full accent-violet-500"
              style={{ minWidth: 0 }}
            />
            <span className="text-[11px] text-neutral-500 font-mono shrink-0">{pixelsPerSecond}</span>
          </div>
        </div>

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
          <div className="flex-1 min-h-0 border-t border-neutral-800/60">
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
              microTimelineRef={microTimelineRef}
              onSplitScene={handleSplitSceneAtTime}
            />
          </div>
        ) : (
          <div className="flex-1 border-t border-neutral-800/60 px-4 py-3 flex items-center justify-center">
            <p className="text-sm text-neutral-600">
              Select a scene to preview
            </p>
          </div>
        )}
      </div>
      )}

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
          onGenerate={handleRecompositeThumbnailInline}
          onClose={() => setShowThumbnailModal(false)}
        />
      )}

      {showExport && (
        <ExportPanel
          youtubeStatus={render.youtubeStatus}
          youtubeUrl={render.youtubeUrl}
          onStartYoutubeRender={render.startYoutubeRender}
          thumbnails={render.thumbnails}
          thumbnailsGenerating={render.thumbnailsGenerating}
          onRecompositeThumbnail={() => render.recompositeThumbnail()}
          seoMetadata={render.seoMetadata}
          seoGenerating={render.seoGenerating}
          onGenerateSEO={render.generateSEO}
          estimatedSeconds={render.estimatedSeconds}
          exportBundleLoading={render.exportBundleLoading}
          exportBundleResult={render.exportBundleResult}
          onExportBundle={handleSmartExport}
          exportPhase={render.exportPhase}
          thumbnailProgress={render.thumbnailProgress}
          seoProgress={render.seoProgress}
          exportBundleProgress={render.exportBundleProgress}
          youtubeConnected={youtubeConnected}
          onNavigateToSettings={() => {
            setShowExport(false);
            onNavigateToSettings?.();
          }}
          seoTitle={title}
          seoDescription=""
          seoTags={[]}
          projectTitle={title}
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
