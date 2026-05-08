import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import api, { assetUrl, uploadRecordingTake, importRecordingTake } from "../../api";
import { showToast } from "../ToastContainer";
import type { ScriptContent, ScriptRead, Scene } from "../../types/script";
import SceneNavigator, { type SceneScore } from "./SceneNavigator";
import TeleprompterPanel, { type DeliveryAnnotations } from "./TeleprompterPanel";
import TakePanel, { type Take } from "./TakePanel";
import ExportSection from "./ExportSection";
import PunchInMode from "./PunchInMode";
import { useRecorder } from "./useRecorder";
import { useAudioDevices } from "./useAudioDevices";

interface Props {
  scriptId: string;
  onClose: () => void;
}

interface SessionData {
  selected_takes: Record<string, number>;
  flagged_scenes: Record<string, number> | string[];
  trim_points: Record<string, number>;
  settings: Record<string, unknown>;
}

interface WordTimestamp {
  word: string;
  start_ms: number;
  end_ms: number;
}

interface DeviationData {
  match_ratio: number;
  deviations: Array<{ type: string; expected?: string; actual?: string; position: number }>;
}

type RecordingMode = "single" | "continuous" | "free";

export default function VoiceoverRecordingPage({ scriptId, onClose }: Props) {
  const [content, setContent] = useState<ScriptContent | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeSceneId, setActiveSceneId] = useState<string | null>(null);
  const [session, setSession] = useState<SessionData>({ selected_takes: {}, flagged_scenes: [], trim_points: {}, settings: {} });
  const [takes, setTakes] = useState<Take[]>([]);
  const [countdown, setCountdown] = useState<number | null>(null);
  const [timingOffsetMs, setTimingOffsetMs] = useState(0);
  const [filter, setFilter] = useState<"all" | "unrecorded" | "flagged" | "low-score">("all");
  const [playingTakeNumber, setPlayingTakeNumber] = useState<number | null>(null);
  const pausedTakeRef = useRef<{ takeNumber: number; filename: string } | null>(null);
  const [showTrim, setShowTrim] = useState(false);
  const [showExport, setShowExport] = useState(false);
  const [mode, setMode] = useState<RecordingMode>("single");
  const [rehearseMode, setRehearseMode] = useState(false);
  const [autoAdvancing, setAutoAdvancing] = useState(false);
  const autoAdvanceTimerRef = useRef<number | null>(null);
  const hasSpokenRef = useRef(false);
  const silenceStartRef = useRef<number | null>(null);
  const silenceRafRef = useRef<number>(0);
  const pendingAutoAdvanceRef = useRef<string | null>(null);
  const handleStartRecordingRef = useRef<() => Promise<void>>(() => Promise.resolve());
  const abortCountdownRef = useRef(false);

  // Phase 1A: Preview timestamps from align-take
  const [previewTimestamps, setPreviewTimestamps] = useState<WordTimestamp[] | null>(null);
  // Phase 1B: Deviation data per scene/take
  const [deviationData, setDeviationData] = useState<Record<string, DeviationData>>({});
  // Phase 3C: Delivery annotations
  const [annotations, setAnnotations] = useState<Record<string, DeliveryAnnotations>>({});
  // Phase 4C: AI reference playback
  const [playingReference, setPlayingReference] = useState(false);
  const [referenceElapsedMs, setReferenceElapsedMs] = useState(0);
  // Phase 5A: Punch-in mode
  const [showPunchIn, setShowPunchIn] = useState(false);
  // Voiceover scoring
  const [scores, setScores] = useState<Record<string, SceneScore>>({});
  const [scoring, setScoring] = useState(false);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const referenceAudioRef = useRef<HTMLAudioElement | null>(null);
  const referenceTimerRef = useRef<number | null>(null);
  const recorder = useRecorder();
  const audioDevices = useAudioDevices();

  // Load script content
  useEffect(() => {
    api.get(`/api/scripts/${scriptId}`).then((res) => {
      if (res.ok) {
        const data = res.data as ScriptRead;
        setContent(data.script);
        // Select first narrated scene
        for (const seg of data.script.segments) {
          for (const sc of seg.scenes) {
            if (sc.narration) {
              setActiveSceneId(sc.id);
              setLoading(false);
              return;
            }
          }
        }
      }
      setLoading(false);
    });
  }, [scriptId]);

  // Load session
  useEffect(() => {
    api.get(`/api/recording/session/${scriptId}`).then((res) => {
      if (res.ok) {
        setSession(res.data as SessionData);
      }
    });
  }, [scriptId]);

  // Load existing takes from backend (initial hydration only)
  const takesHydratedRef = useRef(false);
  useEffect(() => {
    if (!content || takesHydratedRef.current) return;
    takesHydratedRef.current = true;
    api.get(`/api/recording/takes/${scriptId}`).then((res) => {
      if (res.ok) {
        const data = res.data as { takes: Array<{ filename: string; sceneId: string; takeNumber: number; durationSeconds: number }> };
        setTakes(data.takes.map((t) => ({
          filename: t.filename,
          sceneId: t.sceneId,
          takeNumber: t.takeNumber,
          durationSeconds: t.durationSeconds,
        })));
      }
    });
  }, [content, scriptId]);

  // Fetch delivery annotations for active scene
  const fetchedAnnotationsRef = useRef<Set<string>>(new Set());
  useEffect(() => {
    if (!activeSceneId || fetchedAnnotationsRef.current.has(activeSceneId)) return;
    fetchedAnnotationsRef.current.add(activeSceneId);
    api.post("/api/recording/annotate-delivery", { script_id: scriptId, scene_id: activeSceneId }).then((res) => {
      if (res.ok) {
        setAnnotations((prev) => ({ ...prev, [activeSceneId]: res.data as DeliveryAnnotations }));
      }
    });
  }, [activeSceneId, scriptId]);

  const saveSession = useCallback(async (updated: SessionData) => {
    setSession(updated);
    await api.put(`/api/recording/session/${scriptId}`, updated);
  }, [scriptId]);

  const activeScene: Scene | null = (() => {
    if (!content || !activeSceneId) return null;
    for (const seg of content.segments) {
      for (const sc of seg.scenes) {
        if (sc.id === activeSceneId) return sc;
      }
    }
    return null;
  })();

  const recordedScenes = useMemo(() => new Set(Object.keys(session.selected_takes)), [session.selected_takes]);

  const allNarratedSceneIds = useMemo(() => {
    if (!content) return [];
    const ids: string[] = [];
    for (const seg of content.segments) {
      for (const sc of seg.scenes) {
        if (sc.narration) ids.push(sc.id);
      }
    }
    return ids;
  }, [content]);

  const findNextUnrecordedScene = useCallback((afterId: string | null): string | null => {
    if (!afterId) return null;
    const idx = allNarratedSceneIds.indexOf(afterId);
    if (idx === -1) return null;
    for (let i = idx + 1; i < allNarratedSceneIds.length; i++) {
      if (!recordedScenes.has(allNarratedSceneIds[i])) return allNarratedSceneIds[i];
    }
    for (let i = 0; i < idx; i++) {
      if (!recordedScenes.has(allNarratedSceneIds[i])) return allNarratedSceneIds[i];
    }
    return null;
  }, [allNarratedSceneIds, recordedScenes]);

  const beepCtxRef = useRef<AudioContext | null>(null);
  const playBeep = useCallback((freq = 880) => {
    try {
      if (!beepCtxRef.current || beepCtxRef.current.state === "closed") {
        beepCtxRef.current = new AudioContext();
      }
      const ctx = beepCtxRef.current;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = freq;
      gain.gain.value = 0.15;
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.12);
    } catch {
      // AudioContext creation can fail silently
    }
  }, []);

  // Phase 1A: Align take on selection for instant feedback
  const alignTake = useCallback(async (sceneId: string, takeNumber: number) => {
    const res = await api.post("/api/recording/align-take", {
      script_id: scriptId,
      scene_id: sceneId,
      take_number: takeNumber,
    });
    if (res.ok) {
      const data = res.data as {
        word_timestamps: WordTimestamp[];
        duration_seconds: number;
        deviation: DeviationData | null;
      };
      setPreviewTimestamps(data.word_timestamps);
      if (data.deviation) {
        setDeviationData((prev) => ({ ...prev, [`${sceneId}:${takeNumber}`]: data.deviation! }));
      }
    }
  }, [scriptId]);

  // Score all selected takes (background job with polling)
  const handleScoreAll = useCallback(async () => {
    setScoring(true);
    const res = await api.post("/api/recording/score-all", { script_id: scriptId });
    if (!res.ok) {
      showToast((res.data as { detail?: string }).detail || "Scoring failed");
      setScoring(false);
      return;
    }
    const { job_id } = res.data as { job_id: string };

    // Poll for completion
    const poll = async () => {
      const statusRes = await api.get(`/api/recording/score-status/${job_id}`);
      if (!statusRes.ok) {
        showToast("Failed to check scoring status");
        setScoring(false);
        return;
      }
      const job = statusRes.data as { status: string; progress: number; scores: Record<string, SceneScore>; error: string | null };
      if (job.status === "completed") {
        setScores(job.scores);
        const count = Object.keys(job.scores).length;
        const lowCount = Object.values(job.scores).filter((s) => s.overall < 7).length;
        showToast(`Scored ${count} scenes — ${lowCount} need attention`);
        setScoring(false);
      } else if (job.status === "failed") {
        showToast(job.error || "Scoring failed");
        setScoring(false);
      } else {
        setTimeout(poll, 2000);
      }
    };
    setTimeout(poll, 2000);
  }, [scriptId]);

  const handleStartRecording = useCallback(async () => {
    if (rehearseMode || !activeSceneId || !audioDevices.selectedDeviceId) return;

    // Stop reference playback if active
    if (playingReference) {
      referenceAudioRef.current?.pause();
      setPlayingReference(false);
      if (referenceTimerRef.current) cancelAnimationFrame(referenceTimerRef.current);
    }

    if (mode === "free") {
      // Free mode: no countdown, start immediately
      hasSpokenRef.current = false;
      silenceStartRef.current = null;
      await recorder.startRecording(audioDevices.selectedDeviceId);
    } else {
      // Single/Continuous: 3-2-1 countdown then record
      abortCountdownRef.current = false;
      setCountdown(3);
      playBeep(660);
      await new Promise((r) => setTimeout(r, 1000));
      if (abortCountdownRef.current) { setCountdown(null); return; }
      setCountdown(2);
      playBeep(660);
      await new Promise((r) => setTimeout(r, 1000));
      if (abortCountdownRef.current) { setCountdown(null); return; }
      setCountdown(1);
      playBeep(660);
      await new Promise((r) => setTimeout(r, 1000));
      if (abortCountdownRef.current) { setCountdown(null); return; }
      setCountdown(null);

      playBeep(1320);
      await recorder.startRecording(audioDevices.selectedDeviceId);
    }
  }, [rehearseMode, activeSceneId, audioDevices.selectedDeviceId, recorder, playingReference, mode, playBeep]);
  handleStartRecordingRef.current = handleStartRecording;

  const handleStopRecording = useCallback(async () => {
    // Cancel silence detection
    cancelAnimationFrame(silenceRafRef.current);
    silenceStartRef.current = null;
    hasSpokenRef.current = false;

    const blob = await recorder.stopRecording();
    if (!blob || !activeSceneId) return;

    const currentTakes = takes.filter((t) => t.sceneId === activeSceneId);
    const nextTakeNumber = currentTakes.length > 0 ? Math.max(...currentTakes.map((t) => t.takeNumber)) + 1 : 1;

    try {
      const data = await uploadRecordingTake(scriptId, activeSceneId, nextTakeNumber, blob);
      const newTake: Take = {
        filename: data.filename,
        takeNumber: nextTakeNumber,
        durationSeconds: data.duration_seconds,
        sceneId: activeSceneId,
      };
      setTakes((prev) => [...prev, newTake]);

      // Auto-select if first take
      if (currentTakes.length === 0) {
        const updated = { ...session, selected_takes: { ...session.selected_takes, [activeSceneId]: nextTakeNumber } };
        saveSession(updated);
      }

      // Auto-align the new take for instant feedback
      alignTake(activeSceneId, nextTakeNumber);

      // Continuous mode: auto-advance to next unrecorded scene
      if (mode === "continuous") {
        const nextSceneId = findNextUnrecordedScene(activeSceneId);
        if (nextSceneId) {
          setAutoAdvancing(true);
          autoAdvanceTimerRef.current = window.setTimeout(() => {
            setActiveSceneId(nextSceneId);
            setAutoAdvancing(false);
            pendingAutoAdvanceRef.current = nextSceneId;
          }, 1500);
        } else {
          showToast("All scenes recorded!");
        }
      }
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Take upload failed");
    }
  }, [recorder, activeSceneId, takes, scriptId, session, saveSession, alignTake, mode, findNextUnrecordedScene]);

  const handleSelectTake = useCallback((takeNumber: number) => {
    if (!activeSceneId) return;
    const updated = { ...session, selected_takes: { ...session.selected_takes, [activeSceneId]: takeNumber } };
    saveSession(updated);
    // Re-align on take swap for instant teleprompter update
    alignTake(activeSceneId, takeNumber);
  }, [activeSceneId, session, saveSession, alignTake]);

  const handleDeleteTake = useCallback(async (takeNumber: number) => {
    if (!activeSceneId) return;
    if (playingTakeNumber === takeNumber) {
      audioRef.current?.pause();
      setPlayingTakeNumber(null);
    }
    if (pausedTakeRef.current?.takeNumber === takeNumber) {
      pausedTakeRef.current = null;
    }
    await api.delete(`/api/recording/take/${scriptId}/${activeSceneId}/${takeNumber}`);
    setTakes((prev) => prev.filter((t) => !(t.sceneId === activeSceneId && t.takeNumber === takeNumber)));
    if (session.selected_takes[activeSceneId] === takeNumber) {
      const { [activeSceneId]: _, ...rest } = session.selected_takes;
      saveSession({ ...session, selected_takes: rest });
      setPreviewTimestamps(null);
    }
  }, [activeSceneId, scriptId, session, saveSession, playingTakeNumber]);

  const handlePlayTake = useCallback((take: Take) => {
    if (playingTakeNumber === take.takeNumber) {
      audioRef.current?.pause();
      setPlayingTakeNumber(null);
      pausedTakeRef.current = { takeNumber: take.takeNumber, filename: take.filename };
      return;
    }
    if (pausedTakeRef.current?.takeNumber === take.takeNumber && pausedTakeRef.current.filename === take.filename && audioRef.current && !audioRef.current.ended) {
      audioRef.current.play();
      setPlayingTakeNumber(take.takeNumber);
      pausedTakeRef.current = null;
      return;
    }
    pausedTakeRef.current = null;
    const url = assetUrl(`/static/projects/${scriptId}/recording/takes/${take.filename}`);
    if (audioRef.current) {
      audioRef.current.src = url;
      audioRef.current.play();
      setPlayingTakeNumber(take.takeNumber);
      audioRef.current.onended = () => setPlayingTakeNumber(null);
    }
  }, [playingTakeNumber, scriptId]);

  // Phase 4C: AI reference playback
  const handlePlayReference = useCallback(() => {
    if (!activeScene?.audio_url) return;

    if (playingReference) {
      referenceAudioRef.current?.pause();
      setPlayingReference(false);
      setReferenceElapsedMs(0);
      if (referenceTimerRef.current) cancelAnimationFrame(referenceTimerRef.current);
      return;
    }

    const url = assetUrl(activeScene.audio_url);
    if (!referenceAudioRef.current) return;

    referenceAudioRef.current.src = url;
    referenceAudioRef.current.play();
    setPlayingReference(true);

    const startTime = performance.now();
    const tick = () => {
      setReferenceElapsedMs(performance.now() - startTime);
      referenceTimerRef.current = requestAnimationFrame(tick);
    };
    referenceTimerRef.current = requestAnimationFrame(tick);

    referenceAudioRef.current.onended = () => {
      setPlayingReference(false);
      setReferenceElapsedMs(0);
      if (referenceTimerRef.current) cancelAnimationFrame(referenceTimerRef.current);
    };
  }, [activeScene?.audio_url, playingReference]);

  const handleImport = useCallback(async (file: File) => {
    if (!activeSceneId) return;
    try {
      const data = await importRecordingTake(scriptId, activeSceneId, file);
      const newTake: Take = {
        filename: data.filename,
        takeNumber: data.take_number,
        durationSeconds: data.duration_seconds,
        sceneId: activeSceneId,
      };
      setTakes((prev) => [...prev, newTake]);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Import failed");
    }
  }, [activeSceneId, scriptId]);

  const handleTrimChange = useCallback((seconds: number | null) => {
    if (!activeSceneId) return;
    const updated = { ...session, trim_points: { ...session.trim_points, [activeSceneId]: seconds ?? 0 } };
    saveSession(updated);
  }, [activeSceneId, session, saveSession]);

  const handleToggleFlag = useCallback(() => {
    if (!activeSceneId) return;
    const flags = new Set(Array.isArray(session.flagged_scenes) ? session.flagged_scenes : Object.keys(session.flagged_scenes));
    if (flags.has(activeSceneId)) flags.delete(activeSceneId);
    else flags.add(activeSceneId);
    saveSession({ ...session, flagged_scenes: [...flags] });
  }, [activeSceneId, session, saveSession]);

  // Clear preview timestamps and stop reference when changing scenes
  useEffect(() => {
    setPreviewTimestamps(null);
    // Cancel any pending auto-advance
    if (autoAdvanceTimerRef.current) {
      clearTimeout(autoAdvanceTimerRef.current);
      autoAdvanceTimerRef.current = null;
      setAutoAdvancing(false);
    }
    // Trigger recording if this scene change was from continuous auto-advance
    if (pendingAutoAdvanceRef.current && activeSceneId === pendingAutoAdvanceRef.current) {
      pendingAutoAdvanceRef.current = null;
      setTimeout(() => handleStartRecordingRef.current(), 300);
    }
    if (playingReference) {
      referenceAudioRef.current?.pause();
      setPlayingReference(false);
      setReferenceElapsedMs(0);
      if (referenceTimerRef.current) cancelAnimationFrame(referenceTimerRef.current);
    }
    pausedTakeRef.current = null;
  }, [activeSceneId]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      if (e.code === "Space") {
        e.preventDefault();
        if (countdown !== null) {
          abortCountdownRef.current = true;
          setCountdown(null);
        } else if (recorder.isRecording) handleStopRecording();
        else handleStartRecording();
      } else if (e.key === "f" || e.key === "F") {
        handleToggleFlag();
      } else if (e.key === "t" || e.key === "T") {
        setShowTrim((prev) => !prev);
      } else if (e.key === "Escape") {
        if (autoAdvancing && autoAdvanceTimerRef.current) {
          clearTimeout(autoAdvanceTimerRef.current);
          autoAdvanceTimerRef.current = null;
          setAutoAdvancing(false);
          setMode("single");
          showToast("Auto-advance stopped");
        } else if (countdown !== null) {
          abortCountdownRef.current = true;
          setCountdown(null);
          if (mode === "continuous") {
            setMode("single");
            showToast("Auto-advance stopped");
          }
        } else if (recorder.isRecording) {
          handleStopRecording();
        } else if (showExport) {
          setShowExport(false);
        }
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [recorder.isRecording, handleStartRecording, handleStopRecording, handleToggleFlag, showExport, autoAdvancing, countdown, mode]);

  // Free mode: auto-stop on silence after speech detected
  useEffect(() => {
    if (mode !== "free" || !recorder.isRecording) return;

    const SILENCE_THRESHOLD = 0.05;
    const SILENCE_DURATION_MS = 3000;

    const checkSilence = () => {
      const level = recorder.audioLevelRef.current;

      if (level > SILENCE_THRESHOLD) {
        hasSpokenRef.current = true;
        silenceStartRef.current = null;
      } else if (hasSpokenRef.current) {
        if (silenceStartRef.current === null) {
          silenceStartRef.current = Date.now();
        } else if (Date.now() - silenceStartRef.current >= SILENCE_DURATION_MS) {
          handleStopRecording();
          return;
        }
      }

      silenceRafRef.current = requestAnimationFrame(checkSilence);
    };

    silenceRafRef.current = requestAnimationFrame(checkSilence);
    return () => cancelAnimationFrame(silenceRafRef.current);
  }, [mode, recorder.isRecording, handleStopRecording]);

  if (loading || !content) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <span className="text-neutral-500">Loading...</span>
      </div>
    );
  }

  const flaggedScenes = new Set(Array.isArray(session.flagged_scenes) ? session.flagged_scenes : Object.keys(session.flagged_scenes));
  const activeDeviation = activeSceneId && session.selected_takes[activeSceneId]
    ? deviationData[`${activeSceneId}:${session.selected_takes[activeSceneId]}`]
    : undefined;

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      {/* Top bar */}
      <div className="shrink-0 border-b border-neutral-800 px-4 py-2.5 flex items-center bg-neutral-950/50">
        <button
          onClick={onClose}
          className="text-sm px-4 py-1.5 bg-neutral-800 border border-neutral-700 text-neutral-200 hover:bg-neutral-700 rounded-lg font-medium transition-colors mr-64"
        >
          Back to Project
        </button>
        <div className="flex items-center gap-4">
          <div className="text-xs text-neutral-400 tabular-nums">
            {recordedScenes.size}/{content.segments.reduce((acc, s) => acc + s.scenes.filter((sc) => sc.narration).length, 0)} recorded
          </div>
          {/* Mic selector */}
          <select
            value={audioDevices.selectedDeviceId}
            onChange={(e) => audioDevices.setSelectedDeviceId(e.target.value)}
            className="text-[11px] bg-neutral-800 border border-neutral-700 rounded-md px-2 py-1 text-neutral-300 max-w-[180px]"
          >
            {audioDevices.devices.map((d) => (
              <option key={d.deviceId} value={d.deviceId}>{d.label}</option>
            ))}
          </select>
          {/* Level meter */}
          <div className="w-16 h-2 bg-neutral-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-emerald-400 transition-all duration-75"
              style={{ width: `${Math.min(100, audioDevices.audioLevel * 100)}%` }}
            />
          </div>
          {/* Mode selector */}
          <div className="flex items-center gap-1">
            {([
              { key: "single" as const, tip: "Record one scene at a time with manual navigation" },
              { key: "continuous" as const, tip: "Auto-advance and record the next scene after each take" },
              { key: "free" as const, tip: "Record without teleprompter tracking. Auto-stops on silence" },
            ]).map(({ key, tip }) => (
              <button
                key={key}
                onClick={() => setMode(key)}
                title={tip}
                className={`text-[11px] px-2 py-1 rounded-md transition-colors capitalize ${
                  mode === key ? "bg-neutral-700 text-neutral-200" : "text-neutral-500 hover:text-neutral-300"
                }`}
              >
                {key}
              </button>
            ))}
          </div>
          {/* Rehearse toggle */}
          <button
            onClick={() => setRehearseMode(!rehearseMode)}
            title="Practice without recording. Teleprompter tracks normally"
            className={`text-[11px] px-2 py-1 rounded-md transition-colors ${
              rehearseMode ? "bg-sky-500/15 text-sky-300" : "text-neutral-500 hover:text-neutral-300"
            }`}
          >
            Rehearse
          </button>
        </div>
        <div className="flex-1" />
        <div className="flex items-center gap-3">
          {/* AI Reference playback button */}
          {activeScene?.audio_url && (
            <button
              onClick={handlePlayReference}
              className={`text-[11px] px-2.5 py-1 rounded-md transition-colors ${
                playingReference ? "bg-violet-500/15 text-violet-300" : "text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800"
              }`}
              title="Play AI reference audio with synchronized teleprompter"
            >
              {playingReference ? "Stop Ref" : "Reference"}
            </button>
          )}
          {/* Timing offset */}
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] text-neutral-500">Offset</span>
            <input
              type="range"
              min={-500}
              max={500}
              step={50}
              value={timingOffsetMs}
              onChange={(e) => setTimingOffsetMs(parseInt(e.target.value))}
              className="w-16 h-1 accent-violet-500"
            />
            <span className="text-[11px] text-neutral-500 tabular-nums w-8">{timingOffsetMs > 0 ? "+" : ""}{timingOffsetMs}ms</span>
          </div>
          {/* Score All button */}
          <button
            onClick={handleScoreAll}
            disabled={recordedScenes.size === 0 || scoring}
            className="text-xs px-3 py-1.5 text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800 rounded-lg transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {scoring ? "Scoring..." : "Score All"}
          </button>
          {/* Export button */}
          <button
            onClick={() => setShowExport(true)}
            disabled={recordedScenes.size === 0}
            className="text-xs px-3 py-1.5 bg-violet-500/10 border border-violet-500/25 text-violet-300 hover:bg-violet-500/20 rounded-lg font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Export
          </button>
        </div>
      </div>

      {/* 3-panel layout */}
      <div className="flex-1 flex overflow-hidden">
        <SceneNavigator
          content={content}
          activeSceneId={activeSceneId}
          onSelectScene={setActiveSceneId}
          recordedScenes={recordedScenes}
          flaggedScenes={flaggedScenes}
          filter={filter}
          onFilterChange={setFilter}
          scores={scores}
        />
        <TeleprompterPanel
          scene={activeScene}
          isRecording={playingReference ? true : recorder.isRecording}
          elapsedMs={playingReference ? referenceElapsedMs : recorder.elapsedMs}
          audioLevel={playingReference ? 0 : recorder.audioLevel}
          countdown={countdown}
          timingOffsetMs={timingOffsetMs}
          previewTimestamps={previewTimestamps}
          annotations={annotations[activeSceneId ?? ""]}
          freeMode={mode === "free"}
          rehearseMode={rehearseMode}
          isPlayingReference={playingReference}
        />
        <TakePanel
          scriptId={scriptId}
          sceneId={activeSceneId}
          takes={takes}
          selectedTakeNumber={activeSceneId ? session.selected_takes[activeSceneId] ?? null : null}
          onSelectTake={handleSelectTake}
          onDeleteTake={handleDeleteTake}
          onPlayTake={handlePlayTake}
          onRecordNew={handleStartRecording}
          onImport={handleImport}
          playingTakeNumber={playingTakeNumber}
          trimEndSeconds={activeSceneId ? (session.trim_points[activeSceneId] ?? null) : null}
          onTrimChange={handleTrimChange}
          showTrim={showTrim}
          onToggleTrim={() => setShowTrim(!showTrim)}
          deviation={activeDeviation}
        />
      </div>

      {/* Record/Stop button floating */}
      <div className="shrink-0 border-t border-neutral-800 px-4 py-3 flex items-center justify-center gap-4 bg-neutral-950/50">
        {autoAdvancing && (
          <div className="flex items-center gap-2 text-sm text-violet-300 animate-pulse">
            <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Next scene... (Esc to stop)
          </div>
        )}
        {!autoAdvancing && (
          <button
            onClick={recorder.isRecording ? handleStopRecording : handleStartRecording}
            disabled={!activeSceneId || !audioDevices.selectedDeviceId || countdown !== null}
            className={`px-6 py-2.5 rounded-xl font-medium text-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed ${
              recorder.isRecording
                ? "bg-red-500 text-white hover:bg-red-600 shadow-lg shadow-red-500/20"
                : "bg-neutral-800 border border-neutral-700 text-neutral-200 hover:bg-neutral-700"
            }`}
          >
            {recorder.isRecording
              ? "Stop Recording (Space)"
              : rehearseMode
                ? "Start Rehearsal (Space)"
                : "Start Recording (Space)"}
          </button>
        )}
        {/* Punch-in button */}
        {activeSceneId && previewTimestamps && previewTimestamps.length > 0 && session.selected_takes[activeSceneId] && (
          <button
            onClick={() => setShowPunchIn(true)}
            className="text-xs px-3 py-1.5 text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800 rounded-lg transition-colors"
          >
            Punch-In
          </button>
        )}
        {activeSceneId && flaggedScenes.has(activeSceneId) && (
          <span className="text-xs text-amber-400 flex items-center gap-1">
            <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24"><path d="M14.4 6L14 4H5v17h2v-7h5.6l.4 2h7V6h-5.6z" /></svg>
            Flagged
          </span>
        )}
      </div>

      {/* Punch-in modal */}
      {showPunchIn && activeSceneId && activeScene && previewTimestamps && session.selected_takes[activeSceneId] && (
        <PunchInMode
          scriptId={scriptId}
          sceneId={activeSceneId}
          baseTakeNumber={session.selected_takes[activeSceneId]}
          baseTakeFilename={takes.find((t) => t.sceneId === activeSceneId && t.takeNumber === session.selected_takes[activeSceneId])?.filename || `${activeSceneId}_take${session.selected_takes[activeSceneId]}.mp3`}
          wordTimestamps={previewTimestamps}
          narration={activeScene.narration || ""}
          onPunchComplete={(newTake) => {
            setShowPunchIn(false);
            const take: Take = {
              filename: newTake.filename,
              takeNumber: newTake.take_number,
              durationSeconds: newTake.duration_seconds,
              sceneId: activeSceneId,
            };
            setTakes((prev) => [...prev, take]);
            setPreviewTimestamps(newTake.word_timestamps);
            showToast(`Punch-in saved as Take ${newTake.take_number}`);
          }}
          onCancel={() => setShowPunchIn(false)}
        />
      )}

      {/* Export modal */}
      {showExport && (
        <ExportSection
          scriptId={scriptId}
          recordedCount={recordedScenes.size}
          onClose={() => setShowExport(false)}
          onExported={onClose}
        />
      )}

      {/* Hidden audio elements for playback */}
      <audio ref={audioRef} className="hidden" />
      <audio ref={referenceAudioRef} className="hidden" />

      {/* Mic error */}
      {(audioDevices.error || recorder.error) && (
        <div className="fixed bottom-4 right-4 bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-2 text-sm text-red-300 z-50">
          {audioDevices.error || recorder.error}
        </div>
      )}
    </div>
  );
}
