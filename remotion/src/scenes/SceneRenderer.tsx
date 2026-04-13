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
import { SubtitleScene } from "./SubtitleScene";

import { ZoomPunch } from "../effects/camera/ZoomPunch";
import { CaptionOverlay } from "../effects/typography/KineticCaption";
import { EliOverlay } from "../effects/overlays/EliOverlay";

interface Props {
  scene: SceneInput;
}

export const SceneRenderer: React.FC<Props> = ({ scene }) => {
  const hasMultipleFrames = scene.frame_paths && scene.frame_paths.length > 1;
  const isVideoClip = scene.media_type === "gameplay_clip" && scene.video_clip_path;
  const isTitleCard = scene.is_title_card && scene.title_card_zoom_target;
  const isAhaSubtitle = scene.visual_beat === "aha_subtitle";
  const fx = scene.fx;

  // Visual layer dispatch
  let visualLayer: React.ReactNode;
  if (isVideoClip) {
    visualLayer = <VideoClipScene scene={scene} />;
  } else if (isTitleCard) {
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
      {/* Visual layer (possibly wrapped in ZoomPunch) */}
      {visualLayer}

      {/* Eli character overlay */}
      {scene.eli_overlay?.enabled && scene.eli_overlay.keyframes.length > 0 && scene.character_frames_base_url && (
        <EliOverlay
          overlay={scene.eli_overlay}
          wordTimestamps={scene.word_timestamps}
          characterFramesBaseUrl={scene.character_frames_base_url}
        />
      )}

      {/* Caption overlay — base subtitles + kinetic emphasis */}
      {!scene.is_title_card && (
        (fx?.kinetic_captions?.words?.length ?? 0) > 0 || (scene.word_timestamps?.length ?? 0) > 0
      ) && (
        <CaptionOverlay
          words={fx?.kinetic_captions?.words ?? []}
          wordTimestamps={scene.word_timestamps}
        />
      )}

      {/* Audio layer — narration voiceover */}
      {scene.audio_path && (
        <Audio src={scene.audio_path} volume={1} />
      )}
    </div>
  );
};
