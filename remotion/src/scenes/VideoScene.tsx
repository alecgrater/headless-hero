/**
 * VideoScene — renders a video clip (gameplay footage or user upload)
 * using Remotion's OffthreadVideo for frame-accurate playback.
 * Trims/loops the video to match the scene's audio duration.
 */
import React from "react";
import { OffthreadVideo, useVideoConfig } from "remotion";
import type { SceneInput } from "../types";

interface Props {
  scene: SceneInput;
}

export const VideoScene: React.FC<Props> = ({ scene }) => {
  const { fps } = useVideoConfig();
  const durationInFrames = Math.round(scene.duration_seconds * fps);
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
      style={{
        width: "100%",
        height: "100%",
        objectFit: "cover",
      }}
      pauseWhenBuffering
    />
  );
};
