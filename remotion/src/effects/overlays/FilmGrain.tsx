/**
 * FilmGrain — subtle canvas noise overlay for cinematic feel.
 */
import React, { useMemo } from "react";
import { useCurrentFrame } from "remotion";

interface Props {
  opacity?: number;
}

export const FilmGrain: React.FC<Props> = ({ opacity = 0.06 }) => {
  const frame = useCurrentFrame();

  // Generate a pseudo-random SVG noise pattern that changes each frame
  const seed = frame % 60; // cycle every 2s at 30fps

  const noiseStyle = useMemo(
    () => ({
      position: "absolute" as const,
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      opacity,
      mixBlendMode: "overlay" as const,
      backgroundImage: `url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' seed='${seed}' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E")`,
      backgroundSize: "256px 256px",
      pointerEvents: "none" as const,
      zIndex: 15,
    }),
    [seed, opacity],
  );

  return <div style={noiseStyle} />;
};
