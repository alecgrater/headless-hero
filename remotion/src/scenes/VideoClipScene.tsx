/**
 * VideoClipScene — renders a real video clip (gameplay) with audio mixing.
 */
import React from "react";
import { OffthreadVideo, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import type { SceneInput } from "../types";

interface Props {
  scene: SceneInput;
}

export const VideoClipScene: React.FC<Props> = ({ scene }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const clipPath = scene.video_clip_path;

  if (!clipPath) {
    return (
      <div
        style={{
          width: "100%",
          height: "100%",
          backgroundColor: "#0a0a0a",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#666",
          fontSize: 24,
        }}
      >
        No video clip
      </div>
    );
  }

  // Fade out at end
  const fadeOutFrames = 9;
  const opacity = interpolate(
    frame,
    [durationInFrames - fadeOutFrames, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <div style={{ width: "100%", height: "100%", backgroundColor: "#000", opacity }}>
      <OffthreadVideo
        src={clipPath}
        style={{ width: "100%", height: "100%", objectFit: "cover" }}
        volume={0.15}
      />
    </div>
  );
};
