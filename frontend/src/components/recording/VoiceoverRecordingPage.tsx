import { useCallback, useEffect, useRef, useState } from "react";
import api, { assetUrl, uploadRecordingTake, importRecordingTake } from "../../api";
import { showToast } from "../ToastContainer";
import type { ScriptContent, ScriptRead, Scene } from "../../types/script";
import SceneNavigator from "./SceneNavigator";
import TeleprompterPanel from "./TeleprompterPanel";
import TakePanel, { type Take } from "./TakePanel";
import ExportSection from "./ExportSection";
import { useRecorder } from "./useRecorder";
import { useAudioDevices } from "./useAudioDevices";

interface Props {
  scriptId: string;
  onClose: () => void;
}

interface SessionData {
  selected_takes: Record<string, number>;
  flagged_scenes: string[];
  trim_points: Record<string, number>;
  settings: Record<string, unknown>;
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
  const [filter, setFilter] = useState<"all" | "unrecorded" | "flagged">("all");
  const [playingTakeNumber, setPlayingTakeNumber] = useState<number | null>(null);
  const [showTrim, setShowTrim] = useState(false);
  const [showExport, setShowExport] = useState(false);
  const [mode, setMode] = useState<RecordingMode>("single");
  const [rehearseMode, setRehearseMode] = useState(false);

  const audioRef = useRef<HTMLAudioElement | null>(null);
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

  // Load existing takes from session
  useEffect(() => {
    if (!content) return;
    const loadTakes = async () => {
      const allTakes: Take[] = [];
      for (const seg of content.segments) {
        for (const scene of seg.scenes) {
          if (!scene.narration) continue;
          const selectedTake = session.selected_takes[scene.id];
          if (selectedTake) {
            allTakes.push({
              filename: `${scene.id}_take${selectedTake}.webm`,
              takeNumber: selectedTake,
              durationSeconds: 0,
              sceneId: scene.id,
            });
          }
        }
      }
      setTakes(allTakes);
    };
    loadTakes();
  }, [content, session.selected_takes]);

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

  const recordedScenes = new Set(Object.keys(session.selected_takes));

  const handleStartRecording = useCallback(async () => {
    if (rehearseMode || !activeSceneId || !audioDevices.selectedDeviceId) return;

    setCountdown(3);
    await new Promise((r) => setTimeout(r, 1000));
    setCountdown(2);
    await new Promise((r) => setTimeout(r, 1000));
    setCountdown(1);
    await new Promise((r) => setTimeout(r, 1000));
    setCountdown(null);

    await recorder.startRecording(audioDevices.selectedDeviceId);
  }, [rehearseMode, activeSceneId, audioDevices.selectedDeviceId, recorder]);

  const handleStopRecording = useCallback(async () => {
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
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Take upload failed");
    }
  }, [recorder, activeSceneId, takes, scriptId, session, saveSession]);

  const handleSelectTake = useCallback((takeNumber: number) => {
    if (!activeSceneId) return;
    const updated = { ...session, selected_takes: { ...session.selected_takes, [activeSceneId]: takeNumber } };
    saveSession(updated);
  }, [activeSceneId, session, saveSession]);

  const handleDeleteTake = useCallback(async (takeNumber: number) => {
    if (!activeSceneId) return;
    await api.delete(`/api/recording/take/${scriptId}/${activeSceneId}/${takeNumber}`);
    setTakes((prev) => prev.filter((t) => !(t.sceneId === activeSceneId && t.takeNumber === takeNumber)));
    if (session.selected_takes[activeSceneId] === takeNumber) {
      const { [activeSceneId]: _, ...rest } = session.selected_takes;
      saveSession({ ...session, selected_takes: rest });
    }
  }, [activeSceneId, scriptId, session, saveSession]);

  const handlePlayTake = useCallback((take: Take) => {
    if (playingTakeNumber === take.takeNumber) {
      audioRef.current?.pause();
      setPlayingTakeNumber(null);
      return;
    }
    const url = assetUrl(`/static/projects/${scriptId}/recording/takes/${take.filename}`);
    if (audioRef.current) {
      audioRef.current.src = url;
      audioRef.current.play();
      setPlayingTakeNumber(take.takeNumber);
      audioRef.current.onended = () => setPlayingTakeNumber(null);
    }
  }, [playingTakeNumber, scriptId]);

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
    const flags = new Set(session.flagged_scenes);
    if (flags.has(activeSceneId)) flags.delete(activeSceneId);
    else flags.add(activeSceneId);
    saveSession({ ...session, flagged_scenes: [...flags] });
  }, [activeSceneId, session, saveSession]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      if (e.code === "Space") {
        e.preventDefault();
        if (recorder.isRecording) handleStopRecording();
        else handleStartRecording();
      } else if (e.key === "f" || e.key === "F") {
        handleToggleFlag();
      } else if (e.key === "t" || e.key === "T") {
        setShowTrim((prev) => !prev);
      } else if (e.key === "Escape") {
        if (recorder.isRecording) handleStopRecording();
        else if (showExport) setShowExport(false);
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [recorder.isRecording, handleStartRecording, handleStopRecording, handleToggleFlag, showExport]);

  if (loading || !content) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <span className="text-neutral-500">Loading...</span>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      {/* Top bar */}
      <div className="shrink-0 border-b border-neutral-800 px-4 py-2.5 flex items-center justify-between bg-neutral-950/50">
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
            {(["single", "continuous", "free"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`text-[11px] px-2 py-1 rounded-md transition-colors capitalize ${
                  mode === m ? "bg-neutral-700 text-neutral-200" : "text-neutral-500 hover:text-neutral-300"
                }`}
              >
                {m}
              </button>
            ))}
          </div>
          {/* Rehearse toggle */}
          <button
            onClick={() => setRehearseMode(!rehearseMode)}
            className={`text-[11px] px-2 py-1 rounded-md transition-colors ${
              rehearseMode ? "bg-sky-500/15 text-sky-300" : "text-neutral-500 hover:text-neutral-300"
            }`}
          >
            Rehearse
          </button>
        </div>
        <div className="flex items-center gap-3">
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
          {/* Export button */}
          <button
            onClick={() => setShowExport(true)}
            disabled={recordedScenes.size === 0}
            className="text-xs px-3 py-1.5 bg-violet-500/10 border border-violet-500/25 text-violet-300 hover:bg-violet-500/20 rounded-lg font-medium transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Export
          </button>
          <button
            onClick={onClose}
            className="text-xs px-3 py-1.5 text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800 rounded-lg transition-colors"
          >
            Close
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
          flaggedScenes={new Set(session.flagged_scenes)}
          filter={filter}
          onFilterChange={setFilter}
        />
        <TeleprompterPanel
          scene={activeScene}
          isRecording={recorder.isRecording}
          elapsedMs={recorder.elapsedMs}
          audioLevel={recorder.audioLevel}
          countdown={countdown}
          timingOffsetMs={timingOffsetMs}
        />
        <TakePanel
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
        />
      </div>

      {/* Record/Stop button floating */}
      <div className="shrink-0 border-t border-neutral-800 px-4 py-3 flex items-center justify-center gap-4 bg-neutral-950/50">
        <button
          onClick={recorder.isRecording ? handleStopRecording : handleStartRecording}
          disabled={!activeSceneId || !audioDevices.selectedDeviceId || countdown !== null}
          className={`px-6 py-2.5 rounded-xl font-medium text-sm transition-all disabled:opacity-40 disabled:cursor-not-allowed ${
            recorder.isRecording
              ? "bg-red-500 text-white hover:bg-red-600 shadow-lg shadow-red-500/20"
              : "bg-neutral-800 border border-neutral-700 text-neutral-200 hover:bg-neutral-700"
          }`}
        >
          {recorder.isRecording ? "Stop Recording (Space)" : rehearseMode ? "Start Rehearsal (Space)" : "Start Recording (Space)"}
        </button>
        {activeSceneId && session.flagged_scenes.includes(activeSceneId) && (
          <span className="text-xs text-amber-400 flex items-center gap-1">
            <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24"><path d="M14.4 6L14 4H5v17h2v-7h5.6l.4 2h7V6h-5.6z" /></svg>
            Flagged
          </span>
        )}
      </div>

      {/* Export modal */}
      {showExport && (
        <ExportSection
          scriptId={scriptId}
          recordedCount={recordedScenes.size}
          onClose={() => setShowExport(false)}
          onExported={onClose}
        />
      )}

      {/* Hidden audio element for playback */}
      <audio ref={audioRef} className="hidden" />

      {/* Mic error */}
      {(audioDevices.error || recorder.error) && (
        <div className="fixed bottom-4 right-4 bg-red-500/10 border border-red-500/30 rounded-lg px-4 py-2 text-sm text-red-300 z-50">
          {audioDevices.error || recorder.error}
        </div>
      )}
    </div>
  );
}
