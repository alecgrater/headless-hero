/**
 * RecapCard — brief animated summary between sections.
 */
import React from "react";
import { useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";

interface Props {
  text?: string;
}

export const RecapCard: React.FC<Props> = ({ text }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (!text) return null;

  const entry = spring({
    frame,
    fps,
    config: { damping: 18, mass: 0.6, stiffness: 120 },
  });

  const fadeOut = interpolate(frame, [fps * 2.5, fps * 3], [1, 0], {
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
        backgroundColor: `rgba(0,0,0,${0.7 * entry})`,
        opacity: fadeOut,
        zIndex: 20,
      }}
    >
      <div
        style={{
          backgroundColor: "rgba(30,30,30,0.9)",
          border: "1px solid rgba(139,92,246,0.3)",
          borderRadius: "12px",
          padding: "24px 40px",
          maxWidth: "70%",
          transform: `translateY(${(1 - entry) * 20}px)`,
        }}
      >
        <div
          style={{
            fontSize: "12px",
            fontWeight: 600,
            color: "#8b5cf6",
            textTransform: "uppercase",
            letterSpacing: "0.15em",
            marginBottom: "8px",
          }}
        >
          Recap
        </div>
        <span
          style={{
            fontSize: "24px",
            fontWeight: 500,
            color: "rgba(255,255,255,0.9)",
            lineHeight: 1.4,
          }}
        >
          {text}
        </span>
      </div>
    </div>
  );
};
