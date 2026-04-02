/**
 * ChapterIndicator — global progress bar with chapter tick marks.
 * Rendered as a global overlay spanning the entire video composition.
 */
import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import type { ChapterMarker } from "../../types";

interface Props {
  markers: ChapterMarker[];
  totalFrames: number;
}

const BAR_HEIGHT = 4;
const ACCENT_COLOR = "#8b5cf6"; // violet-500
const LABEL_FLASH_FRAMES = 45; // how long a chapter label stays visible

export const ChapterIndicator: React.FC<Props> = ({ markers, totalFrames }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const progress = frame / (totalFrames || durationInFrames);

  // Fade in at start
  const opacity = interpolate(frame, [0, 30], [0, 0.85], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Find the currently active chapter label (if we just crossed a marker)
  let activeLabel: string | null = null;
  let labelOpacity = 0;
  for (const marker of markers) {
    const framesAfter = frame - marker.frame_offset;
    if (framesAfter >= 0 && framesAfter < LABEL_FLASH_FRAMES) {
      activeLabel = marker.label;
      labelOpacity = framesAfter < 10
        ? interpolate(framesAfter, [0, 10], [0, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          })
        : interpolate(framesAfter, [LABEL_FLASH_FRAMES - 15, LABEL_FLASH_FRAMES], [1, 0], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          });
    }
  }

  return (
    <div
      style={{
        position: "absolute",
        bottom: 0,
        left: 0,
        right: 0,
        height: BAR_HEIGHT + 30, // room for labels
        opacity,
        zIndex: 30,
        pointerEvents: "none",
      }}
    >
      {/* Chapter label */}
      {activeLabel && labelOpacity > 0 && (
        <div
          style={{
            position: "absolute",
            bottom: BAR_HEIGHT + 8,
            left: "50%",
            transform: "translateX(-50%)",
            opacity: labelOpacity,
            fontSize: "16px",
            fontWeight: 700,
            color: "#fff",
            textShadow: "0 2px 8px rgba(0,0,0,0.8)",
            letterSpacing: "0.05em",
            textTransform: "uppercase",
            whiteSpace: "nowrap",
          }}
        >
          {activeLabel}
        </div>
      )}

      {/* Bar background */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: BAR_HEIGHT,
          backgroundColor: "rgba(255,255,255,0.1)",
        }}
      >
        {/* Filled progress */}
        <div
          style={{
            position: "absolute",
            top: 0,
            left: 0,
            height: "100%",
            width: `${Math.min(1, progress) * 100}%`,
            background: `linear-gradient(90deg, ${ACCENT_COLOR}, ${ACCENT_COLOR}dd)`,
          }}
        />

        {/* Chapter tick marks */}
        {markers.map((marker, i) => {
          const position = totalFrames > 0 ? marker.frame_offset / totalFrames : 0;
          return (
            <div
              key={i}
              style={{
                position: "absolute",
                left: `${position * 100}%`,
                top: -2,
                width: 2,
                height: BAR_HEIGHT + 4,
                backgroundColor: "rgba(255,255,255,0.5)",
              }}
            />
          );
        })}
      </div>
    </div>
  );
};
