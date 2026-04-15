/**
 * MultiFrameScene — renders N images with per-frame transitions.
 * Supports three transition types per frame directive:
 *   - "crossfade" (default): smooth 12-frame opacity interpolation
 *   - "cut": instant switch (0 transition frames)
 *   - "fade_black": 6-frame fade out → 3-frame black hold → 6-frame fade in
 * Subtitle frames (source === "subtitle") render text-on-black instead of <Img>.
 */
import React from "react";
import { Img, useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import type { SceneInput } from "../types";

interface Props {
  scene: SceneInput;
}

const CROSSFADE_FRAMES = 12; // ~0.4s at 30fps
const FADE_BLACK_OUT = 6;
const FADE_BLACK_HOLD = 3;
const FADE_BLACK_IN = 6;

/**
 * Renders a subtitle frame: white text centered on black.
 */
const SubtitleFrame: React.FC<{ text: string; opacity: number }> = ({
  text,
  opacity,
}) => {
  const charCount = text.length;
  const fontSize = charCount < 60 ? 72 : charCount < 120 ? 56 : 44;

  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        backgroundColor: "#000",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: 80,
        opacity,
      }}
    >
      <div
        style={{
          color: "#fff",
          fontSize,
          fontWeight: 700,
          textAlign: "center",
          lineHeight: 1.3,
          maxWidth: "85%",
        }}
      >
        {text}
      </div>
    </div>
  );
};

export const MultiFrameScene: React.FC<Props> = ({ scene }) => {
  const frame = useCurrentFrame();
  const { durationInFrames, fps } = useVideoConfig();
  const framePaths = scene.frame_paths ?? [];
  const directives = scene.frame_directives ?? [];

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
    const directive = directives[0];
    const isSubtitle = directive?.source === "subtitle";
    if (isSubtitle) {
      return <SubtitleFrame text={directive.prompt} opacity={1} />;
    }
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

  // Compute per-frame start/end from frame_timings or even split
  const frameRanges: { start: number; end: number }[] = [];
  if (scene.frame_timings && scene.frame_timings.length === n) {
    for (let i = 0; i < n; i++) {
      const start = Math.round(scene.frame_timings[i] * fps);
      const end = i < n - 1 ? Math.round(scene.frame_timings[i + 1] * fps) : durationInFrames;
      frameRanges.push({ start, end });
    }
  } else {
    const framesPerImage = Math.floor(durationInFrames / n);
    for (let i = 0; i < n; i++) {
      frameRanges.push({
        start: i * framesPerImage,
        end: i === n - 1 ? durationInFrames : (i + 1) * framesPerImage,
      });
    }
  }

  // Determine transition type for each frame
  const getTransition = (i: number): "cut" | "crossfade" | "fade_black" => {
    return (directives[i]?.transition as "cut" | "crossfade" | "fade_black") ?? "crossfade";
  };

  // Check if a frame is a subtitle frame
  const isSubtitle = (i: number): boolean => {
    return directives[i]?.source === "subtitle";
  };

  // Compute opacity for fade_black: uses a black overlay that fades in/out
  // This is handled separately with a black overlay div
  return (
    <div style={{ width: "100%", height: "100%", backgroundColor: "#000", position: "relative" }}>
      {framePaths.map((path, i) => {
        const startFrame = frameRanges[i].start;
        const endFrame = frameRanges[i].end;
        const transition = getTransition(i);
        const nextTransition = i < n - 1 ? getTransition(i + 1) : "crossfade";

        let opacity: number;

        if (transition === "cut" && nextTransition === "cut") {
          // Pure cut: visible only during this frame's slot
          opacity = frame >= startFrame && frame < endFrame ? 1 : 0;
        } else if (i === 0) {
          // First frame
          if (nextTransition === "cut") {
            opacity = frame < endFrame ? 1 : 0;
          } else if (nextTransition === "fade_black") {
            opacity = interpolate(
              frame,
              [endFrame - FADE_BLACK_OUT, endFrame],
              [1, 0],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            );
          } else {
            // crossfade out
            opacity = interpolate(
              frame,
              [endFrame - CROSSFADE_FRAMES, endFrame],
              [1, 0],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            );
          }
        } else if (i === n - 1) {
          // Last frame — fade in based on this frame's transition type
          if (transition === "cut") {
            opacity = frame >= startFrame ? 1 : 0;
          } else if (transition === "fade_black") {
            opacity = interpolate(
              frame,
              [startFrame + FADE_BLACK_HOLD, startFrame + FADE_BLACK_HOLD + FADE_BLACK_IN],
              [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            );
          } else {
            opacity = interpolate(
              frame,
              [startFrame, startFrame + CROSSFADE_FRAMES],
              [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            );
          }
        } else {
          // Middle frames: fade in + fade out
          let fadeIn: number;
          if (transition === "cut") {
            fadeIn = frame >= startFrame ? 1 : 0;
          } else if (transition === "fade_black") {
            fadeIn = interpolate(
              frame,
              [startFrame + FADE_BLACK_HOLD, startFrame + FADE_BLACK_HOLD + FADE_BLACK_IN],
              [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            );
          } else {
            fadeIn = interpolate(
              frame,
              [startFrame, startFrame + CROSSFADE_FRAMES],
              [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            );
          }

          let fadeOut: number;
          if (nextTransition === "cut") {
            fadeOut = frame < endFrame ? 1 : 0;
          } else if (nextTransition === "fade_black") {
            fadeOut = interpolate(
              frame,
              [endFrame - FADE_BLACK_OUT, endFrame],
              [1, 0],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            );
          } else {
            fadeOut = interpolate(
              frame,
              [endFrame - CROSSFADE_FRAMES, endFrame],
              [1, 0],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
            );
          }

          opacity = Math.min(fadeIn, fadeOut);
        }

        // Render subtitle frames as text-on-black
        if (isSubtitle(i)) {
          return (
            <SubtitleFrame
              key={i}
              text={directives[i]?.prompt ?? ""}
              opacity={opacity}
            />
          );
        }

        // Skip rendering for empty paths (subtitle placeholders)
        if (!path) {
          return null;
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
