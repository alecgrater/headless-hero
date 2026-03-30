/**
 * ChapterIndicator — thin progress bar showing position in video.
 */
import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";

interface Props {
  /** Progress through the overall video (0-1), if known. */
  videoProgress?: number;
}

export const ChapterIndicator: React.FC<Props> = ({ videoProgress }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  // If overall video progress is known, use it; otherwise use scene progress
  const progress = videoProgress ?? frame / durationInFrames;

  // Fade in
  const opacity = interpolate(frame, [0, 15], [0, 0.7], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        position: "absolute",
        bottom: 0,
        left: 0,
        right: 0,
        height: "3px",
        backgroundColor: "rgba(255,255,255,0.1)",
        opacity,
        zIndex: 20,
      }}
    >
      <div
        style={{
          height: "100%",
          width: `${progress * 100}%`,
          backgroundColor: "#8b5cf6",
          transition: "width 0.1s linear",
        }}
      />
    </div>
  );
};
