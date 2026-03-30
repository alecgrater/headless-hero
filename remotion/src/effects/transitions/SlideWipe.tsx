/**
 * SlideWipe transition — slides content in from a direction.
 */
import React from "react";
import { useCurrentFrame, interpolate, Easing } from "remotion";

interface Props {
  children: React.ReactNode;
  durationInFrames: number;
  direction?: "left" | "right" | "up" | "down";
}

export const SlideWipe: React.FC<Props> = ({
  children,
  durationInFrames,
  direction = "left",
}) => {
  const frame = useCurrentFrame();

  const progress = interpolate(frame, [0, durationInFrames], [0, 1], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  let translateX = 0;
  let translateY = 0;

  switch (direction) {
    case "left":
      translateX = (1 - progress) * 100;
      break;
    case "right":
      translateX = -(1 - progress) * 100;
      break;
    case "up":
      translateY = (1 - progress) * 100;
      break;
    case "down":
      translateY = -(1 - progress) * 100;
      break;
  }

  return (
    <div
      style={{
        transform: `translate(${translateX}%, ${translateY}%)`,
        width: "100%",
        height: "100%",
      }}
    >
      {children}
    </div>
  );
};
