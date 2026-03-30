/**
 * Letterbox — animated cinematic bars for dramatic moments.
 */
import React from "react";
import { useCurrentFrame, useVideoConfig, spring } from "remotion";

interface Props {
  barHeight?: number; // percentage of viewport height (default 10%)
}

export const Letterbox: React.FC<Props> = ({ barHeight = 10 }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const progress = spring({
    frame,
    fps,
    config: { damping: 30, mass: 1, stiffness: 60 },
  });

  const height = `${barHeight * progress}%`;

  return (
    <>
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height,
          backgroundColor: "#000",
          zIndex: 12,
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height,
          backgroundColor: "#000",
          zIndex: 12,
        }}
      />
    </>
  );
};
