/**
 * ShortTitleCardScene — full-frame square image with darken/blur.
 *
 * Zone 1 (upper half): stripped video title — clean, minimal, punchy.
 *   White bold text, tight tracking, single amber accent underline. No bevel/badge/ornaments.
 * Zone 2 (lower half): segment name (larger, primary weight, amber color).
 *   Pops in at TITLE_CARD_BEAT_SECONDS with spring scale + radial glow burst.
 */
import React from "react";
import { Img, useCurrentFrame, useVideoConfig, spring } from "remotion";
import { loadFont as loadDisplayFont } from "@remotion/google-fonts/Montserrat";
import { loadFont as loadHeavyFont } from "@remotion/google-fonts/ArchivoBlack";

const { fontFamily: displayFontFamily } = loadDisplayFont("normal", {
  weights: ["800"],
  subsets: ["latin"],
});

const { fontFamily: heavyFontFamily } = loadHeavyFont("normal", {
  weights: ["400"],
  subsets: ["latin"],
});

interface Props {
  stripped_title: string;
  segment_name: string;
  backdrop_image_path: string;
}

const ACCENT_COLOR = "#fbbf24"; // amber
const BACKDROP_FILTER = "blur(18px) brightness(0.45) saturate(0.7)";

const TITLE_CARD_BEAT_SECONDS = 0.5;
const GLOW_BURST_SECONDS = 0.4;

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function fitTitleFontSize(title: string): number {
  const length = title.trim().length;
  if (length > 64) return 52;
  if (length > 48) return 60;
  if (length > 34) return 68;
  return 78;
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

  const segmentScale = spring({
    frame: Math.max(0, popAge),
    fps,
    config: { damping: 12, mass: 0.7, stiffness: 180, overshootClamping: false },
    from: 0.6,
    to: 1,
  });

  const opacityFrames = Math.max(1, Math.round(0.12 * fps));
  const segmentOpacity = popAge < 0 ? 0 : clamp(popAge / opacityFrames, 0, 1);

  const glowFrames = Math.max(1, Math.round(GLOW_BURST_SECONDS * fps));
  const glowProgress = popAge < 0 ? 0 : clamp(popAge / glowFrames, 0, 1);
  const glowScale = 0.7 + glowProgress * 0.7;
  const glowOpacity = popAge < 0 ? 0 : (1 - glowProgress) * 0.85;

  const titleFontSize = fitTitleFontSize(stripped_title);
  const titleText = stripped_title.toUpperCase();

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
      {/* Full-frame backdrop */}
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

      {/* Zone 1: Stripped title (upper half) — clean, static at t=0 */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          width: "100%",
          height: "50%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          padding: "80px 64px 40px",
          boxSizing: "border-box",
          gap: 20,
        }}
      >
        {/* Title text */}
        <div
          style={{
            fontFamily: displayFontFamily,
            fontWeight: 800,
            fontSize: titleFontSize,
            lineHeight: 1.1,
            color: "#ffffff",
            textAlign: "center",
            letterSpacing: "-0.02em",
            textTransform: "uppercase",
            textShadow: "0 4px 32px rgba(0,0,0,0.9), 0 2px 0 rgba(0,0,0,0.6)",
          }}
        >
          {titleText}
        </div>

        {/* Amber accent bar — the one tasteful flourish */}
        <div
          style={{
            width: 80,
            height: 5,
            borderRadius: 3,
            background: ACCENT_COLOR,
            boxShadow: `0 0 16px rgba(251,191,36,0.7)`,
          }}
        />
      </div>

      {/* Zone divider */}
      <div
        style={{
          position: "absolute",
          top: "49.5%",
          left: 80,
          right: 80,
          height: 1,
          background:
            "linear-gradient(90deg, rgba(255,255,255,0), rgba(255,255,255,0.18), rgba(255,255,255,0))",
        }}
      />

      {/* Zone 2: Segment name (lower half) — pops in at TITLE_CARD_BEAT_SECONDS */}
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
        {/* Glow burst */}
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
                "radial-gradient(ellipse at center, rgba(251,191,36,0.45) 0%, rgba(251,191,36,0.2) 40%, rgba(251,191,36,0) 70%)",
              filter: "blur(8px)",
            }}
          />
        </div>

        {/* Segment name */}
        <div
          style={{
            fontFamily: heavyFontFamily,
            fontWeight: 400,
            fontSize: 110,
            lineHeight: 1.1,
            color: ACCENT_COLOR,
            textAlign: "center",
            letterSpacing: "-0.01em",
            WebkitTextStroke: "4px rgba(75,37,0,0.72)",
            paintOrder: "stroke fill",
            textShadow:
              "0 6px 0 rgba(120,53,15,0.92), 0 12px 28px rgba(0,0,0,0.86), 0 0 30px rgba(251,191,36,0.56)",
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
