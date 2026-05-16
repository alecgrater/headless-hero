/**
 * ShortTitleCardScene — full-frame square image with darken/blur, plus
 * static stripped long-form title (upper zone) and pop-in segment name (lower zone).
 *
 * Zone 1 (upper half): stripped video title rendered as a static legendary badge.
 * Appears instantly at t=0 and holds, but carries bevel, stroke, aura, and status trim.
 * Zone 2 (lower half): segment name (larger, primary weight, accent color).
 * Pops in at TITLE_CARD_BEAT_SECONDS with spring scale + radial glow burst.
 */
import React from "react";
import { Img, useCurrentFrame, useVideoConfig, spring } from "remotion";
import { loadFont as loadDisplayFont } from "@remotion/google-fonts/BlackOpsOne";
import { loadFont as loadHeavyFont } from "@remotion/google-fonts/ArchivoBlack";

const { fontFamily: displayFontFamily } = loadDisplayFont("normal", {
  weights: ["400"],
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

const ACCENT_COLOR = "#fbbf24"; // amber accent — matches existing aha-subtitle glow palette
const BACKDROP_FILTER = "blur(18px) brightness(0.45) saturate(0.7)";
const TITLE_STROKE_COLOR = "#2a1700";
const TITLE_SHADOW_COLOR = "rgba(0,0,0,0.9)";

// Beat before the segment name pops in (in seconds). Tunable visually.
const TITLE_CARD_BEAT_SECONDS = 0.5;
// Glow burst total duration (in seconds), from start of pop-in.
const GLOW_BURST_SECONDS = 0.4;

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function fitTitleFontSize(title: string): number {
  const length = title.trim().length;
  if (length > 64) return 52;
  if (length > 48) return 58;
  if (length > 34) return 66;
  return 76;
}

function statusOrnament(side: "left" | "right"): React.CSSProperties {
  return {
    width: 88,
    height: 18,
    borderTop: "4px solid rgba(255, 214, 92, 0.96)",
    borderBottom: "4px solid rgba(255, 115, 0, 0.72)",
    transform: side === "left" ? "skewX(-24deg)" : "skewX(24deg)",
    boxShadow: "0 0 18px rgba(251,191,36,0.8), inset 0 0 12px rgba(255,255,255,0.34)",
    background:
      "linear-gradient(90deg, rgba(255,255,255,0.78), rgba(251,191,36,0.55), rgba(239,68,68,0.0))",
  };
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
          padding: "80px 56px 34px",
          boxSizing: "border-box",
        }}
      >
        <div
          style={{
            position: "absolute",
            top: 80,
            left: "10%",
            right: "10%",
            height: 360,
            background:
              "radial-gradient(ellipse at center, rgba(251,191,36,0.34) 0%, rgba(244,63,94,0.2) 34%, rgba(14,165,233,0.12) 58%, rgba(0,0,0,0) 74%)",
            filter: "blur(18px)",
          }}
        />
        <div
          style={{
            position: "absolute",
            top: 128,
            left: 90,
            right: 90,
            height: 10,
            background:
              "linear-gradient(90deg, rgba(251,191,36,0), rgba(251,191,36,0.95), rgba(255,255,255,0.9), rgba(251,191,36,0.95), rgba(251,191,36,0))",
            boxShadow: "0 0 28px rgba(251,191,36,0.8)",
          }}
        />
        <div
          style={{
            position: "absolute",
            bottom: 96,
            left: 148,
            right: 148,
            height: 7,
            background:
              "linear-gradient(90deg, rgba(14,165,233,0), rgba(14,165,233,0.85), rgba(255,255,255,0.74), rgba(239,68,68,0.8), rgba(239,68,68,0))",
            boxShadow: "0 0 18px rgba(14,165,233,0.68)",
          }}
        />
        <div
          style={{
            position: "relative",
            maxWidth: 940,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            gap: 20,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 22,
              width: "100%",
            }}
          >
            <div style={statusOrnament("left")} />
            <div
              style={{
                fontFamily: heavyFontFamily,
                fontSize: 25,
                lineHeight: 1,
                color: "#fde68a",
                textShadow: "0 0 12px rgba(251,191,36,0.9), 0 3px 10px rgba(0,0,0,0.7)",
              }}
            >
              ★ LEGENDARY STATUS ★
            </div>
            <div style={statusOrnament("right")} />
          </div>

          <div
            style={{
              position: "relative",
              width: "100%",
              transform: "skewX(-3deg)",
            }}
          >
            <div
              aria-hidden
              style={{
                position: "absolute",
                inset: 0,
                transform: "translate(12px, 14px)",
                fontFamily: displayFontFamily,
                fontSize: titleFontSize,
                lineHeight: 1.05,
                color: "#3f1300",
                WebkitTextStroke: "12px rgba(0,0,0,0.78)",
                textAlign: "center",
                letterSpacing: 0,
                filter: "blur(0.2px)",
              }}
            >
              {titleText}
            </div>
            <div
              aria-hidden
              style={{
                position: "absolute",
                inset: 0,
                transform: "translate(-7px, -8px)",
                fontFamily: displayFontFamily,
                fontSize: titleFontSize,
                lineHeight: 1.05,
                color: "#ffffff",
                WebkitTextStroke: "5px rgba(255,255,255,0.86)",
                textAlign: "center",
                letterSpacing: 0,
                opacity: 0.8,
                filter: "blur(0.6px)",
              }}
            >
              {titleText}
            </div>
            <div
              style={{
                position: "relative",
                fontFamily: displayFontFamily,
                fontSize: titleFontSize,
                lineHeight: 1.05,
                color: "#FFFFFF",
                background:
                  "linear-gradient(180deg, #ffffff 0%, #fff7c2 22%, #facc15 47%, #f97316 70%, #ffffff 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
                WebkitTextStroke: `5px ${TITLE_STROKE_COLOR}`,
                paintOrder: "stroke fill",
                textAlign: "center",
                letterSpacing: 0,
                textTransform: "uppercase",
                textShadow: [
                  `0 7px 0 ${TITLE_STROKE_COLOR}`,
                  `0 16px 24px ${TITLE_SHADOW_COLOR}`,
                  "0 0 20px rgba(251,191,36,0.9)",
                  "0 0 44px rgba(239,68,68,0.64)",
                  "0 0 64px rgba(14,165,233,0.38)",
                ].join(", "),
              }}
            >
              {titleText}
            </div>
            <div
              aria-hidden
              style={{
                position: "absolute",
                top: "-12%",
                left: "8%",
                width: "84%",
                height: "38%",
                background:
                  "linear-gradient(180deg, rgba(255,255,255,0.55), rgba(255,255,255,0.08), rgba(255,255,255,0))",
                mixBlendMode: "screen",
                transform: "skewX(-8deg)",
                clipPath: "polygon(4% 0, 100% 0, 91% 100%, 0 76%)",
              }}
            />
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 14,
            }}
          >
            {["◆", "✦", "◆"].map((mark, index) => (
              <div
                key={`${mark}-${index}`}
                style={{
                  fontFamily: heavyFontFamily,
                  fontSize: index === 1 ? 32 : 22,
                  lineHeight: 1,
                  color: index === 1 ? "#ffffff" : ACCENT_COLOR,
                  textShadow:
                    "0 0 14px rgba(251,191,36,0.9), 0 3px 12px rgba(0,0,0,0.8)",
                }}
              >
                {mark}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Zone divider: keeps the two big title moments connected without moving either one. */}
      <div
        style={{
          position: "absolute",
          top: "49.5%",
          left: 80,
          right: 80,
          height: 2,
          background:
            "linear-gradient(90deg, rgba(255,255,255,0), rgba(251,191,36,0.58), rgba(255,255,255,0.42), rgba(251,191,36,0.58), rgba(255,255,255,0))",
          boxShadow: "0 0 18px rgba(251,191,36,0.48)",
        }}
      />

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
            fontFamily: heavyFontFamily,
            fontWeight: 400,
            fontSize: 110,
            lineHeight: 1.1,
            color: ACCENT_COLOR,
            textAlign: "center",
            letterSpacing: 0,
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
