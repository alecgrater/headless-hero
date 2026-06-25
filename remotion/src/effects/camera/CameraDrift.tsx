/**
 * CameraDrift camera effect — slow continuous camera motion over the entire scene.
 *
 * Coverage guarantee: the image ALWAYS fully covers the 1920×1080 frame. No drift
 * state ever pulls an image edge inside the frame, so the global canvas / background
 * color can never show through behind a panning or zooming photo.
 *
 * How it works:
 *   - transformOrigin is locked to the frame center ("50% 50%"). With a center origin
 *     and a `translate(...) scale(...)` transform, the explicit translate is expressed
 *     in real screen pixels and the image's safe travel envelope is exactly
 *     (scale - 1) * dimension / 2 on each axis, independently.
 *   - Every motion is expressed as a per-frame scale `s >= 1 + COVER_EPS` plus a
 *     normalized position (fx, fy) in [-1, 1]. The translate is derived as
 *     (fx, fy) * envelope, so |translate| can never exceed the envelope — coverage
 *     holds for every motion at every frame by construction.
 *   - Pans START slightly more zoomed in and ease back out (REVEAL), so the camera
 *     reveals slightly more of the photo as it slides across — instead of starting at
 *     full frame and sliding an edge off into the background.
 *
 * Motion types:
 *   zoom_in  — push toward the anchored region
 *   zoom_out — pull back from the anchored region (reveals more, never past full cover)
 *   pan_left / pan_right — lateral slide; anchor sets the held vertical bias
 *   drift_diagonal — diagonal slide across the anchored corner
 */
import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate, Easing } from "remotion";
import type { DriftFX } from "../../types";

interface Props {
  children: React.ReactNode;
  motion: DriftFX["motion"];
  intensity: number;
  anchor: DriftFX["anchor"];
}

/** Fraction of the available travel envelope we actually use (margin against subpixel edge bleed). */
const SAFETY = 0.92;
/** Baseline overscan floor — keeps the image fractionally larger than the frame even when fully "revealed". */
const COVER_EPS = 0.012;
/** Extra zoom a pan/diagonal starts with and eases away, so the move reveals slightly more of the photo. */
const REVEAL = 0.025;

/**
 * Normalized translation bias from the 9-point anchor, each axis in {-1, 0, 1}.
 * Positive x reveals more of the LEFT of the image; positive y reveals more of the TOP.
 * So we bias toward the anchored region to keep the subject in view.
 */
function anchorBias(anchor: DriftFX["anchor"]): { x: number; y: number } {
  const a = anchor ?? "center";
  let x = 0;
  if (a.includes("left")) x = 1;
  else if (a.includes("right")) x = -1;
  let y = 0;
  if (a.includes("top")) y = 1;
  else if (a.includes("bottom")) y = -1;
  return { x, y };
}

export const CameraDrift: React.FC<Props> = ({
  children,
  motion,
  intensity,
  anchor,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames, width, height } = useVideoConfig();

  const progress = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.inOut(Easing.ease),
  });

  // Clamp intensity defensively — drives zoom span / pan travel.
  const amt = Math.min(Math.max(intensity, 0.03), 0.14);
  const bias = anchorBias(anchor);

  // Each motion yields a scale (>= 1 + COVER_EPS) and a normalized position in [-1, 1].
  let scale: number;
  let fx: number;
  let fy: number;

  switch (motion) {
    case "zoom_in": {
      scale = 1 + COVER_EPS + amt * progress;
      // Drift gently toward the anchored region as it pushes in.
      fx = bias.x * progress;
      fy = bias.y * progress;
      break;
    }
    case "zoom_out": {
      scale = 1 + COVER_EPS + amt * (1 - progress);
      fx = bias.x * (1 - progress);
      fy = bias.y * (1 - progress);
      break;
    }
    case "pan_left": {
      // Start a touch more zoomed in, ease out → reveal slightly more while sliding.
      scale = 1 + COVER_EPS + amt + REVEAL * (1 - progress);
      fx = 1 - 2 * progress; // sweep +1 → -1
      fy = bias.y; // hold the anchored vertical region
      break;
    }
    case "pan_right": {
      scale = 1 + COVER_EPS + amt + REVEAL * (1 - progress);
      fx = -1 + 2 * progress; // sweep -1 → +1
      fy = bias.y;
      break;
    }
    case "drift_diagonal": {
      scale = 1 + COVER_EPS + amt + REVEAL * (1 - progress);
      const dirX = bias.x !== 0 ? bias.x : 1;
      const dirY = bias.y !== 0 ? bias.y : -1;
      fx = dirX * (1 - 2 * progress);
      fy = dirY * (1 - 2 * progress);
      break;
    }
    default: {
      scale = 1 + COVER_EPS;
      fx = 0;
      fy = 0;
    }
  }

  // Safe travel envelope (screen px) given the current scale and a center origin.
  // |translate| never exceeds this, so the image always covers the frame.
  const envX = ((scale - 1) * width) / 2 * SAFETY;
  const envY = ((scale - 1) * height) / 2 * SAFETY;
  const tx = fx * envX;
  const ty = fy * envY;

  return (
    <div style={{ width: "100%", height: "100%", overflow: "hidden" }}>
      <div
        style={{
          width: "100%",
          height: "100%",
          transform: `translate(${tx}px, ${ty}px) scale(${scale})`,
          transformOrigin: "50% 50%",
          willChange: "transform",
        }}
      >
        {children}
      </div>
    </div>
  );
};
