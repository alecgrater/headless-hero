import { useEffect, useRef } from "react";
import WaveSurfer from "wavesurfer.js";

interface Props {
  audioUrl: string;
  isPlaying: boolean;
  onSeek?: (progress: number) => void;
}

export default function TakeWaveform({ audioUrl, isPlaying, onSeek }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WaveSurfer | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const ws = WaveSurfer.create({
      container: containerRef.current,
      height: 32,
      waveColor: "#525252",
      progressColor: "#a78bfa",
      cursorColor: "#a78bfa",
      cursorWidth: 1,
      barWidth: 2,
      barGap: 1,
      barRadius: 1,
      normalize: true,
      interact: true,
      hideScrollbar: true,
      backend: "WebAudio",
    });

    ws.load(audioUrl);

    if (onSeek) {
      ws.on("click", (progress) => {
        onSeek(progress);
      });
    }

    wsRef.current = ws;

    return () => {
      ws.destroy();
      wsRef.current = null;
    };
  }, [audioUrl]);

  useEffect(() => {
    if (!wsRef.current) return;
    if (isPlaying) {
      wsRef.current.play();
    } else {
      wsRef.current.pause();
    }
  }, [isPlaying]);

  return (
    <div
      ref={containerRef}
      className="w-full h-8 rounded overflow-hidden bg-neutral-800/50 cursor-pointer"
    />
  );
}
