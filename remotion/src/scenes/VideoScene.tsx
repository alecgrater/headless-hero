/**
 * VideoScene — renders an AI-generated video clip with Remotion's
 * OffthreadVideo for frame-accurate playback.
 * AI video can be slowed slightly by the backend to cover narration.
 */
import React from "react";
import { OffthreadVideo } from "remotion";
import type { SceneInput } from "../types";

interface Props {
  scene: SceneInput;
}

export const VideoScene: React.FC<Props> = ({ scene }) => {
  const src = scene.video_path || scene.image_path || "";

  if (!src) {
    return (
      <div
        style={{
          width: "100%",
          height: "100%",
          backgroundColor: "#1a1a2a",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#666",
          fontSize: 24,
        }}
      >
        No video source
      </div>
    );
  }

  return (
    <OffthreadVideo
      src={src}
      playbackRate={scene.video_playback_rate ?? 1}
      style={{
        width: "100%",
        height: "100%",
        objectFit: "cover",
      }}
      pauseWhenBuffering
    />
  );
};
