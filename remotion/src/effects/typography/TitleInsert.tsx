/**
 * TitleInsert — oversized word slam for dramatic reveals.
 */
import React from "react";
import { useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";

interface Props {
  text: string;
  enterAt?: number;
  duration?: number;
}

export const TitleInsert: React.FC<Props> = ({
  text,
  enterAt = 0,
  duration = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const enterFrame = Math.round(enterAt * fps);
  const durationFrames = duration > 0 ? Math.round(duration * fps) : durationInFrames * 0.5;
  const endFrame = enterFrame + durationFrames;

  // Scale slam: starts big, springs to normal
  const scaleSpring = spring({
    frame: frame - enterFrame,
    fps,
    config: { damping: 12, mass: 0.6, stiffness: 180 },
  });
  const scale = 1.5 - scaleSpring * 0.5; // 1.5 → 1.0

  // Fade out
  const fadeOut = interpolate(frame, [endFrame - 10, endFrame], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  if (frame < enterFrame || fadeOut <= 0) return null;

  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        opacity: fadeOut * scaleSpring,
        zIndex: 10,
      }}
    >
      <span
        style={{
          fontSize: "80px",
          fontWeight: 900,
          color: "#fff",
          textShadow: "0 4px 16px rgba(0,0,0,0.8)",
          transform: `scale(${scale})`,
          textAlign: "center",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
        }}
      >
        {text}
      </span>
    </div>
  );
};
