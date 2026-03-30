/**
 * WordReveal — word-by-word reveal synced with approximate timing.
 */
import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";

interface Props {
  text: string;
  position?: string;
  enterAt?: number;
  duration?: number;
}

export const WordReveal: React.FC<Props> = ({
  text,
  position = "lower_third",
  enterAt = 0,
  duration = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const enterFrame = Math.round(enterAt * fps);
  const durationFrames = duration > 0 ? Math.round(duration * fps) : durationInFrames;

  const words = text.split(/\s+/);
  const framesPerWord = durationFrames / words.length;

  // Fade out at end
  const endFrame = enterFrame + durationFrames;
  const fadeOut = interpolate(frame, [endFrame - 10, endFrame], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  if (frame < enterFrame || fadeOut <= 0) return null;

  const positionStyle = getPositionStyle(position);

  return (
    <div
      style={{
        ...positionStyle,
        position: "absolute",
        display: "flex",
        flexWrap: "wrap",
        justifyContent: "center",
        gap: "0.3em",
        padding: "16px 32px",
        opacity: fadeOut,
        zIndex: 10,
      }}
    >
      {words.map((word, i) => {
        const wordStart = enterFrame + i * framesPerWord;
        const opacity = interpolate(frame, [wordStart, wordStart + 5], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        return (
          <span
            key={i}
            style={{
              fontSize: "36px",
              fontWeight: 700,
              color: "#fff",
              textShadow: "0 2px 6px rgba(0,0,0,0.7)",
              opacity,
            }}
          >
            {word}
          </span>
        );
      })}
    </div>
  );
};

function getPositionStyle(position: string): React.CSSProperties {
  switch (position) {
    case "top":
      return { top: "10%", left: 0, right: 0, textAlign: "center" };
    case "center":
      return { top: "40%", left: 0, right: 0, textAlign: "center" };
    case "bottom":
      return { bottom: "10%", left: 0, right: 0, textAlign: "center" };
    case "lower_third":
    default:
      return { bottom: "15%", left: 0, right: 0, textAlign: "center" };
  }
}
