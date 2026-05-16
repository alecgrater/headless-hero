/**
 * ShortTitleCardScene — full-frame square image with darken/blur, plus
 * two-zone word-by-word text reveal synced to the intro VO.
 *
 * Zone 1 (upper half): video title (smaller, secondary weight).
 * Zone 2 (lower half): segment name (larger, primary weight, accent color).
 * The em-dash in display_text marks the boundary between the two zones.
 */
import React from "react";
import { Img, useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";
import type { ShortIntroProps } from "../types";

const { fontFamily } = loadFont("normal", {
  weights: ["600", "800", "900"],
  subsets: ["latin"],
});

interface Props {
  intro: ShortIntroProps;
}

const ACCENT_COLOR = "#fbbf24"; // amber accent — matches existing aha-subtitle glow palette
const BACKDROP_FILTER = "blur(18px) brightness(0.45) saturate(0.7)";
const EM_DASH = "—";

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export const ShortTitleCardScene: React.FC<Props> = ({ intro }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Split display_text on em-dash → title words (zone 1) + segment words (zone 2)
  const parts = intro.display_text.split(EM_DASH);
  const titleText = (parts[0] ?? "").trim();
  const segmentText = (parts[1] ?? "").trim();
  const titleWords = titleText.split(/\s+/).filter(Boolean);
  const segmentWords = segmentText.split(/\s+/).filter(Boolean);

  // Filter word_timestamps to non-em-dash entries (ElevenLabs may or may not emit the dash;
  // we strip any timestamp whose word matches the em-dash exactly).
  const wordTimestamps = (intro.word_timestamps ?? []).filter(
    (wt) => wt.word.trim() !== EM_DASH,
  );

  // Map timestamps to zones by index relative to titleWords.length
  function getWordStartFrame(zone: "title" | "segment", index: number): number {
    const globalIdx = zone === "title" ? index : titleWords.length + index;
    const ts = wordTimestamps[globalIdx];
    if (!ts) return 0;
    return Math.round((ts.start_ms / 1000) * fps);
  }

  function renderWord(
    word: string,
    zone: "title" | "segment",
    index: number,
  ): React.ReactNode {
    const wordStartFrame = getWordStartFrame(zone, index);
    const wordAge = frame - wordStartFrame;
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
        key={`${zone}-${index}`}
        style={{
          display: "inline-block",
          opacity: wordAge < 0 ? 0 : wordOpacity,
          transform: `translateY(${wordAge < 0 ? 30 : wordY}px) scale(${
            wordAge < 0 ? 0.7 : wordScale
          })`,
        }}
      >
        {word}
      </span>
    );
  }

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
      {intro.backdrop_image_path && (
        <Img
          src={intro.backdrop_image_path}
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

      {/* Zone 1: Title (upper half) */}
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
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "center",
            gap: "0.25em",
          }}
        >
          {titleWords.map((w, i) => renderWord(w, "title", i))}
        </div>
      </div>

      {/* Zone 2: Segment name (lower half) */}
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
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "center",
            gap: "0.2em",
          }}
        >
          {segmentWords.map((w, i) => renderWord(w, "segment", i))}
        </div>
      </div>
    </div>
  );
};
