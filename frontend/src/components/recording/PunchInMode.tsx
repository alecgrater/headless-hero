import { useCallback, useMemo, useState } from "react";
import { assetUrl } from "../../api";
import { BACKEND_PORT } from "../../constants";
import { showToast } from "../ToastContainer";

interface WordTimestamp {
  word: string;
  start_ms: number;
  end_ms: number;
}

interface Props {
  scriptId: string;
  sceneId: string;
  baseTakeNumber: number;
  baseTakeFilename: string;
  wordTimestamps: WordTimestamp[];
  narration: string;
  onPunchComplete: (newTake: { filename: string; take_number: number; duration_seconds: number; word_timestamps: WordTimestamp[] }) => void;
  onCancel: () => void;
}

type PunchState = "selecting" | "preroll" | "recording" | "processing";

export default function PunchInMode({
  scriptId, sceneId, baseTakeNumber, baseTakeFilename, wordTimestamps, narration, onPunchComplete, onCancel,
}: Props) {
  const [state, setState] = useState<PunchState>("selecting");
  const [punchInIdx, setPunchInIdx] = useState<number | null>(null);
  const [punchOutIdx, setPunchOutIdx] = useState<number | null>(null);
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);

  const words = useMemo(() => narration.split(/\s+/).filter(Boolean), [narration]);

  const punchInMs = punchInIdx !== null && wordTimestamps[punchInIdx] ? wordTimestamps[punchInIdx].start_ms : null;
  const punchOutMs = punchOutIdx !== null && wordTimestamps[punchOutIdx] ? wordTimestamps[punchOutIdx].end_ms : null;

  const handleWordClick = useCallback((idx: number) => {
    if (state !== "selecting") return;
    if (punchInIdx === null) {
      setPunchInIdx(idx);
    } else if (punchOutIdx === null) {
      if (idx <= punchInIdx) {
        setPunchInIdx(idx);
      } else {
        setPunchOutIdx(idx);
      }
    } else {
      setPunchInIdx(idx);
      setPunchOutIdx(null);
    }
  }, [state, punchInIdx, punchOutIdx]);

  const handleStartPunch = useCallback(async () => {
    if (punchInMs === null || punchOutMs === null) return;

    setState("preroll");

    // Play 2s of pre-roll audio from the base take
    const prerollStart = Math.max(0, punchInMs - 2000);
    const audioUrl = assetUrl(`/static/projects/${scriptId}/recording/takes/${baseTakeFilename}`);
    const audio = new Audio(audioUrl);
    audio.currentTime = prerollStart / 1000;

    await audio.play();
    await new Promise((resolve) => setTimeout(resolve, punchInMs - prerollStart));
    audio.pause();

    // Start recording
    setState("recording");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus" });
      const chunks: Blob[] = [];

      recorder.ondataavailable = (e) => { if (e.data.size > 0) chunks.push(e.data); };
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks, { type: "audio/webm" });
        setState("processing");

        // Send to punch-in API
        const formData = new FormData();
        formData.append("script_id", scriptId);
        formData.append("scene_id", sceneId);
        formData.append("base_take_number", String(baseTakeNumber));
        formData.append("punch_in_ms", String(punchInMs));
        formData.append("punch_out_ms", String(punchOutMs));
        formData.append("audio", blob, "punch.webm");

        try {
          const response = await fetch(`http://localhost:${BACKEND_PORT}/api/recording/punch-in`, {
            method: "POST",
            body: formData,
          });
          if (!response.ok) throw new Error("Punch-in failed");
          const result = await response.json();
          onPunchComplete(result);
        } catch (err) {
          showToast(err instanceof Error ? err.message : "Punch-in splice failed");
          setState("selecting");
        }
      };

      recorder.start();
      setMediaRecorder(recorder);
    } catch {
      showToast("Microphone access failed");
      setState("selecting");
    }
  }, [punchInMs, punchOutMs, scriptId, sceneId, baseTakeNumber, baseTakeFilename, onPunchComplete]);

  const handleStopPunch = useCallback(() => {
    if (mediaRecorder && mediaRecorder.state === "recording") {
      mediaRecorder.stop();
    }
  }, [mediaRecorder]);

  return (
    <div className="fixed inset-0 bg-black/70 backdrop-blur-sm z-50 flex items-center justify-center" onClick={onCancel}>
      <div className="bg-neutral-900 border border-neutral-700 rounded-xl shadow-2xl w-[600px] max-h-[80vh] overflow-hidden flex flex-col" onClick={(e) => e.stopPropagation()}>
        <div className="px-5 py-4 border-b border-neutral-800 flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-neutral-100">Punch-In Recording</h3>
            <p className="text-xs text-neutral-500 mt-0.5">
              {state === "selecting" && "Click start word, then end word to define punch zone"}
              {state === "preroll" && "Playing pre-roll..."}
              {state === "recording" && "Recording — speak the replacement"}
              {state === "processing" && "Splicing audio..."}
            </p>
          </div>
          <button onClick={onCancel} className="text-neutral-500 hover:text-neutral-300 text-xs">Cancel</button>
        </div>

        {/* Word selection area */}
        <div className="flex-1 overflow-y-auto p-5">
          <div className="flex flex-wrap gap-1">
            {words.map((word, i) => {
              const isInRange = punchInIdx !== null && punchOutIdx !== null && i >= punchInIdx && i <= punchOutIdx;
              const isStart = i === punchInIdx;
              const isEnd = i === punchOutIdx;
              return (
                <button
                  key={i}
                  onClick={() => handleWordClick(i)}
                  disabled={state !== "selecting"}
                  className={`px-1.5 py-0.5 rounded text-sm transition-colors ${
                    isInRange
                      ? "bg-red-500/20 text-red-300 border border-red-500/40"
                      : isStart || isEnd
                        ? "bg-violet-500/20 text-violet-300 border border-violet-500/40"
                        : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800"
                  } ${state !== "selecting" ? "cursor-default" : "cursor-pointer"}`}
                >
                  {word}
                </button>
              );
            })}
          </div>
        </div>

        {/* Action bar */}
        <div className="px-5 py-3 border-t border-neutral-800 flex items-center justify-between">
          <div className="text-xs text-neutral-500">
            {punchInIdx !== null && punchOutIdx !== null && punchInMs !== null && punchOutMs !== null && (
              <span>Punch zone: {(punchInMs / 1000).toFixed(1)}s — {(punchOutMs / 1000).toFixed(1)}s</span>
            )}
          </div>
          {state === "selecting" && (
            <button
              onClick={handleStartPunch}
              disabled={punchInIdx === null || punchOutIdx === null}
              className="px-4 py-2 bg-red-500 text-white rounded-lg text-xs font-medium hover:bg-red-600 transition-colors disabled:opacity-40"
            >
              Start Punch-In
            </button>
          )}
          {state === "recording" && (
            <button
              onClick={handleStopPunch}
              className="px-4 py-2 bg-red-500 text-white rounded-lg text-xs font-medium hover:bg-red-600 transition-colors animate-pulse"
            >
              Stop Recording
            </button>
          )}
          {state === "processing" && (
            <span className="text-xs text-neutral-400 flex items-center gap-2">
              <span className="w-3 h-3 border-2 border-neutral-400/40 border-t-neutral-300 rounded-full animate-spin" />
              Processing...
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
