/**
 * LowerThird — branded info bar that slides/fades in.
 */
import React from "react";
import { useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";

interface Props {
  text: string;
  enterAt?: number;
  duration?: number;
}

export const LowerThird: React.FC<Props> = ({
  text,
  enterAt = 0,
  duration = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const enterFrame = Math.round(enterAt * fps);
  const durationFrames = duration > 0 ? Math.round(duration * fps) : durationInFrames;
  const endFrame = enterFrame + durationFrames;

  // Slide in from left
  const slideIn = spring({
    frame: frame - enterFrame,
    fps,
    config: { damping: 20, mass: 0.8, stiffness: 100 },
  });

  // Fade out
  const fadeOut = interpolate(frame, [endFrame - 15, endFrame], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  if (frame < enterFrame || fadeOut <= 0) return null;

  return (
    <div
      style={{
        position: "absolute",
        bottom: "12%",
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        opacity: fadeOut,
        zIndex: 10,
      }}
    >
      <div
        style={{
          transform: `translateX(${(1 - slideIn) * -100}px)`,
          backgroundColor: "rgba(0, 0, 0, 0.75)",
          backdropFilter: "blur(8px)",
          borderLeft: "3px solid #8b5cf6",
          padding: "12px 24px",
          borderRadius: "0 8px 8px 0",
        }}
      >
        <span
          style={{
            fontSize: "28px",
            fontWeight: 600,
            color: "#fff",
            letterSpacing: "0.02em",
          }}
        >
          {text}
        </span>
      </div>
    </div>
  );
};
