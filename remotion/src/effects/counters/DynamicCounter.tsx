/**
 * DynamicCounter — numbers counting up when mentioned.
 */
import React from "react";
import { useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";

interface Props {
  targetNumber: number;
  suffix?: string;
  prefix?: string;
  enterAt?: number;
  duration?: number;
}

export const DynamicCounter: React.FC<Props> = ({
  targetNumber,
  suffix = "",
  prefix = "",
  enterAt = 0,
  duration = 2,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enterFrame = Math.round(enterAt * fps);
  const durationFrames = Math.round(duration * fps);
  const endFrame = enterFrame + durationFrames;

  const progress = spring({
    frame: frame - enterFrame,
    fps,
    config: { damping: 30, mass: 1, stiffness: 40 },
  });

  const fadeOut = interpolate(frame, [endFrame, endFrame + 10], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  if (frame < enterFrame || fadeOut <= 0) return null;

  const currentValue = Math.round(targetNumber * progress);
  const formatted = currentValue.toLocaleString();

  return (
    <div
      style={{
        position: "absolute",
        top: "35%",
        left: 0,
        right: 0,
        textAlign: "center",
        opacity: fadeOut,
        zIndex: 10,
      }}
    >
      <span
        style={{
          fontSize: "72px",
          fontWeight: 900,
          color: "#fff",
          textShadow: "0 4px 16px rgba(0,0,0,0.8)",
          fontVariantNumeric: "tabular-nums",
        }}
      >
        {prefix}
        {formatted}
        {suffix}
      </span>
    </div>
  );
};
