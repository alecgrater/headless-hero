import { useCallback, useEffect, useRef, useState, useMemo, forwardRef, useImperativeHandle } from "react";
import type { Scene } from "../../types/script";
import WaveformSplitter from "./WaveformSplitter";
import InOutLane from "./micro-timeline/InOutLane";
import ImageLane from "./micro-timeline/ImageLane";
import FxLane from "./micro-timeline/FxLane";
import { FPS, secondsToPx, wordToSeconds, estimateWordPosition } from "./micro-timeline/shared";
import { assetUrl } from "../../api";

export type LaneId = "images" | "fx" | "inout";

export interface MicroTimelineHandle {
  selectedLane: LaneId | null;
  setSelectedLane: (lane: LaneId | null) => void;
  placeMarkerAtPlayhead: () => void;
  nudge: (frames: number) => void;
  deleteSelectedMarker: () => void;
  hasSelectedMarker: () => boolean;
}

interface Props {
  scene: Scene;
  playheadSeconds?: number;
  onUpdateScene: (updates: Partial<Scene>) => void;
  onSplitScene: (splitTimeMs: number) => void;
}

const SceneMicroTimeline = forwardRef<MicroTimelineHandle, Props>(function SceneMicroTimeline(
  { scene, playheadSeconds = 0, onUpdateScene, onSplitScene },
  ref,
) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(400);
  const [selectedLane, setSelectedLane] = useState<LaneId | null>(null);
  const [selectedImageMarker, setSelectedImageMarker] = useState<number | null>(null);
  const [selectedFxMarker, setSelectedFxMarker] = useState(false);
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

  // Track previous audio duration for stale marker detection
  const prevAudioDuration = useRef(scene.audio_duration_seconds ?? 0);
  const [isStale, setIsStale] = useState(false);

  useEffect(() => {
    if (
      prevAudioDuration.current > 0 &&
      (scene.audio_duration_seconds ?? 0) > 0 &&
      prevAudioDuration.current !== scene.audio_duration_seconds
    ) {
      // Audio was regenerated with a different duration
      const hasManualTimings =
        scene.frame_timings != null ||
        (scene.visual_in_seconds ?? 0) > 0 ||
        (scene.visual_out_seconds ?? 0) > 0;
      if (hasManualTimings) {
        setIsStale(true);
      }
    }
    prevAudioDuration.current = scene.audio_duration_seconds ?? 0;
  }, [scene.audio_duration_seconds, scene.frame_timings, scene.visual_in_seconds, scene.visual_out_seconds]);

  // Determine which lanes are visible
  const hasMultiFrame = (scene.frame_urls?.length ?? 0) > 1;
  const hasZoomPunch = !!scene.fx?.zoom_punch;

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
    (triggerWord: string, triggerFrame: number) => {
      const currentFx = scene.fx ?? {};
      const currentZoom = currentFx.zoom_punch ?? { trigger_frame: 0, scale: 1.06 };
      onUpdateScene({
        fx: {
          ...currentFx,
          zoom_punch: {
            ...currentZoom,
            trigger_word: triggerWord || undefined,
            trigger_frame: triggerFrame,
          },
        },
      });
    },
    [scene.fx, onUpdateScene],
  );

  // Imperative API for keyboard shortcuts
  useImperativeHandle(ref, () => ({
    selectedLane,
    setSelectedLane,
    placeMarkerAtPlayhead: () => {
    },
    nudge: (frames: number) => {
      const delta = frames / FPS;
      if (selectedLane === "images" && selectedImageMarker !== null) {
        const updated = [...frameTimings];
        const idx = selectedImageMarker;
        if (idx > 0) {
          const minSec = (frameTimings[idx - 1] ?? 0) + 0.1;
          const maxSec = (frameTimings[idx + 1] ?? durationSeconds) - 0.1;
          updated[idx] = Math.max(minSec, Math.min(maxSec, updated[idx] + delta));
          updated[idx] = Math.round(updated[idx] * 1000) / 1000;
          onUpdateScene({ frame_timings: updated });
        }
      } else if (selectedLane === "fx" && selectedFxMarker) {
        const wts = scene.word_timestamps;
        const currentWord = scene.fx?.zoom_punch?.trigger_word;
        if (wts && wts.length > 0) {
          const currentSec = currentWord
            ? (wordToSeconds(currentWord, wts) ?? estimateWordPosition(currentWord, scene.narration, durationSeconds))
            : (scene.fx?.zoom_punch?.trigger_frame ?? 0) / FPS;
          let nearestIdx = 0;
          let nearestDist = Infinity;
          for (let i = 0; i < wts.length; i++) {
            const d = Math.abs(wts[i].start_ms / 1000 - currentSec);
            if (d < nearestDist) { nearestDist = d; nearestIdx = i; }
          }
          const newIdx = Math.max(0, Math.min(wts.length - 1, nearestIdx + (frames > 0 ? 1 : -1)));
          const newWord = wts[newIdx].word;
          const newFrame = Math.round(wts[newIdx].start_ms / 1000 * FPS);
          handleZoomPunchChange(newWord, newFrame);
        } else {
          const currentFrame = scene.fx?.zoom_punch?.trigger_frame ?? 0;
          const newFrame = Math.max(0, Math.min(Math.round(durationSeconds * FPS), currentFrame + frames));
          handleZoomPunchChange(currentWord ?? "", newFrame);
        }
      } else if (selectedLane === "inout") {
        const currentIn = scene.visual_in_seconds ?? 0;
        const newIn = Math.max(0, currentIn + delta);
        onUpdateScene({ visual_in_seconds: Math.round(newIn * 1000) / 1000 });
      }
    },
    deleteSelectedMarker: () => {
      if (selectedLane === "images" && selectedImageMarker !== null) {
        onUpdateScene({ frame_timings: null });
        setSelectedImageMarker(null);
      } else if (selectedLane === "fx" && selectedFxMarker) {
        handleZoomPunchChange("", 0);
        setSelectedFxMarker(false);
      } else if (selectedLane === "inout") {
        onUpdateScene({ visual_in_seconds: 0, visual_out_seconds: 0 });
      }
    },
    hasSelectedMarker: () => {
      if (selectedLane === "images" && selectedImageMarker !== null) return true;
      if (selectedLane === "fx" && selectedFxMarker) return true;
      return false;
    },
  }), [selectedLane, selectedImageMarker, selectedFxMarker, frameTimings, durationSeconds, scene, onUpdateScene, handleZoomPunchChange]);

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

      {/* Stale marker warning */}
      {isStale && (
        <div className="flex items-center gap-2 px-2 py-1 bg-amber-500/10 border border-amber-500/30 rounded text-[10px] text-amber-400">
          <span>Audio changed — timing markers may need adjustment.</span>
          <button
            onClick={() => setIsStale(false)}
            className="text-amber-500 hover:text-amber-300 underline"
          >
            Dismiss
          </button>
        </div>
      )}

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
            triggerWord={scene.fx!.zoom_punch!.trigger_word}
            narration={scene.narration}
            wordTimestamps={scene.word_timestamps}
            onChange={handleZoomPunchChange}
            isMarkerSelected={selectedLane === "fx" && selectedFxMarker}
            onSelectMarker={setSelectedFxMarker}
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
});

export default SceneMicroTimeline;
