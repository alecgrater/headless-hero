import { useCallback, useEffect, useRef, useState } from "react";

export interface AudioDevice {
  deviceId: string;
  label: string;
}

interface UseAudioDevicesResult {
  devices: AudioDevice[];
  selectedDeviceId: string;
  setSelectedDeviceId: (id: string) => void;
  audioLevel: number;
  error: string | null;
}

export function useAudioDevices(): UseAudioDevicesResult {
  const [devices, setDevices] = useState<AudioDevice[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState("");
  const [audioLevel, setAudioLevel] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const ctxRef = useRef<AudioContext | null>(null);
  const animFrameRef = useRef<number>(0);

  const enumerate = useCallback(async () => {
    try {
      await navigator.mediaDevices.getUserMedia({ audio: true }).then((s) => s.getTracks().forEach((t) => t.stop()));
      const all = await navigator.mediaDevices.enumerateDevices();
      const audioInputs = all
        .filter((d) => d.kind === "audioinput")
        .map((d) => ({ deviceId: d.deviceId, label: d.label || `Microphone ${d.deviceId.slice(0, 6)}` }));
      setDevices(audioInputs);
      if (audioInputs.length > 0 && !selectedDeviceId) {
        setSelectedDeviceId(audioInputs[0].deviceId);
      }
      setError(null);
    } catch (err) {
      setError("Microphone access denied");
    }
  }, [selectedDeviceId]);

  useEffect(() => {
    enumerate();
  }, [enumerate]);

  useEffect(() => {
    if (!selectedDeviceId) return;
    let cancelled = false;

    const startMonitor = async () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
      }
      if (ctxRef.current) {
        ctxRef.current.close();
        ctxRef.current = null;
      }
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: { deviceId: { exact: selectedDeviceId } },
        });
        if (cancelled) { stream.getTracks().forEach((t) => t.stop()); return; }
        streamRef.current = stream;
        const ctx = new AudioContext();
        ctxRef.current = ctx;
        const source = ctx.createMediaStreamSource(stream);
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 256;
        source.connect(analyser);
        analyserRef.current = analyser;

        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        const tick = () => {
          if (cancelled) return;
          analyser.getByteFrequencyData(dataArray);
          const sum = dataArray.reduce((a, b) => a + b, 0);
          const avg = sum / dataArray.length;
          setAudioLevel(avg / 255);
          animFrameRef.current = requestAnimationFrame(tick);
        };
        tick();
      } catch {
        setError("Could not access microphone");
      }
    };
    startMonitor();

    return () => {
      cancelled = true;
      cancelAnimationFrame(animFrameRef.current);
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
        streamRef.current = null;
      }
      if (ctxRef.current) {
        ctxRef.current.close();
        ctxRef.current = null;
      }
    };
  }, [selectedDeviceId]);

  return { devices, selectedDeviceId, setSelectedDeviceId, audioLevel, error };
}
