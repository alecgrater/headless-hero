/**
 * ParallaxDepth camera effect — foreground/background at different rates.
 * Wraps an image and applies parallax-style depth movement.
 */
import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate, Easing } from "remotion";

interface Props {
  children: React.ReactNode;
  direction?: "left" | "right" | "up" | "down";
  intensity?: "subtle" | "moderate" | "dramatic";
}

const PARALLAX_AMOUNT: Record<string, number> = {
  subtle: 2,
  moderate: 5,
  dramatic: 10,
};

export const ParallaxDepth: React.FC<Props> = ({
  children,
  direction = "left",
  intensity = "moderate",
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const amount = PARALLAX_AMOUNT[intensity] ?? 5;

  const progress = interpolate(frame, [0, durationInFrames], [0, 1], {
    easing: Easing.inOut(Easing.ease),
    extrapolateRight: "clamp",
  });

  let translateX = 0;
  let translateY = 0;

  switch (direction) {
    case "left":
      translateX = -progress * amount;
      break;
    case "right":
      translateX = progress * amount;
      break;
    case "up":
      translateY = -progress * amount;
      break;
    case "down":
      translateY = progress * amount;
      break;
  }

  return (
    <div style={{ width: "100%", height: "100%", overflow: "hidden" }}>
      <div
        style={{
          width: "110%",
          height: "110%",
          marginLeft: "-5%",
          marginTop: "-5%",
          transform: `translate(${translateX}%, ${translateY}%)`,
          willChange: "transform",
        }}
      >
        {children}
      </div>
    </div>
  );
};
