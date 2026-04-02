/**
 * SceneRenderer — dispatches to the appropriate scene component
 * based on scene type, media_type, and flags.
 * Optionally wraps with ZoomPunch and KineticCaption effects.
 */
import React from "react";
import { Audio } from "remotion";
import type { SceneInput } from "../types";
import { StaticImageScene } from "./StaticImageScene";
import { MultiFrameScene } from "./MultiFrameScene";
import { TitleCardScene } from "./TitleCardScene";
import { VideoClipScene } from "./VideoClipScene";

import { ZoomPunch } from "../effects/camera/ZoomPunch";
import { KineticCaption } from "../effects/typography/KineticCaption";

interface Props {
  scene: SceneInput;
}

export const SceneRenderer: React.FC<Props> = ({ scene }) => {
  const hasMultipleFrames = scene.frame_paths && scene.frame_paths.length > 1;
  const isVideoClip = scene.media_type === "gameplay_clip" && scene.video_clip_path;
  const isTitleCard = scene.is_title_card && scene.title_card_zoom_target;
  const fx = scene.fx;

  // Visual layer dispatch
  let visualLayer: React.ReactNode;
  if (isVideoClip) {
    visualLayer = <VideoClipScene scene={scene} />;
  } else if (isTitleCard) {
    visualLayer = <TitleCardScene scene={scene} />;
  } else if (hasMultipleFrames) {
    visualLayer = <MultiFrameScene scene={scene} />;
  } else {
    visualLayer = <StaticImageScene scene={scene} />;
  }

  // Wrap with ZoomPunch if assigned
  if (fx?.zoom_punch) {
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
      {/* Visual layer (possibly wrapped in ZoomPunch) */}
      {visualLayer}

      {/* Kinetic caption overlay */}
      {fx?.kinetic_captions?.words && fx.kinetic_captions.words.length > 0 && (
        <KineticCaption words={fx.kinetic_captions.words} />
      )}

      {/* Audio layer — narration voiceover */}
      {scene.audio_path && (
        <Audio src={scene.audio_path} volume={1} />
      )}
    </div>
  );
};
