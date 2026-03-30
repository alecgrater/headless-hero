/**
 * ChapterTransition — full-screen section title interstitial.
 */
import React from "react";
import { useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";

interface Props {
  title?: string;
  subtitle?: string;
}

export const ChapterTransition: React.FC<Props> = ({ title, subtitle }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (!title) return null;

  const entry = spring({
    frame,
    fps,
    config: { damping: 20, mass: 0.8, stiffness: 100 },
  });

  const fadeOut = interpolate(frame, [fps * 2, fps * 2.5], [1, 0], {
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
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: `rgba(10,10,10,${0.85 * entry})`,
        opacity: fadeOut,
        zIndex: 20,
      }}
    >
      {/* Accent line */}
      <div
        style={{
          width: `${entry * 60}px`,
          height: "3px",
          backgroundColor: "#8b5cf6",
          marginBottom: "20px",
        }}
      />
      <span
        style={{
          fontSize: "48px",
          fontWeight: 800,
          color: "#fff",
          textTransform: "uppercase",
          letterSpacing: "0.1em",
          transform: `translateY(${(1 - entry) * 20}px)`,
        }}
      >
        {title}
      </span>
      {subtitle && (
        <span
          style={{
            fontSize: "20px",
            fontWeight: 400,
            color: "rgba(255,255,255,0.6)",
            marginTop: "8px",
            transform: `translateY(${(1 - entry) * 10}px)`,
          }}
        >
          {subtitle}
        </span>
      )}
    </div>
  );
};
