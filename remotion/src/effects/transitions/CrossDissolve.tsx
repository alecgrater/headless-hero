/**
 * CrossDissolve transition — alpha crossfade between scenes.
 */
import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";

interface Props {
  children: React.ReactNode;
  durationInFrames: number;
  direction: "in" | "out";
}

export const CrossDissolve: React.FC<Props> = ({
  children,
  durationInFrames,
  direction,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames: totalFrames } = useVideoConfig();

  let opacity = 1;
  if (direction === "in") {
    opacity = interpolate(frame, [0, durationInFrames], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    });
  } else {
    opacity = interpolate(
      frame,
      [totalFrames - durationInFrames, totalFrames],
      [1, 0],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
    );
  }

  return <div style={{ opacity }}>{children}</div>;
};
