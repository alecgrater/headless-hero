/**
 * VideoScene — renders a video clip (gameplay footage or user upload)
 * using Remotion's OffthreadVideo for frame-accurate playback.
 * Scene duration is capped by the backend when the source clip is shorter.
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
      style={{
        width: "100%",
        height: "100%",
        objectFit: "cover",
      }}
      pauseWhenBuffering
    />
  );
};
