/**
 * KineticCaption — key words pop/scale/shake for emphasis.
 */
import React from "react";
import { useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";

interface Props {
  text: string;
  emphasisWords?: string[];
  position?: string;
  enterAt?: number;
  duration?: number;
}

export const KineticCaption: React.FC<Props> = ({
  text,
  emphasisWords = [],
  position = "lower_third",
  enterAt = 0,
  duration = 0,
}) => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const enterFrame = Math.round(enterAt * fps);
  const durationFrames = duration > 0 ? Math.round(duration * fps) : durationInFrames;
  const endFrame = enterFrame + durationFrames;

  // Overall visibility
  const fadeIn = interpolate(frame, [enterFrame, enterFrame + 10], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(frame, [endFrame - 10, endFrame], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const opacity = Math.min(fadeIn, fadeOut);

  if (opacity <= 0) return null;

  const positionStyle = getPositionStyle(position);
  const words = text.split(/\s+/);
  const emphasisSet = new Set(emphasisWords.map((w) => w.toLowerCase()));

  return (
    <div
      style={{
        ...positionStyle,
        opacity,
        position: "absolute",
        display: "flex",
        flexWrap: "wrap",
        justifyContent: "center",
        gap: "0.3em",
        padding: "16px 32px",
        zIndex: 10,
      }}
    >
      {words.map((word, i) => {
        const isEmphasis = emphasisSet.has(word.toLowerCase().replace(/[^a-z]/g, ""));
        if (isEmphasis) {
          const wordEnter = enterFrame + i * 2;
          const scale = spring({
            frame: frame - wordEnter,
            fps,
            config: { damping: 10, mass: 0.5, stiffness: 200 },
          });
          return (
            <span
              key={i}
              style={{
                fontSize: "48px",
                fontWeight: 800,
                color: "#fff",
                textShadow: "0 2px 8px rgba(0,0,0,0.8)",
                transform: `scale(${0.8 + scale * 0.4})`,
                display: "inline-block",
              }}
            >
              {word}
            </span>
          );
        }
        return (
          <span
            key={i}
            style={{
              fontSize: "36px",
              fontWeight: 600,
              color: "rgba(255,255,255,0.9)",
              textShadow: "0 2px 6px rgba(0,0,0,0.6)",
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
