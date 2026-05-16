/**
 * SubtitleScene — dramatic aha-moment text reveal.
 * Used for "aha_subtitle" visual beats: dramatic reveals, shocking stats.
 *
 * Three-phase architecture:
 * 1. Lead-In: Glow orb + expanding rings while narrator builds up
 * 2. Word Reveal: Words appear one-by-one synced to word_timestamps
 * 3. Hold: All words visible with ambient glow pulse
 */
import React, { useMemo } from "react";
import { useCurrentFrame, useVideoConfig, spring } from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";
import type { SceneInput, Orientation } from "../types";
import { findWordBoundary } from "../utils/wordMatch";

const { fontFamily } = loadFont("normal", {
  weights: ["800"],
  subsets: ["latin"],
});

interface Props {
  scene: SceneInput;
  orientation?: Orientation;
}

/** Adaptive font size based on character count and orientation. */
function getFontSize(charCount: number, orientation: Orientation): number {
  if (orientation === "vertical") {
    // Vertical (1080w): bump everything up — less horizontal room to break into lines.
    if (charCount < 40) return 110;
    if (charCount < 80) return 92;
    return 76;
  }
  // Horizontal (1920w): original ramp.
  if (charCount < 40) return 96;
  if (charCount < 80) return 72;
  return 56;
}

/** Clamp a value between min and max. */
function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/** Expanding ring component for lead-in animation. */
const ExpandingRing: React.FC<{
  progress: number;
  delay: number;
  maxRadius: number;
}> = ({ progress, delay, maxRadius }) => {
  const p = clamp((progress - delay) / (1 - delay), 0, 1);
  if (p <= 0) return null;

  const radius = p * maxRadius;
  const opacity = 0.3 * (1 - p);

  return (
    <circle
      cx="50%"
      cy="50%"
      r={radius}
      fill="none"
      stroke={`rgba(255, 255, 255, ${opacity})`}
      strokeWidth={2}
    />
  );
};

export const SubtitleScene: React.FC<Props> = ({ scene, orientation = "horizontal" }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const text = scene.narration || "";
  const fontSize = getFontSize(text.length, orientation);
  const timestamps = scene.word_timestamps ?? [];

  // Split timestamps into lead-in and subtitle words
  const boundary = useMemo(
    () => findWordBoundary(timestamps, text),
    [timestamps, text],
  );

  // --- Fallback: no word_timestamps, show static styled text ---
  if (timestamps.length === 0) {
    const fadeIn = spring({
      frame,
      fps,
      config: { damping: 15, mass: 0.8 },
      from: 0,
      to: 1,
    });
    return (
      <div style={backgroundStyle}>
        <div
          style={{
            ...textContainerStyle,
            fontSize,
            opacity: fadeIn,
            transform: `scale(${0.85 + 0.15 * fadeIn})`,
            ...gradientTextStyle,
            textShadow: glowShadow(1),
          }}
        >
          {text}
        </div>
      </div>
    );
  }

  // Frame boundaries for phases
  const subtitleStartFrame = boundary.subtitleWords.length > 0
    ? Math.round((boundary.subtitleStartMs / 1000) * fps)
    : 0;
  const lastWordEndFrame = boundary.subtitleWords.length > 0
    ? Math.round(
        (boundary.subtitleWords[boundary.subtitleWords.length - 1].end_ms / 1000) * fps,
      )
    : 0;

  const hasLeadIn = boundary.leadInWords.length > 0;
  const leadInFrames = hasLeadIn ? subtitleStartFrame : 0;

  // Phase determination
  const isLeadIn = hasLeadIn && frame < subtitleStartFrame;
  const isWordReveal = frame >= subtitleStartFrame && frame < lastWordEndFrame;
  const isHold = frame >= lastWordEndFrame;

  // Cross-fade: lead-in elements fade out over 8 frames as word reveal begins
  const leadInFadeOut = hasLeadIn
    ? clamp(1 - (frame - subtitleStartFrame) / 8, 0, 1)
    : 0;

  // Lead-in progress (0 → 1 over lead-in duration)
  const leadInProgress = hasLeadIn
    ? clamp(frame / Math.max(leadInFrames, 1), 0, 1)
    : 0;

  // Ambient glow pulse during hold phase (0.5 Hz)
  const holdPulse = isHold
    ? 0.7 + 0.3 * Math.sin(((frame - lastWordEndFrame) / fps) * Math.PI)
    : 1;

  // Tokenize subtitle text into words for rendering
  const displayWords = text.split(/\s+/).filter((w) => w.length > 0);

  return (
    <div style={backgroundStyle}>
      {/* Lead-in: glow orb + rings */}
      {(isLeadIn || leadInFadeOut > 0) && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            opacity: isLeadIn ? 1 : leadInFadeOut,
          }}
        >
          {/* Central glow orb */}
          <div
            style={{
              position: "absolute",
              width: 160,
              height: 160,
              borderRadius: "50%",
              background:
                "radial-gradient(circle, rgba(251,191,36,0.6) 0%, rgba(251,191,36,0.2) 40%, transparent 70%)",
              filter: "blur(20px)",
              transform: `scale(${
                0.8 + 0.4 * leadInProgress + 0.1 * Math.sin(frame * 0.15)
              })`,
            }}
          />
          {/* Expanding rings */}
          <svg
            width="800"
            height="800"
            style={{ position: "absolute" }}
            viewBox="0 0 800 800"
          >
            <ExpandingRing
              progress={leadInProgress}
              delay={0}
              maxRadius={350}
            />
            <ExpandingRing
              progress={leadInProgress}
              delay={0.2}
              maxRadius={300}
            />
            <ExpandingRing
              progress={leadInProgress}
              delay={0.4}
              maxRadius={250}
            />
          </svg>
        </div>
      )}

      {/* Word reveal + hold */}
      {(isWordReveal || isHold) && (
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "center",
            alignItems: "center",
            gap: "0.2em",
            maxWidth: orientation === "vertical" ? "92%" : "85%",
            fontFamily,
            fontWeight: 800,
            fontSize,
            lineHeight: 1.4,
            letterSpacing: "0.02em",
            textShadow: glowShadow(holdPulse),
          }}
        >
          {displayWords.map((word, i) => {
            // Find corresponding timestamp for this display word
            const ts = boundary.subtitleWords[i];
            const wordStartFrame = ts
              ? Math.round((ts.start_ms / 1000) * fps)
              : subtitleStartFrame;

            const wordAge = frame - wordStartFrame;

            // Per-word entry animation (~8 frames)
            const entryProgress = clamp(wordAge / 8, 0, 1);
            const wordScale = spring({
              frame: Math.max(0, wordAge),
              fps,
              config: { damping: 14, mass: 0.6 },
              from: 0.7,
              to: 1,
            });
            const wordY = (1 - entryProgress) * 30;
            const wordOpacity = clamp(wordAge / 5, 0, 1);

            return (
              <span
                key={i}
                style={{
                  display: "inline-block",
                  opacity: wordAge < 0 ? 0 : wordOpacity,
                  transform: `translateY(${wordAge < 0 ? 30 : wordY}px) scale(${wordAge < 0 ? 0.7 : wordScale})`,
                  ...gradientTextStyle,
                }}
              >
                {word}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
};

// --- Shared styles ---

const backgroundStyle: React.CSSProperties = {
  width: "100%",
  height: "100%",
  background: "radial-gradient(ellipse at center, #0a0a0a 0%, #000 70%)",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  padding: 120,
  position: "relative",
  overflow: "hidden",
};

const textContainerStyle: React.CSSProperties = {
  fontFamily,
  fontWeight: 800,
  textAlign: "center",
  lineHeight: 1.4,
  letterSpacing: "0.02em",
  maxWidth: "85%",
};

const gradientTextStyle: React.CSSProperties = {
  background: "linear-gradient(180deg, #FFFFFF 0%, #E2E8F0 50%, #94A3B8 100%)",
  backgroundClip: "text",
  WebkitBackgroundClip: "text",
  color: "transparent",
  WebkitTextFillColor: "transparent",
};

function glowShadow(intensity: number): string {
  const r = Math.round(30 * intensity);
  const r2 = Math.round(60 * intensity);
  return `0 0 ${r}px rgba(251,191,36,0.4), 0 0 ${r2}px rgba(251,191,36,0.2), 0 4px 8px rgba(0,0,0,0.8)`;
}
