/**
 * SubtitleOverlay — phrase-based subtitle renderer timed to word_timestamps.
 *
 * Groups words into natural phrases (by punctuation, pauses, or max-length),
 * displays the active phrase with a semi-transparent background bar,
 * and fades out after each phrase ends.
 */
import React, { useMemo } from "react";
import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";
import type { WordTimestamp } from "../../types";

interface Props {
  wordTimestamps?: WordTimestamp[] | null;
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

export const SubtitleOverlay: React.FC<Props> = ({ wordTimestamps }) => {
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
      style={{
        position: "absolute",
        bottom: "8%",
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        opacity: phraseOpacity,
        zIndex: 10,
      }}
    >
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          gap: "0 8px",
          maxWidth: "80%",
          padding: "8px 16px",
          borderRadius: "6px",
          backgroundColor: "rgba(0, 0, 0, 0.45)",
        }}
      >
        {activePhrase.words.map((w, i) => (
          <span
            key={i}
            style={{
              fontSize: "32px",
              fontWeight: 600,
              lineHeight: 1.4,
              color: "#fff",
              textShadow: "0 2px 8px rgba(0, 0, 0, 0.8)",
            }}
          >
            {w.word}
          </span>
        ))}
      </div>
    </div>
  );
};
