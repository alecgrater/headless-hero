/**
 * CameraDrift camera effect — slow continuous camera motion over the entire scene.
 * Applies eased scale/translate to eliminate static frames.
 *
 * Motion types:
 *   zoom_in  — push toward anchor
 *   zoom_out — pull back from anchor
 *   pan_left / pan_right — lateral slide with vertical positioning from anchor
 *   drift_diagonal — diagonal slide toward/away from anchor corner
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

/** Map 9-point anchor string to CSS transformOrigin value. */
function anchorToOrigin(anchor: DriftFX["anchor"]): string {
  const map: Record<string, string> = {
    "top-left": "0% 0%",
    "top-center": "50% 0%",
    "top-right": "100% 0%",
    "center-left": "0% 50%",
    "center": "50% 50%",
    "center-right": "100% 50%",
    "bottom-left": "0% 100%",
    "bottom-center": "50% 100%",
    "bottom-right": "100% 100%",
  };
  return map[anchor] ?? "50% 50%";
}

export const CameraDrift: React.FC<Props> = ({
  children,
  motion,
  intensity,
  anchor,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const progress = interpolate(frame, [0, durationInFrames], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.inOut(Easing.ease),
  });

  let transform: string;
  const origin = anchorToOrigin(anchor);

  // Range in pixels for pan/diagonal (based on 1920px width)
  const panRange = intensity * 1920 * 0.5;

  switch (motion) {
    case "zoom_in": {
      const scale = 1 + intensity * progress;
      transform = `scale(${scale})`;
      break;
    }
    case "zoom_out": {
      const scale = 1 + intensity * (1 - progress);
      transform = `scale(${scale})`;
      break;
    }
    case "pan_left": {
      const overscale = 1 + intensity;
      const tx = panRange - 2 * panRange * progress;
      transform = `scale(${overscale}) translateX(${tx}px)`;
      break;
    }
    case "pan_right": {
      const overscale = 1 + intensity;
      const tx = -panRange + 2 * panRange * progress;
      transform = `scale(${overscale}) translateX(${tx}px)`;
      break;
    }
    case "drift_diagonal": {
      const overscale = 1 + intensity;
      const tx = panRange * 0.7 * (1 - 2 * progress);
      const ty = panRange * 0.5 * (1 - 2 * progress);
      transform = `scale(${overscale}) translate(${tx}px, ${ty}px)`;
      break;
    }
    default:
      transform = "none";
  }

  return (
    <div style={{ width: "100%", height: "100%", overflow: "hidden" }}>
      <div
        style={{
          width: "100%",
          height: "100%",
          transform,
          transformOrigin: origin,
          willChange: "transform",
        }}
      >
        {children}
      </div>
    </div>
  );
};
