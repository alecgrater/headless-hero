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
  const { fps, width, height } = useVideoConfig();

  const imagePath = scene.image_path;
  const target = scene.title_card_zoom_target;
  const overlay = scene.chapter_overlay;

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

  // Cinematic-chapters chapter card: full-frame image + two-line text overlay
  if (overlay) {
    return (
      <div
        style={{
          width: "100%",
          height: "100%",
          overflow: "hidden",
          position: "relative",
          backgroundColor: "#000",
        }}
      >
        <Img
          src={imagePath}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            width: "100%",
            height: "100%",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            textShadow: "0 4px 24px rgba(0,0,0,0.8)",
            color: "white",
            fontFamily: "Inter, sans-serif",
            pointerEvents: "none",
          }}
        >
          <div
            style={{
              fontSize: 56,
              fontWeight: 600,
              letterSpacing: 8,
              opacity: 0.85,
              textTransform: "uppercase",
            }}
          >
            Level {overlay.level_number}
          </div>
          <div
            style={{
              fontSize: 180,
              fontWeight: 800,
              letterSpacing: 4,
              textTransform: "uppercase",
              marginTop: 24,
            }}
          >
            The {overlay.descriptor}
          </div>
        </div>
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
