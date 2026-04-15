/**
 * SceneRenderer — dispatches to the appropriate scene component
 * based on scene type and flags.
 * Optionally wraps with ZoomPunch effect and subtitle overlay.
 */
import React from "react";
import { Audio, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import type { SceneInput } from "../types";
import { StaticImageScene } from "./StaticImageScene";
import { MultiFrameScene } from "./MultiFrameScene";
import { TitleCardScene } from "./TitleCardScene";
import { SubtitleScene } from "./SubtitleScene";

import { ZoomPunch } from "../effects/camera/ZoomPunch";
import { SubtitleOverlay } from "../effects/typography/Subtitles";

interface Props {
  scene: SceneInput;
}

export const SceneRenderer: React.FC<Props> = ({ scene }) => {
  const hasMultipleFrames = scene.frame_paths && scene.frame_paths.length > 1;
  const isTitleCard = scene.is_title_card && scene.title_card_zoom_target;
  const isAhaSubtitle = scene.visual_beat === "aha_subtitle";
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
    visualLayer = <SubtitleScene scene={scene} />;
  } else if (hasMultipleFrames) {
    visualLayer = <MultiFrameScene scene={scene} />;
  } else {
    visualLayer = <StaticImageScene scene={scene} />;
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

  return (
    <div style={{ width: "100%", height: "100%", position: "relative" }}>
      {/* Visual + subtitle layer with in/out opacity */}
      <div style={{ width: "100%", height: "100%", opacity: visualOpacity }}>
        {visualLayer}
        {!scene.is_title_card && !isAhaSubtitle && (scene.word_timestamps?.length ?? 0) > 0 && (
          <SubtitleOverlay wordTimestamps={scene.word_timestamps} />
        )}
      </div>

      {/* Audio layer — always plays regardless of visual in/out */}
      {scene.audio_path && (
        <Audio src={scene.audio_path} volume={1} />
      )}
    </div>
  );
};
