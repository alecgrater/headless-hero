/**
 * MultiFrameScene — renders N images with crossfade between them.
 * Each frame gets equal screen time with smooth transitions.
 * No camera motion; crossfade is the primary visual effect.
 */
import React from "react";
import { Img, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import type { SceneInput } from "../types";

interface Props {
  scene: SceneInput;
}

const CROSSFADE_DURATION_FRAMES = 12; // ~0.4s at 30fps

export const MultiFrameScene: React.FC<Props> = ({ scene }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const framePaths = scene.frame_paths ?? [];

  if (framePaths.length === 0) {
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
        No frames
      </div>
    );
  }

  if (framePaths.length === 1) {
    return (
      <div style={{ width: "100%", height: "100%" }}>
        <Img
          src={framePaths[0]}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      </div>
    );
  }

  const n = framePaths.length;
  const framesPerImage = durationInFrames / n;

  return (
    <div style={{ width: "100%", height: "100%", backgroundColor: "#000", position: "relative" }}>
      {framePaths.map((path, i) => {
        const startFrame = i * framesPerImage;
        const endFrame = startFrame + framesPerImage;

        // Opacity: fade in at start, full, fade out at end
        let opacity: number;
        if (i === 0) {
          // First frame: full, then fade out
          opacity = interpolate(
            frame,
            [endFrame - CROSSFADE_DURATION_FRAMES, endFrame],
            [1, 0],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
          );
        } else if (i === n - 1) {
          // Last frame: fade in, then full
          opacity = interpolate(
            frame,
            [startFrame, startFrame + CROSSFADE_DURATION_FRAMES],
            [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
          );
        } else {
          // Middle frames: fade in, full, fade out
          const fadeIn = interpolate(
            frame,
            [startFrame, startFrame + CROSSFADE_DURATION_FRAMES],
            [0, 1],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
          );
          const fadeOut = interpolate(
            frame,
            [endFrame - CROSSFADE_DURATION_FRAMES, endFrame],
            [1, 0],
            { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
          );
          opacity = Math.min(fadeIn, fadeOut);
        }

        return (
          <div
            key={i}
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              opacity,
            }}
          >
            <Img
              src={path}
              style={{ width: "100%", height: "100%", objectFit: "cover" }}
            />
          </div>
        );
      })}
    </div>
  );
};
