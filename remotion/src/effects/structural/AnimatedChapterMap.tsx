/**
 * AnimatedChapterMap — full chapter map that zooms to the current chapter circle.
 *
 * Timeline (~2 seconds at 30fps = 60 frames):
 * - Frames 0-15: Fade in full chapter map with all circles visible
 * - Frames 15-45: Zoom/pan to center on current chapter circle
 * - Frames 45-60: Hold on zoomed view with title, then cut to scene content
 */
import React from "react";
import { Img, useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";
import type { ChapterMapData } from "../../types";

interface Props {
  chapterMap: ChapterMapData;
  currentChapterIndex: number;
}

export const AnimatedChapterMap: React.FC<Props> = ({
  chapterMap,
  currentChapterIndex,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();

  // Fade in
  const fadeIn = interpolate(frame, [0, 15], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Zoom/pan to current chapter (starts at frame 15)
  const zoomProgress = frame >= 15
    ? spring({
        frame: frame - 15,
        fps,
        config: {
          damping: 50,
          mass: 1,
          stiffness: 30,
          overshootClamping: true,
        },
      })
    : 0;

  // Get the target circle for the current chapter
  const target = chapterMap.circles[currentChapterIndex];
  if (!target) {
    // Fallback: just show the image
    return chapterMap.image_path ? (
      <div style={{ width: "100%", height: "100%", backgroundColor: "#000" }}>
        <Img
          src={chapterMap.image_path}
          style={{ width: "100%", height: "100%", objectFit: "cover", opacity: fadeIn }}
        />
      </div>
    ) : null;
  }

  // Target: circle fills ~60% of frame
  const targetScale = Math.min(2.5, Math.max(width, height) * 0.6 / (target.radius * 2));
  const scale = 1 + (targetScale - 1) * zoomProgress;

  // Translate to center the target circle
  const centerX = width / 2;
  const centerY = height / 2;
  const offsetX = (centerX - target.x) * zoomProgress;
  const offsetY = (centerY - target.y) * zoomProgress;

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        backgroundColor: "#000",
        overflow: "hidden",
        opacity: fadeIn,
      }}
    >
      <div
        style={{
          width: "100%",
          height: "100%",
          transform: `translate(${offsetX}px, ${offsetY}px) scale(${scale})`,
          transformOrigin: `${target.x}px ${target.y}px`,
          willChange: "transform",
        }}
      >
        {chapterMap.image_path && (
          <Img
            src={chapterMap.image_path}
            style={{ width: "100%", height: "100%", objectFit: "cover" }}
          />
        )}
      </div>

      {/* Current chapter label overlay */}
      {zoomProgress > 0.5 && (
        <div
          style={{
            position: "absolute",
            bottom: "12%",
            left: 0,
            right: 0,
            display: "flex",
            justifyContent: "center",
            opacity: interpolate(zoomProgress, [0.5, 0.8], [0, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            }),
          }}
        >
          <span
            style={{
              fontSize: "48px",
              fontWeight: 800,
              color: "#fff",
              textShadow: "0 4px 16px rgba(0,0,0,0.9)",
              textTransform: "uppercase",
              letterSpacing: "0.05em",
            }}
          >
            {target.label}
          </span>
        </div>
      )}
    </div>
  );
};
