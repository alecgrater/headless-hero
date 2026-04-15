import { useCallback, useEffect, useRef, useState, useMemo } from "react";
import type { Scene, EliKeyframe } from "../../types/script";
import type { PlayerRef } from "@remotion/player";
import WaveformSplitter from "./WaveformSplitter";
import InOutLane from "./micro-timeline/InOutLane";
import ImageLane from "./micro-timeline/ImageLane";
import FxLane from "./micro-timeline/FxLane";
import EliLane from "./micro-timeline/EliLane";
import { FPS, FRAME_SECONDS, secondsToPx, snapToWordBoundary } from "./micro-timeline/shared";
import { assetUrl } from "../../api";

type LaneId = "images" | "fx" | "eli" | "inout";

interface Props {
  scene: Scene;
  playerRef: React.RefObject<PlayerRef | null>;
  playheadSeconds: number;
  onUpdateScene: (updates: Partial<Scene>) => void;
  onSplitScene: (splitTimeMs: number) => void;
}

export default function SceneMicroTimeline({
  scene,
  playerRef,
  playheadSeconds,
  onUpdateScene,
  onSplitScene,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(400);
  const [selectedLane, setSelectedLane] = useState<LaneId | null>(null);
  const [selectedImageMarker, setSelectedImageMarker] = useState<number | null>(null);
  const [selectedFxMarker, setSelectedFxMarker] = useState(false);
  const [selectedEliMarker, setSelectedEliMarker] = useState<number | null>(null);
  const [shiftHeld, setShiftHeld] = useState(false);

  const durationSeconds = scene.audio_duration_seconds || scene.duration_estimate_seconds || 5;

  // Track shift key state
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => { if (e.key === "Shift") setShiftHeld(true); };
    const onKeyUp = (e: KeyboardEvent) => { if (e.key === "Shift") setShiftHeld(false); };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, []);

  // Track container width via ResizeObserver
  useEffect(() => {
    if (!containerRef.current) return;
    const ro = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerWidth(entry.contentRect.width);
      }
    });
    ro.observe(containerRef.current);
    return () => ro.disconnect();
  }, []);

  // Determine which lanes are visible
  const hasMultiFrame = (scene.frame_urls?.length ?? 0) > 1;
  const hasZoomPunch = !!scene.fx?.zoom_punch;
  const hasEli = !!scene.eli_overlay?.enabled && (scene.eli_overlay?.keyframes?.length ?? 0) > 0;

  // Compute default frame_timings (even split) if not set
  const frameTimings = useMemo(() => {
    if (scene.frame_timings && scene.frame_timings.length === (scene.frame_urls?.length ?? 0)) {
      return scene.frame_timings;
    }
    const count = scene.frame_urls?.length ?? 0;
    if (count <= 1) return [0];
    const interval = durationSeconds / count;
    return Array.from({ length: count }, (_, i) => Math.round(i * interval * 1000) / 1000);
  }, [scene.frame_timings, scene.frame_urls?.length, durationSeconds]);

  // Lane change handlers
  const handleInOutChange = useCallback(
    (field: "visual_in_seconds" | "visual_out_seconds", value: number) => {
      onUpdateScene({ [field]: Math.round(value * 1000) / 1000 });
    },
    [onUpdateScene],
  );

  const handleFrameTimingsChange = useCallback(
    (timings: number[]) => {
      onUpdateScene({ frame_timings: timings });
    },
    [onUpdateScene],
  );

  const handleZoomPunchChange = useCallback(
    (triggerFrame: number) => {
      const currentFx = scene.fx ?? {};
      const currentZoom = currentFx.zoom_punch ?? { trigger_frame: 0, scale: 1.06 };
      onUpdateScene({
        fx: { ...currentFx, zoom_punch: { ...currentZoom, trigger_frame: triggerFrame } },
      });
    },
    [scene.fx, onUpdateScene],
  );

  const handleEliKeyframesChange = useCallback(
    (keyframes: EliKeyframe[]) => {
      const currentEli = scene.eli_overlay ?? { enabled: true, keyframes: [] };
      onUpdateScene({
        eli_overlay: { ...currentEli, keyframes },
      });
    },
    [scene.eli_overlay, onUpdateScene],
  );

  // Playhead line position
  const playheadPx = secondsToPx(playheadSeconds, durationSeconds, containerWidth);

  // Common lane props
  const laneBase = {
    durationSeconds,
    playheadSeconds,
    widthPx: containerWidth,
  };

  // No audio → gate
  if (!scene.audio_url) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <p className="text-xs text-neutral-600">
          Generate voiceover to enable timing controls
        </p>
      </div>
    );
  }

  return (
    <div ref={containerRef} className="flex flex-col gap-0.5 flex-1 min-h-0">
      {/* Waveform (existing — for audio visualization + split) */}
      <WaveformSplitter
        audioUrl={assetUrl(scene.audio_url)}
        wordTimestamps={scene.word_timestamps}
        onSplit={onSplitScene}
      />

      {/* Event lanes */}
      <div className="flex flex-col gap-px relative">
        {/* Playhead line spanning all lanes */}
        <div
          className="absolute top-0 bottom-0 w-px bg-white/40 z-30 pointer-events-none"
          style={{ left: playheadPx }}
        />

        {hasMultiFrame && (
          <ImageLane
            {...laneBase}
            isSelected={selectedLane === "images"}
            onSelect={() => setSelectedLane("images")}
            frameTimings={frameTimings}
            frameCount={scene.frame_urls?.length ?? 0}
            wordTimestamps={scene.word_timestamps}
            onChange={handleFrameTimingsChange}
            selectedMarker={selectedLane === "images" ? selectedImageMarker : null}
            onSelectMarker={setSelectedImageMarker}
            shiftHeld={shiftHeld}
          />
        )}

        {hasZoomPunch && (
          <FxLane
            {...laneBase}
            isSelected={selectedLane === "fx"}
            onSelect={() => setSelectedLane("fx")}
            triggerFrame={scene.fx!.zoom_punch!.trigger_frame}
            wordTimestamps={scene.word_timestamps}
            onChange={handleZoomPunchChange}
            isMarkerSelected={selectedLane === "fx" && selectedFxMarker}
            onSelectMarker={setSelectedFxMarker}
            shiftHeld={shiftHeld}
          />
        )}

        {hasEli && (
          <EliLane
            {...laneBase}
            isSelected={selectedLane === "eli"}
            onSelect={() => setSelectedLane("eli")}
            keyframes={scene.eli_overlay!.keyframes as EliKeyframe[]}
            wordTimestamps={scene.word_timestamps}
            onChange={handleEliKeyframesChange}
            selectedMarker={selectedLane === "eli" ? selectedEliMarker : null}
            onSelectMarker={setSelectedEliMarker}
            shiftHeld={shiftHeld}
          />
        )}

        <InOutLane
          {...laneBase}
          isSelected={selectedLane === "inout"}
          onSelect={() => setSelectedLane("inout")}
          visualInSeconds={scene.visual_in_seconds ?? 0}
          visualOutSeconds={scene.visual_out_seconds ?? 0}
          onChangeIn={(v) => handleInOutChange("visual_in_seconds", v)}
          onChangeOut={(v) => handleInOutChange("visual_out_seconds", v)}
        />
      </div>

      {/* Transport bar */}
      <div className="flex items-center gap-2 px-1 py-0.5 text-[10px] text-neutral-500 shrink-0">
        <span className="font-mono tabular-nums">
          {playheadSeconds.toFixed(2)}s · frame {Math.round(playheadSeconds * FPS)}
        </span>
        {selectedLane && (
          <span className="text-neutral-600">
            Lane: {selectedLane}
          </span>
        )}
      </div>
    </div>
  );
}
