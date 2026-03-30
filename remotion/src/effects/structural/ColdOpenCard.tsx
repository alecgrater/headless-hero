/**
 * ColdOpenCard — bold question/statement in first 5 seconds.
 */
import React from "react";
import { useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";

interface Props {
  text?: string;
}

export const ColdOpenCard: React.FC<Props> = ({ text }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (!text) return null;

  // Spring entry
  const entry = spring({
    frame,
    fps,
    config: { damping: 15, mass: 0.8, stiffness: 150 },
  });

  // Fade out after 3 seconds
  const fadeOut = interpolate(frame, [fps * 3, fps * 4], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  if (fadeOut <= 0) return null;

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
        backgroundColor: `rgba(0,0,0,${0.5 * entry})`,
        opacity: fadeOut,
        zIndex: 20,
      }}
    >
      <div
        style={{
          transform: `scale(${0.8 + entry * 0.2})`,
          maxWidth: "80%",
          textAlign: "center",
        }}
      >
        <span
          style={{
            fontSize: "56px",
            fontWeight: 900,
            color: "#fff",
            textShadow: "0 4px 20px rgba(0,0,0,0.8)",
            lineHeight: 1.2,
          }}
        >
          {text}
        </span>
      </div>
    </div>
  );
};
