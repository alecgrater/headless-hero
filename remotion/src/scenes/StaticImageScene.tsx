/**
 * StaticImageScene — renders a single image with a subtle constant-zoom motion.
 * Default scene type for ai_generated images.
 */
import React from "react";
import { Img, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import type { SceneInput } from "../types";

interface Props {
  scene: SceneInput;
}

export const StaticImageScene: React.FC<Props> = ({ scene }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  if (!scene.image_path) {
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
        No image
      </div>
    );
  }

  // Subtle constant zoom: 1.0 → 1.02 over scene duration
  const scale = interpolate(frame, [0, durationInFrames], [1.0, 1.02], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        backgroundColor: "#000",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          width: "100%",
          height: "100%",
          transform: `scale(${scale})`,
          transformOrigin: "center center",
        }}
      >
        <Img
          src={scene.image_path}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </div>
    </div>
  );
};
