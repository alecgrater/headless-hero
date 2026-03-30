/**
 * SourceCitation — animated fact/source citation card.
 */
import React from "react";
import { useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";

interface Props {
  text: string;
  enterAt?: number;
  duration?: number;
}

export const SourceCitation: React.FC<Props> = ({
  text,
  enterAt = 0,
  duration = 3,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const enterFrame = Math.round(enterAt * fps);
  const durationFrames = Math.round(duration * fps);
  const endFrame = enterFrame + durationFrames;

  const slideIn = spring({
    frame: frame - enterFrame,
    fps,
    config: { damping: 20, mass: 0.6, stiffness: 120 },
  });

  const fadeOut = interpolate(frame, [endFrame - 10, endFrame], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  if (frame < enterFrame || fadeOut <= 0) return null;

  return (
    <div
      style={{
        position: "absolute",
        bottom: "8%",
        right: "5%",
        transform: `translateY(${(1 - slideIn) * 30}px)`,
        opacity: slideIn * fadeOut,
        zIndex: 10,
      }}
    >
      <div
        style={{
          backgroundColor: "rgba(0, 0, 0, 0.8)",
          backdropFilter: "blur(8px)",
          border: "1px solid rgba(255,255,255,0.1)",
          borderRadius: "8px",
          padding: "10px 16px",
          maxWidth: "400px",
        }}
      >
        <span
          style={{
            fontSize: "14px",
            color: "rgba(255,255,255,0.7)",
            fontStyle: "italic",
          }}
        >
          {text}
        </span>
      </div>
    </div>
  );
};
