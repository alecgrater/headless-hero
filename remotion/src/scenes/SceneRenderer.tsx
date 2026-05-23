/**
 * SceneRenderer — dispatches to the appropriate scene component
 * based on scene type and flags.
 * Optionally wraps with ZoomPunch effect and subtitle overlay.
 */
import React from "react";
import { Audio, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import type { SceneInput, Orientation, VisualCanvas } from "../types";
import { StaticImageScene } from "./StaticImageScene";
import { MultiFrameScene } from "./MultiFrameScene";
import { TitleCardScene } from "./TitleCardScene";
import { SubtitleScene } from "./SubtitleScene";
import { VideoScene } from "./VideoScene";
import { VerticalSceneLayout } from "./VerticalSceneLayout";
import { StaticCanvas } from "./StaticCanvas";
import { TreatmentRenderer } from "./TreatmentRenderer";

import { ZoomPunch } from "../effects/camera/ZoomPunch";
import { CameraDrift } from "../effects/camera/CameraDrift";
import { SubtitleOverlay } from "../effects/typography/Subtitles";
import { EliOverlay } from "../effects/overlays/EliOverlay";
import { SceneTransition } from "../effects/transitions/SceneTransition";

interface Props {
  scene: SceneInput;
  highlightEnabled?: boolean;
  orientation?: Orientation;
  visualCanvas?: VisualCanvas | null;
}

export const SceneRenderer: React.FC<Props> = ({
  scene,
  highlightEnabled,
  orientation = "horizontal",
  visualCanvas,
}) => {
  const hasMultipleFrames = scene.frame_paths && scene.frame_paths.length > 1;
  const isTitleCard = scene.is_title_card && scene.title_card_zoom_target;
  const isAhaSubtitle = scene.visual_beat === "aha_subtitle";
  const isVideo = scene.media_type === "video" && (scene.video_path || scene.image_path);
  const fx = scene.fx;

  const currentFrame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Visual in/out: fade to/from black during offset periods
  const inFrames = Math.round((scene.visual_in_seconds ?? 0) * fps);
  const outStartFrame = Math.round(
    (scene.duration_seconds - (scene.visual_out_seconds ?? 0)) * fps
  );
  const totalSceneFrames = Math.round(scene.duration_seconds * fps);

  // 6-frame (0.2s) crossfade at boundaries
  const FADE_FRAMES = 6;
  let visualOpacity = 1;
  if (inFrames > 0 && currentFrame < inFrames) {
    visualOpacity = interpolate(
      currentFrame,
      [Math.max(0, inFrames - FADE_FRAMES), inFrames],
      [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
    );
  }
  if ((scene.visual_out_seconds ?? 0) > 0 && currentFrame >= outStartFrame) {
    visualOpacity = interpolate(
      currentFrame,
      [outStartFrame, Math.min(totalSceneFrames, outStartFrame + FADE_FRAMES)],
      [1, 0],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
    );
  }

  // Visual layer dispatch
  let visualLayer: React.ReactNode;
  if (isTitleCard) {
    visualLayer = <TitleCardScene scene={scene} />;
  } else if (isAhaSubtitle) {
    visualLayer = <SubtitleScene scene={scene} orientation={orientation} />;
  } else if (isVideo) {
    visualLayer = <VideoScene scene={scene} />;
  } else if (hasMultipleFrames) {
    const fallbackVisualLayer = <MultiFrameScene scene={scene} />;
    visualLayer = (
      <>
        <StaticCanvas canvas={visualCanvas} />
        <TreatmentRenderer scene={scene} fallbackVisualLayer={fallbackVisualLayer} />
      </>
    );
  } else {
    const fallbackVisualLayer = <StaticImageScene scene={scene} />;
    visualLayer = (
      <>
        <StaticCanvas canvas={visualCanvas} />
        <TreatmentRenderer scene={scene} fallbackVisualLayer={fallbackVisualLayer} />
      </>
    );
  }

  // Wrap with CameraDrift if assigned (not for subtitle or title card scenes)
  if (fx?.drift && !isAhaSubtitle && !isTitleCard) {
    visualLayer = (
      <CameraDrift
        motion={fx.drift.motion}
        intensity={fx.drift.intensity}
        anchor={fx.drift.anchor}
      >
        {visualLayer}
      </CameraDrift>
    );
  }

  // Wrap with ZoomPunch if assigned (but not for subtitle scenes — no image to zoom)
  if (fx?.zoom_punch && !isAhaSubtitle) {
    visualLayer = (
      <ZoomPunch
        triggerFrame={fx.zoom_punch.trigger_frame}
        scale={fx.zoom_punch.scale}
      >
        {visualLayer}
      </ZoomPunch>
    );
  }

  // In vertical mode, wrap narration scenes in three-band layout.
  // Aha-subtitle scenes occupy the full vertical frame natively.
  // Title cards in shorts are handled by ShortTitleCardScene, not here.
  const isVertical = orientation === "vertical";
  if (isVertical && !isAhaSubtitle && !isTitleCard) {
    visualLayer = (
      <VerticalSceneLayout imagePath={scene.image_path}>
        {visualLayer}
      </VerticalSceneLayout>
    );
  }

  return (
    <div style={{ width: "100%", height: "100%", position: "relative" }}>
      {/* Scene transition wraps visual + subtitle; audio and Eli stay outside */}
      <SceneTransition transitionIn={scene.transition_in} transitionOut={scene.transition_out}>
        {/* Visual + subtitle layer with in/out opacity */}
        <div style={{ width: "100%", height: "100%", opacity: visualOpacity }}>
          {visualLayer}
          {!scene.is_title_card && !isAhaSubtitle && (scene.word_timestamps?.length ?? 0) > 0 && (
            <SubtitleOverlay wordTimestamps={scene.word_timestamps} highlightEnabled={highlightEnabled} orientation={orientation} />
          )}
        </div>
      </SceneTransition>

      {/* Eli character overlay — z:5, outside SceneTransition so it won't fade/clip during transitions.
          Suppressed for aha-subtitle scenes, which take the full frame with their own typography. */}
      {!isAhaSubtitle && scene.eli_overlay?.enabled && scene.eli_overlay.frame_id && scene.character_frames_base_url && (
        <EliOverlay
          overlay={scene.eli_overlay}
          phraseTimestamps={scene.phrase_timestamps}
          characterFramesBaseUrl={scene.character_frames_base_url}
          sceneDurationInFrames={totalSceneFrames}
          sceneId={scene.id}
          orientation={orientation}
        />
      )}

      {/* Audio layer — always plays regardless of visual in/out and transitions */}
      {scene.audio_path && (
        <Audio src={scene.audio_path} volume={1} />
      )}
    </div>
  );
};
