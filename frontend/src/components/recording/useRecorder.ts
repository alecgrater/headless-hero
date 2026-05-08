import { useCallback, useRef, useState } from "react";

interface UseRecorderResult {
  isRecording: boolean;
  startRecording: (deviceId: string) => Promise<void>;
  stopRecording: () => Promise<Blob | null>;
  audioLevel: number;
  audioLevelRef: React.RefObject<number>;
  elapsedMs: number;
  error: string | null;
}

export function useRecorder(): UseRecorderResult {
  const [isRecording, setIsRecording] = useState(false);
  const [audioLevel, setAudioLevel] = useState(0);
  const audioLevelRef = useRef(0);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number>(0);
  const startTimeRef = useRef<number>(0);
  const timerRef = useRef<number>(0);

  const startRecording = useCallback(async (deviceId: string) => {
    setError(null);
    chunksRef.current = [];

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { deviceId: { exact: deviceId } },
      });
      streamRef.current = stream;

      const ctx = new AudioContext();
      ctxRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 256;
      source.connect(analyser);
      analyserRef.current = analyser;

      const dataArray = new Uint8Array(analyser.frequencyBinCount);
      const tickLevel = () => {
        if (!analyserRef.current) return;
        analyserRef.current.getByteFrequencyData(dataArray);
        const sum = dataArray.reduce((a, b) => a + b, 0);
        setAudioLevel(sum / dataArray.length / 255);
        audioLevelRef.current = sum / dataArray.length / 255;
        animFrameRef.current = requestAnimationFrame(tickLevel);
      };
      tickLevel();

      const recorder = new MediaRecorder(stream, {
        mimeType: "audio/webm;codecs=opus",
      });
      recorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };
      mediaRecorderRef.current = recorder;
      recorder.start(100);

      startTimeRef.current = Date.now();
      timerRef.current = window.setInterval(() => {
        setElapsedMs(Date.now() - startTimeRef.current);
      }, 50);

      setIsRecording(true);
    } catch (err) {
      setError("Could not start recording — check microphone permissions");
    }
  }, []);

  const stopRecording = useCallback(async (): Promise<Blob | null> => {
    cancelAnimationFrame(animFrameRef.current);
    clearInterval(timerRef.current);

    const recorder = mediaRecorderRef.current;
    if (!recorder || recorder.state === "inactive") {
      setIsRecording(false);
      return null;
    }

    return new Promise((resolve) => {
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        chunksRef.current = [];
        setIsRecording(false);
        setAudioLevel(0);
        audioLevelRef.current = 0;

        if (streamRef.current) {
          streamRef.current.getTracks().forEach((t) => t.stop());
          streamRef.current = null;
        }
        if (ctxRef.current) {
          ctxRef.current.close();
          ctxRef.current = null;
        }
        analyserRef.current = null;
        resolve(blob);
      };
      recorder.stop();
    });
  }, []);

  return { isRecording, startRecording, stopRecording, audioLevel, audioLevelRef, elapsedMs, error };
}
