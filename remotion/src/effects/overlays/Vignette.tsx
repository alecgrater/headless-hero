/**
 * Vignette — animated dark-edge vignette overlay.
 */
import React from "react";
import { useCurrentFrame, interpolate } from "remotion";

interface Props {
  intensity?: "subtle" | "moderate" | "dramatic";
}

const INTENSITY_MAP: Record<string, string> = {
  subtle: "rgba(0,0,0,0) 60%, rgba(0,0,0,0.3) 100%",
  moderate: "rgba(0,0,0,0) 50%, rgba(0,0,0,0.5) 100%",
  dramatic: "rgba(0,0,0,0) 40%, rgba(0,0,0,0.7) 100%",
};

export const Vignette: React.FC<Props> = ({ intensity = "moderate" }) => {
  const frame = useCurrentFrame();

  const opacity = interpolate(frame, [0, 20], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const gradient = INTENSITY_MAP[intensity] ?? INTENSITY_MAP.moderate;

  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: `radial-gradient(ellipse at center, ${gradient})`,
        opacity,
        pointerEvents: "none",
        zIndex: 11,
      }}
    />
  );
};
