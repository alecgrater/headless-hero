/**
 * PushTransition — pushes previous scene out while new scene pushes in.
 */
import React from "react";
import { useCurrentFrame, interpolate, Easing } from "remotion";

interface Props {
  children: React.ReactNode;
  durationInFrames: number;
  direction?: "left" | "right" | "up" | "down";
}

export const PushTransition: React.FC<Props> = ({
  children,
  durationInFrames,
  direction = "left",
}) => {
  const frame = useCurrentFrame();

  const progress = interpolate(frame, [0, durationInFrames], [1, 0], {
    easing: Easing.out(Easing.cubic),
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  let translateX = 0;
  let translateY = 0;

  switch (direction) {
    case "left":
      translateX = progress * 100;
      break;
    case "right":
      translateX = -progress * 100;
      break;
    case "up":
      translateY = progress * 100;
      break;
    case "down":
      translateY = -progress * 100;
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
