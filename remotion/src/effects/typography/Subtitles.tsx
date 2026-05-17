/**
 * SubtitleOverlay — phrase-based subtitle renderer timed to word_timestamps.
 *
 * Groups words into natural phrases (by punctuation, pauses, or max-length),
 * displays the active phrase with a semi-transparent background bar,
 * and fades out after each phrase ends.
 */
import React, { useMemo } from "react";
import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import type { WordTimestamp, Orientation } from "../../types";
import { VERTICAL_LAYOUT } from "../../scenes/VerticalSceneLayout";
import { formatSubtitleText } from "../../utils/subtitleText";

interface Props {
  wordTimestamps?: WordTimestamp[] | null;
  highlightEnabled?: boolean;
  orientation?: Orientation;
}

const FADE_OUT_FRAMES = 5;

// ---- Phrase grouping for subtitle lines ----

interface SubtitlePhrase {
  words: WordTimestamp[];
  startFrame: number;
  endFrame: number;
}

const MAX_WORDS_PER_LINE = 8;
const PAUSE_THRESHOLD_MS = 300;

function groupIntoPhrases(timestamps: WordTimestamp[], fps: number): SubtitlePhrase[] {
  if (timestamps.length === 0) return [];

  const phrases: SubtitlePhrase[] = [];
  let currentWords: WordTimestamp[] = [];

  for (let i = 0; i < timestamps.length; i++) {
    const w = timestamps[i];
    currentWords.push(w);

    const isLast = i === timestamps.length - 1;
    const hitMax = currentWords.length >= MAX_WORDS_PER_LINE;
    const endsWithPunctuation = /[.!?]$/.test(w.word.trim());
    const longPauseAfter = !isLast && timestamps[i + 1].start_ms - w.end_ms > PAUSE_THRESHOLD_MS;

    if (isLast || hitMax || endsWithPunctuation || longPauseAfter) {
      const startMs = currentWords[0].start_ms;
      const endMs = currentWords[currentWords.length - 1].end_ms;
      phrases.push({
        words: [...currentWords],
        startFrame: Math.round((startMs / 1000) * fps),
        endFrame: Math.round((endMs / 1000) * fps),
      });
      currentWords = [];
    }
  }

  return phrases;
}

// ---- Main component ----

export const SubtitleOverlay: React.FC<Props> = ({ wordTimestamps, highlightEnabled, orientation = "horizontal" }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const phrases = useMemo(
    () => groupIntoPhrases(wordTimestamps ?? [], fps),
    [wordTimestamps, fps],
  );

  if (!wordTimestamps || wordTimestamps.length === 0) return null;

  // Find the active phrase for this frame
  const activePhrase = phrases.find(
    (p) => frame >= p.startFrame && frame <= p.endFrame + FADE_OUT_FRAMES,
  );

  if (!activePhrase) return null;

  // Fade out after phrase ends
  const phraseOver = frame > activePhrase.endFrame;
  const phraseOpacity = phraseOver
    ? interpolate(frame, [activePhrase.endFrame, activePhrase.endFrame + FADE_OUT_FRAMES], [1, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 1;

  if (phraseOpacity <= 0) return null;

  return (
    <div
      style={
        orientation === "vertical"
          ? {
              position: "absolute",
              top: VERTICAL_LAYOUT.TOP_BAND_HEIGHT + VERTICAL_LAYOUT.MIDDLE_BAND_HEIGHT,
              left: 0,
              width: "100%",
              height: VERTICAL_LAYOUT.BOTTOM_BAND_HEIGHT,
              display: "flex",
              alignItems: "flex-start",
              justifyContent: "center",
              padding: "0 40px",
              boxSizing: "border-box",
              opacity: phraseOpacity,
              zIndex: 10,
            }
          : {
              position: "absolute",
              bottom: "8%",
              left: 0,
              right: 0,
              display: "flex",
              justifyContent: "center",
              opacity: phraseOpacity,
              zIndex: 10,
            }
      }
    >
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          gap: orientation === "vertical" ? "0 14px" : "0 8px",
          maxWidth: orientation === "vertical" ? "96%" : "80%",
          padding: orientation === "vertical" ? "16px 28px" : "8px 16px",
          borderRadius: orientation === "vertical" ? "10px" : "6px",
          backgroundColor: "rgba(0, 0, 0, 0.45)",
        }}
      >
        {activePhrase.words.map((w, i) => {
          const displayWord = formatSubtitleText(w.word);
          const wordStartFrame = Math.round((w.start_ms / 1000) * fps);
          const wordEndFrame = Math.round((w.end_ms / 1000) * fps);
          const isActive = highlightEnabled && frame >= wordStartFrame && frame <= wordEndFrame;

          if (!displayWord) return null;

          return (
            <span
              key={i}
              style={{
                fontSize: orientation === "vertical" ? "70px" : "32px",
                fontWeight: orientation === "vertical" ? 700 : 600,
                lineHeight: 1.25,
                color: isActive ? "#F59E0B" : "#fff",
                textShadow: isActive
                  ? "0 0 14px rgba(245, 158, 11, 0.45), 0 2px 10px rgba(0, 0, 0, 0.85)"
                  : "0 2px 10px rgba(0, 0, 0, 0.85)",
              }}
            >
              {displayWord}
            </span>
          );
        })}
      </div>
    </div>
  );
};
