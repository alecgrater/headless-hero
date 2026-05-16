/**
 * ShortTitleCardScene — full-frame square image with darken/blur, plus
 * static stripped long-form title (upper zone) and pop-in segment name (lower zone).
 *
 * Zone 1 (upper half): stripped video title (smaller, secondary weight, white).
 * Appears instantly at t=0 and holds.
 * Zone 2 (lower half): segment name (larger, primary weight, accent color).
 * Pops in at TITLE_CARD_BEAT_FRAMES with spring scale + radial glow burst.
 */
import React from "react";
import { Img, useCurrentFrame, useVideoConfig, spring } from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";

const { fontFamily } = loadFont("normal", {
  weights: ["600", "800", "900"],
  subsets: ["latin"],
});

interface Props {
  stripped_title: string;
  segment_name: string;
  backdrop_image_path: string;
}

const ACCENT_COLOR = "#fbbf24"; // amber accent — matches existing aha-subtitle glow palette
const BACKDROP_FILTER = "blur(18px) brightness(0.45) saturate(0.7)";

// Beat before the segment name pops in (in seconds). Tunable visually.
const TITLE_CARD_BEAT_SECONDS = 0.5;
// Glow burst total duration (in seconds), from start of pop-in.
const GLOW_BURST_SECONDS = 0.4;

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export const ShortTitleCardScene: React.FC<Props> = ({
  stripped_title,
  segment_name,
  backdrop_image_path,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const popInStartFrame = Math.round(TITLE_CARD_BEAT_SECONDS * fps);
  const popAge = frame - popInStartFrame;

  // Segment-name spring scale: 0.6 -> 1.05 -> 1.0 (natural settle via Remotion spring)
  const segmentScale = spring({
    frame: Math.max(0, popAge),
    fps,
    config: { damping: 12, mass: 0.7, stiffness: 180, overshootClamping: false },
    from: 0.6,
    to: 1,
  });

  // Opacity 0 -> 1 over ~120ms (~3-4 frames at 30fps).
  const opacityFrames = Math.max(1, Math.round(0.12 * fps));
  const segmentOpacity = popAge < 0 ? 0 : clamp(popAge / opacityFrames, 0, 1);

  // Glow burst: scale 0.7 -> 1.4 + opacity 0.85 -> 0 across GLOW_BURST_SECONDS
  const glowFrames = Math.max(1, Math.round(GLOW_BURST_SECONDS * fps));
  const glowProgress = popAge < 0 ? 0 : clamp(popAge / glowFrames, 0, 1);
  const glowScale = 0.7 + glowProgress * 0.7; // 0.7 -> 1.4
  const glowOpacity = popAge < 0 ? 0 : (1 - glowProgress) * 0.85;

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        position: "relative",
        backgroundColor: "#000",
        overflow: "hidden",
      }}
    >
      {/* Full-frame square image backdrop */}
      {backdrop_image_path && (
        <Img
          src={backdrop_image_path}
          style={{
            position: "absolute",
            inset: 0,
            width: "100%",
            height: "100%",
            objectFit: "cover",
            filter: BACKDROP_FILTER,
            transform: "scale(1.05)",
          }}
        />
      )}

      {/* Zone 1: Stripped title (upper half) — static, on at t=0 */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "50%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "0 60px",
          boxSizing: "border-box",
        }}
      >
        <div
          style={{
            fontFamily,
            fontWeight: 600,
            fontSize: 64,
            lineHeight: 1.2,
            color: "#FFFFFF",
            textAlign: "center",
            letterSpacing: "0.005em",
            textShadow: "0 4px 16px rgba(0,0,0,0.7)",
          }}
        >
          {stripped_title}
        </div>
      </div>

      {/* Zone 2: Segment name (lower half) — pops in at TITLE_CARD_BEAT_FRAMES */}
      <div
        style={{
          position: "absolute",
          top: "50%",
          left: 0,
          width: "100%",
          height: "50%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "0 60px",
          boxSizing: "border-box",
        }}
      >
        {/* Glow burst (behind the text, pointer-events: none) */}
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            pointerEvents: "none",
            opacity: glowOpacity,
          }}
        >
          <div
            style={{
              width: "70%",
              height: "60%",
              transform: `scale(${glowScale})`,
              background:
                "radial-gradient(ellipse at center, rgba(251,191,36,0.55) 0%, rgba(251,191,36,0.25) 40%, rgba(251,191,36,0) 70%)",
              filter: "blur(8px)",
            }}
          />
        </div>

        {/* Segment name text */}
        <div
          style={{
            fontFamily,
            fontWeight: 900,
            fontSize: 110,
            lineHeight: 1.1,
            color: ACCENT_COLOR,
            textAlign: "center",
            letterSpacing: "-0.005em",
            textShadow: "0 6px 24px rgba(0,0,0,0.8)",
            opacity: segmentOpacity,
            transform: `scale(${popAge < 0 ? 0.6 : segmentScale})`,
          }}
        >
          {segment_name}
        </div>
      </div>
    </div>
  );
};
