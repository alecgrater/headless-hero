/**
 * TitleCardScene — zooms from composite title card into a circle target.
 * Replaces FFmpeg's zoompan-based title card animation.
 */
import React from "react";
import { Img, useCurrentFrame, useVideoConfig, spring } from "remotion";
import type { SceneInput } from "../types";

interface Props {
  scene: SceneInput;
}

export const TitleCardScene: React.FC<Props> = ({ scene }) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames, width, height } = useVideoConfig();

  const imagePath = scene.image_path;
  const target = scene.title_card_zoom_target;

  if (!imagePath) {
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
        No title card image
      </div>
    );
  }

  if (!target) {
    // No zoom target — just show the image with a gentle zoom
    return (
      <div style={{ width: "100%", height: "100%", overflow: "hidden" }}>
        <Img
          src={imagePath}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </div>
    );
  }

  // Spring-based zoom from full card into the circle target
  const zoomProgress = spring({
    frame,
    fps,
    config: {
      damping: 200,
      mass: 1.5,
      stiffness: 10,
      overshootClamping: true,
    },
  });

  // Calculate zoom level needed to fill the viewport with the circle
  const targetRadius = target.radius;
  const finalScale = Math.min(2.5, Math.max(width, height) / (targetRadius * 2));

  const scale = 1 + (finalScale - 1) * zoomProgress;

  // Translate to center the target circle
  const centerX = width / 2;
  const centerY = height / 2;
  const offsetX = (centerX - target.x) * zoomProgress;
  const offsetY = (centerY - target.y) * zoomProgress;

  return (
    <div style={{ width: "100%", height: "100%", overflow: "hidden", backgroundColor: "#000" }}>
      <div
        style={{
          width: "100%",
          height: "100%",
          transform: `translate(${offsetX}px, ${offsetY}px) scale(${scale})`,
          transformOrigin: `${target.x}px ${target.y}px`,
          willChange: "transform",
        }}
      >
        <Img
          src={imagePath}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </div>
    </div>
  );
};
