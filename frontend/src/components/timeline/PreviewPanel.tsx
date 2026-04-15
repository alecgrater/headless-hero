/**
 * PreviewPanel — bottom panel with Remotion Player (left) and waveform placeholder (right).
 * Replaces the old PropertiesPanel at the bottom of the timeline page.
 */
import { useMemo, useState, useCallback, useRef, useEffect } from "react";
import { Player, type PlayerRef } from "@remotion/player";
import { SingleScenePreview } from "@remotion-src/SingleScenePreview";
import { sceneToRemotionInput } from "../../utils/sceneToRemotionInput";
import type { Scene } from "../../types/script";
import SceneMicroTimeline from "./SceneMicroTimeline";
import { Settings } from "lucide-react";

const FPS = 30;
const VIDEO_WIDTH = 1920;
const VIDEO_HEIGHT = 1080;

interface Props {
  scene: Scene;
  segmentName: string;
  scriptId: string;
  onToggleProperties: () => void;
  onSplitScene: (splitTimeMs: number) => void;
  onUpdateScene: (sceneId: string, updates: Partial<Scene>) => void;
}

export default function PreviewPanel({
  scene,
  segmentName,
  onToggleProperties,
  onSplitScene,
  onUpdateScene,
}: Props) {
  const playerRef = useRef<PlayerRef>(null);
  const [currentTime, setCurrentTime] = useState(0);

  const sceneInput = useMemo(() => sceneToRemotionInput(scene), [scene]);
  const durationInFrames = Math.max(1, Math.round(sceneInput.duration_seconds * FPS));

  // Track playback time
  useEffect(() => {
    const player = playerRef.current;
    if (!player) return;

    const handler = () => {
      const frame = player.getCurrentFrame();
      setCurrentTime(frame / FPS);
    };

    player.addEventListener("frameupdate", handler);
    return () => player.removeEventListener("frameupdate", handler);
  }, []);

  const formatTime = useCallback((seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${String(s).padStart(2, "0")}`;
  }, []);

  const totalDuration = sceneInput.duration_seconds;

  return (
    <div className="flex flex-col min-h-0 flex-1 border-t border-neutral-800/60">
      {/* Header */}
      <div className="flex items-center px-4 py-1.5 border-b border-neutral-800/40 bg-neutral-900/60 shrink-0">
        <span className="text-xs text-neutral-500">
          {segmentName} &middot; <span className="font-mono">{scene.id}</span>
        </span>
        <div className="flex-1" />
        <button
          onClick={onToggleProperties}
          className="flex items-center gap-1.5 text-xs text-neutral-400 hover:text-neutral-200 px-2 py-1 rounded-md hover:bg-neutral-800 transition-colors"
          title="Toggle properties (P)"
        >
          <Settings size={13} />
          Properties
        </button>
        <span className="ml-3 text-xs text-neutral-500 font-mono tabular-nums">
          {formatTime(currentTime)} / {formatTime(totalDuration)}
        </span>
      </div>

      {/* Content: Player + Waveform */}
      <div className="flex-1 min-h-0 flex gap-4 px-4 py-2">
        {/* Left: Remotion Player */}
        <div className="flex-[2] min-w-0 min-h-0 flex items-center justify-center">
          <div className="w-full" style={{ aspectRatio: "16/9", maxHeight: "100%" }}>
            <Player
              ref={playerRef}
              component={SingleScenePreview}
              inputProps={{ scene: sceneInput, fps: FPS }}
              durationInFrames={durationInFrames}
              compositionWidth={VIDEO_WIDTH}
              compositionHeight={VIDEO_HEIGHT}
              fps={FPS}
              controls
              style={{ width: "100%", height: "100%" }}
            />
          </div>
        </div>

        {/* Right: Micro-timeline */}
        <div className="flex-1 min-w-0 min-h-0 flex flex-col">
          <SceneMicroTimeline
            scene={scene}
            playerRef={playerRef}
            playheadSeconds={currentTime}
            onUpdateScene={(updates) => onUpdateScene(scene.id, updates)}
            onSplitScene={onSplitScene}
          />
        </div>
      </div>
    </div>
  );
}
