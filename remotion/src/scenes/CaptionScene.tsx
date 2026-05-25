import React, { useMemo } from "react";
import { Img, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";
import type { Orientation, SceneInput, VisualCanvas, WordTimestamp } from "../types";
import { StaticCanvas } from "./StaticCanvas";
import { captionWordsForDisplay, splitCaptionWords } from "../utils/captionText";
import { findWordBoundary } from "../utils/wordMatch";

const { fontFamily } = loadFont("normal", {
  weights: ["800", "900"],
  subsets: ["latin"],
});

interface Props {
  scene: SceneInput;
  orientation?: Orientation;
  visualCanvas?: VisualCanvas | null;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function captionFontSize(wordCount: number, orientation: Orientation): number {
  if (orientation === "vertical") {
    if (wordCount <= 4) return 116;
    if (wordCount <= 8) return 92;
    return 76;
  }

  if (wordCount <= 5) return 118;
  if (wordCount <= 10) return 92;
  return 76;
}

function getTimedWords(
  timestamps: WordTimestamp[],
  captionText: string,
  displayWordCount: number,
): WordTimestamp[] {
  if (timestamps.length === 0 || displayWordCount === 0) return [];

  const boundary = findWordBoundary(timestamps, captionText);
  if (boundary.subtitleWords.length >= displayWordCount) {
    return boundary.subtitleWords.slice(0, displayWordCount);
  }

  return timestamps.slice(-displayWordCount);
}

export const CaptionScene: React.FC<Props> = ({
  scene,
  orientation = "horizontal",
  visualCanvas,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const captionText = scene.caption_text?.trim() || scene.narration || "";
  const displayWords = useMemo(
    () =>
      captionWordsForDisplay({
        captionText: scene.caption_text,
        narration: scene.narration,
      }),
    [scene.caption_text, scene.narration],
  );
  const words = useMemo(
    () => splitCaptionWords(displayWords.join(" "), scene.caption_emphasis),
    [displayWords, scene.caption_emphasis],
  );
  const timedWords = useMemo(
    () => getTimedWords(scene.word_timestamps ?? [], captionText, words.length),
    [captionText, scene.word_timestamps, words.length],
  );
  const hasImage = Boolean(scene.image_path);
  const isVertical = orientation === "vertical";
  const fontSize = captionFontSize(words.length, orientation);
  const intro = spring({
    frame,
    fps,
    config: { damping: 18, mass: 0.8 },
    from: 0.94,
    to: 1,
  });

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        overflow: "hidden",
        color: "#FFFFFF",
        fontFamily,
      }}
    >
      <StaticCanvas canvas={visualCanvas} />
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "linear-gradient(135deg, rgba(5,5,5,0.72) 0%, rgba(12,12,12,0.28) 42%, rgba(5,5,5,0.76) 100%)",
        }}
      />
      {hasImage && (
        <div
          style={{
            position: "absolute",
            top: isVertical ? 96 : 120,
            bottom: isVertical ? height * 0.5 : 120,
            left: isVertical ? 78 : 116,
            right: isVertical ? 78 : width * 0.56,
            border: "10px solid #FFFFFF",
            boxShadow: "0 34px 80px rgba(0,0,0,0.45)",
            overflow: "hidden",
            transform: `rotate(-1.5deg) scale(${intro})`,
            background: "#111111",
          }}
        >
          <Img
            src={scene.image_path ?? ""}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
            }}
          />
        </div>
      )}
      <div
        style={{
          position: "absolute",
          top: hasImage && isVertical ? height * 0.48 : 0,
          bottom: 0,
          left: hasImage && !isVertical ? width * 0.46 : isVertical ? 70 : 145,
          right: isVertical ? 70 : 145,
          display: "flex",
          alignItems: "center",
          justifyContent: hasImage && !isVertical ? "flex-start" : "center",
          textAlign: hasImage && !isVertical ? "left" : "center",
          padding: isVertical ? "80px 0 120px" : "110px 0",
        }}
      >
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            justifyContent: hasImage && !isVertical ? "flex-start" : "center",
            gap: isVertical ? "0.14em 0.22em" : "0.12em 0.2em",
            maxWidth: isVertical ? "100%" : hasImage ? 860 : 1280,
            fontSize,
            fontWeight: 900,
            lineHeight: 0.98,
            textTransform: "uppercase",
            letterSpacing: 0,
          }}
        >
          {words.map((word, index) => {
            const timedWord = timedWords[index];
            const startFrame = timedWord
              ? Math.round((timedWord.start_ms / 1000) * fps)
              : Math.round(index * Math.max(4, fps * 0.14));
            const age = frame - startFrame;
            const reveal = clamp(age / 7, 0, 1);
            const pop = spring({
              frame: Math.max(0, age),
              fps,
              config: { damping: word.emphasized ? 10 : 14, mass: 0.55 },
              from: 0.68,
              to: 1,
            });
            const pulse = word.emphasized
              ? 1 + Math.sin(Math.max(0, age) * 0.18) * 0.035
              : 1;

            return (
              <span
                key={`${word.text}-${index}`}
                style={{
                  display: "inline-block",
                  opacity: reveal,
                  color: word.emphasized ? "#FF1F1F" : "#FFFFFF",
                  transform: `translateY(${(1 - reveal) * 34}px) scale(${pop * pulse})`,
                  textShadow: word.emphasized
                    ? "0 7px 0 #000000, 0 0 34px rgba(255,31,31,0.76), 0 20px 38px rgba(0,0,0,0.72)"
                    : "0 7px 0 #000000, 0 16px 34px rgba(0,0,0,0.68)",
                }}
              >
                {word.text}
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
};
