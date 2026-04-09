/**
 * CaptionOverlay — two-layer caption system.
 *
 * Layer 1 (BaseSubtitles): Running phrase subtitles timed to word_timestamps,
 *   with karaoke-style highlighting of the currently-spoken word.
 *   Only renders when word_timestamps data is available.
 *
 * Layer 2 (KineticEmphasis): Frame-timed emphasis words with per-word
 *   animation styles driven by fx.kinetic_captions.words.
 *
 * When a kinetic word overlaps a subtitle word, the subtitle word is
 * suppressed (hidden) to prevent double-rendering.
 */
import React, { useMemo } from "react";
import { useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";
import type { EmphasisWord, WordTimestamp } from "../../types";

interface Props {
  words: EmphasisWord[];
  wordTimestamps?: WordTimestamp[] | null;
}

const ACCENT_COLOR = "#a78bfa"; // violet-400
const FADE_OUT_FRAMES = 5;

// ─── Position styles for kinetic emphasis layer ─────────────────────

const POSITION_STYLES: Record<string, React.CSSProperties> = {
  bottom_center: { bottom: "15%", left: 0, right: 0, justifyContent: "center" },
  bottom_left: { bottom: "15%", left: "8%", right: "auto", justifyContent: "flex-start" },
  bottom_right: { bottom: "15%", left: "auto", right: "8%", justifyContent: "flex-end" },
  center: { top: "50%", left: 0, right: 0, justifyContent: "center", transform: "translateY(-50%)" },
  top_center: { top: "12%", left: 0, right: 0, justifyContent: "center" },
};

// ─── Phrase grouping for subtitle lines ─────────────────────────────

interface SubtitlePhrase {
  words: WordTimestamp[];
  indices: number[]; // original indices in the word_timestamps array
  startFrame: number;
  endFrame: number;
}

const MAX_WORDS_PER_LINE = 8;
const PAUSE_THRESHOLD_MS = 300;

function groupIntoPhrases(timestamps: WordTimestamp[], fps: number): SubtitlePhrase[] {
  if (timestamps.length === 0) return [];

  const phrases: SubtitlePhrase[] = [];
  let currentWords: WordTimestamp[] = [];
  let currentIndices: number[] = [];

  for (let i = 0; i < timestamps.length; i++) {
    const w = timestamps[i];
    currentWords.push(w);
    currentIndices.push(i);

    const isLast = i === timestamps.length - 1;
    const hitMax = currentWords.length >= MAX_WORDS_PER_LINE;
    const endsWithPunctuation = /[.!?]$/.test(w.word.trim());
    const longPauseAfter = !isLast && timestamps[i + 1].start_ms - w.end_ms > PAUSE_THRESHOLD_MS;

    if (isLast || hitMax || endsWithPunctuation || longPauseAfter) {
      const startMs = currentWords[0].start_ms;
      const endMs = currentWords[currentWords.length - 1].end_ms;
      phrases.push({
        words: [...currentWords],
        indices: [...currentIndices],
        startFrame: Math.round((startMs / 1000) * fps),
        endFrame: Math.round((endMs / 1000) * fps),
      });
      currentWords = [];
      currentIndices = [];
    }
  }

  return phrases;
}

// ─── Main component ─────────────────────────────────────────────────

export const CaptionOverlay: React.FC<Props> = ({ words, wordTimestamps }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Build suppression set: word_timestamp indices that overlap a kinetic word
  const suppressedIndices = useMemo(() => {
    if (!wordTimestamps || wordTimestamps.length === 0 || words.length === 0) {
      return new Set<number>();
    }
    return buildSuppressionSet(words, wordTimestamps);
  }, [words, wordTimestamps]);

  // Compute per-frame suppression (which indices are actively kinetic right now)
  const activeSuppressions = useMemo(() => {
    const active = new Set<number>();
    for (const w of words) {
      const localFrame = frame - w.start_frame;
      if (localFrame >= 0 && localFrame <= (w.end_frame - w.start_frame) + FADE_OUT_FRAMES) {
        // Find matching word_timestamp index
        const idx = w.word_index;
        if (idx != null && suppressedIndices.has(idx)) {
          active.add(idx);
        }
      }
    }
    return active;
  }, [frame, words, suppressedIndices]);

  const hasSubtitles = wordTimestamps && wordTimestamps.length > 0;
  const hasKinetic = words.length > 0;

  if (!hasSubtitles && !hasKinetic) return null;

  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
      }}
    >
      {/* Layer 1: Base subtitles */}
      {hasSubtitles && (
        <BaseSubtitles
          wordTimestamps={wordTimestamps}
          fps={fps}
          frame={frame}
          suppressedIndices={activeSuppressions}
        />
      )}

      {/* Layer 2: Kinetic emphasis */}
      {hasKinetic && (
        <div style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", zIndex: 11 }}>
          {words.map((w, i) => (
            <EmphasisWordRenderer key={i} word={w} frame={frame} fps={fps} />
          ))}
        </div>
      )}
    </div>
  );
};

// Keep old export name for backwards compatibility
export const KineticCaption = CaptionOverlay;

// ─── Suppression mapping ────────────────────────────────────────────

function buildSuppressionSet(
  emphasisWords: EmphasisWord[],
  timestamps: WordTimestamp[],
): Set<number> {
  const suppressed = new Set<number>();
  for (const ew of emphasisWords) {
    if (ew.word_index != null && ew.word_index < timestamps.length) {
      suppressed.add(ew.word_index);
    } else {
      // Fuzzy fallback: match by word text
      const normalized = ew.word.toLowerCase().replace(/[^a-z0-9]/g, "");
      const idx = timestamps.findIndex(
        (t) => t.word.toLowerCase().replace(/[^a-z0-9]/g, "") === normalized,
      );
      if (idx >= 0) suppressed.add(idx);
    }
  }
  return suppressed;
}

// ─── Layer 1: Base subtitle renderer ────────────────────────────────

interface BaseSubtitlesProps {
  wordTimestamps: WordTimestamp[];
  fps: number;
  frame: number;
  suppressedIndices: Set<number>;
}

const BaseSubtitles: React.FC<BaseSubtitlesProps> = ({
  wordTimestamps,
  fps,
  frame,
  suppressedIndices,
}) => {
  const phrases = useMemo(
    () => groupIntoPhrases(wordTimestamps, fps),
    [wordTimestamps, fps],
  );

  const currentTimeMs = (frame / fps) * 1000;

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
        {activePhrase.words.map((w, i) => {
          const globalIdx = activePhrase.indices[i];
          const isSuppressed = suppressedIndices.has(globalIdx);
          const isActive = currentTimeMs >= w.start_ms && currentTimeMs < w.end_ms;

          return (
            <span
              key={globalIdx}
              style={{
                fontSize: "32px",
                fontWeight: 600,
                lineHeight: 1.4,
                color: isSuppressed
                  ? "transparent"
                  : isActive
                    ? "#fff"
                    : "rgba(255, 255, 255, 0.5)",
                textShadow: isSuppressed
                  ? "none"
                  : "0 2px 8px rgba(0, 0, 0, 0.8)",
                transition: "color 0.08s ease",
              }}
            >
              {w.word}
            </span>
          );
        })}
      </div>
    </div>
  );
};

// ─── Layer 2: Kinetic emphasis renderer ─────────────────────────────

interface WordRendererProps {
  word: EmphasisWord;
  frame: number;
  fps: number;
}

const EmphasisWordRenderer: React.FC<WordRendererProps> = ({ word, frame, fps }) => {
  const localFrame = frame - word.start_frame;
  const duration = word.end_frame - word.start_frame;

  if (localFrame < 0 || localFrame > duration + FADE_OUT_FRAMES) return null;

  const fadeOut = localFrame > duration
    ? interpolate(localFrame, [duration, duration + FADE_OUT_FRAMES], [1, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 1;

  if (fadeOut <= 0) return null;

  const intensity = word.intensity ?? 2;
  const result = renderStyle(word.style, localFrame, fps, word.word, intensity);
  const fontSize = word.font_size ?? 64;
  const position = word.position ?? "bottom_center";
  const posStyle = POSITION_STYLES[position] ?? POSITION_STYLES.bottom_center;

  return (
    <div
      style={{
        position: "absolute",
        display: "flex",
        alignItems: "center",
        opacity: fadeOut,
        ...posStyle,
      }}
    >
      <span
        style={{
          fontSize: `${fontSize}px`,
          fontWeight: 800,
          color: "#fff",
          textShadow: "0 4px 16px rgba(0,0,0,0.9), 0 2px 4px rgba(0,0,0,0.5)",
          textTransform: "uppercase",
          letterSpacing: "0.02em",
          ...result.style,
        }}
      >
        {result.displayText ?? word.word}
      </span>
    </div>
  );
};

// ─── Animation styles ───────────────────────────────────────────────

interface StyleResult {
  style: React.CSSProperties;
  displayText?: string;
}

// Intensity multiplier: 1 = subtle, 2 = standard, 3 = max impact
function intensityScale(intensity: number, low: number, mid: number, high: number): number {
  if (intensity <= 1) return low;
  if (intensity >= 3) return high;
  return mid;
}

function renderStyle(
  style: string,
  localFrame: number,
  fps: number,
  fullText: string,
  intensity: number,
): StyleResult {
  switch (style) {
    case "scale_pop": {
      const overshoot = intensityScale(intensity, 0.1, 0.2, 0.35);
      const s = spring({
        frame: localFrame,
        fps,
        config: {
          damping: intensityScale(intensity, 18, 12, 6),
          mass: 0.5,
          stiffness: 200,
        },
      });
      return {
        style: {
          transform: `scale(${0.8 + s * overshoot + (1 - overshoot)})`,
          display: "inline-block",
        },
      };
    }
    case "color_flash": {
      const flashDuration = intensityScale(intensity, 1, 2, 5);
      const isFlash = localFrame < flashDuration;
      const glowSize = intensityScale(intensity, 10, 20, 40);
      return {
        style: {
          color: isFlash ? ACCENT_COLOR : "#fff",
          textShadow: isFlash
            ? `0 0 ${glowSize}px ${ACCENT_COLOR}, 0 4px 16px rgba(0,0,0,0.9)`
            : "0 4px 16px rgba(0,0,0,0.9), 0 2px 4px rgba(0,0,0,0.5)",
        },
      };
    }
    case "size_burst": {
      const burstFrames = intensityScale(intensity, 10, 15, 20);
      const startScale = intensityScale(intensity, 2, 3, 5);
      const scale = localFrame < burstFrames
        ? interpolate(localFrame, [0, burstFrames], [startScale, 1], {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          })
        : 1;
      return {
        style: {
          transform: `scale(${scale})`,
          display: "inline-block",
        },
      };
    }
    case "shake": {
      const shakeFrames = intensityScale(intensity, 6, 10, 16);
      const magnitude = intensityScale(intensity, 1, 2, 4);
      if (localFrame < shakeFrames) {
        const offsetX = Math.sin(localFrame * 7) * magnitude;
        const offsetY = Math.cos(localFrame * 5) * magnitude;
        return {
          style: {
            transform: `translate(${offsetX}px, ${offsetY}px)`,
            display: "inline-block",
          },
        };
      }
      return { style: {} };
    }
    case "underline_draw": {
      const drawDuration = intensityScale(intensity, 20, 15, 8);
      const progress = Math.min(1, localFrame / drawDuration);
      const thickness = intensityScale(intensity, 3, 4, 6);
      return {
        style: {
          borderBottom: `${thickness}px solid #fff`,
          paddingBottom: "4px",
          backgroundImage: "linear-gradient(#fff, #fff)",
          backgroundSize: `${progress * 100}% ${thickness}px`,
          backgroundPosition: "left bottom",
          backgroundRepeat: "no-repeat",
          borderBottomColor: "transparent",
        },
      };
    }
    case "glow_pulse": {
      const pulseSpeed = intensityScale(intensity, 0.3, 0.6, 1.0);
      const maxBlur = intensityScale(intensity, 12, 24, 40);
      const maxSpread = intensityScale(intensity, 4, 12, 20);
      const pulsePhase = Math.sin(localFrame * pulseSpeed) * 0.5 + 0.5;
      const blurRadius = 8 + pulsePhase * maxBlur;
      const spreadRadius = 4 + pulsePhase * maxSpread;
      return {
        style: {
          color: ACCENT_COLOR,
          textShadow: `0 0 ${blurRadius}px ${ACCENT_COLOR}, 0 0 ${spreadRadius}px ${ACCENT_COLOR}, 0 4px 16px rgba(0,0,0,0.9)`,
        },
      };
    }
    case "typewriter": {
      const revealFrames = intensityScale(intensity, 18, 12, 6);
      const charsPerFrame = fullText.length / revealFrames;
      const visibleChars = Math.min(fullText.length, Math.floor(localFrame * charsPerFrame) + 1);
      return {
        style: {
          fontFamily: "'Courier New', monospace",
        },
        displayText: fullText.slice(0, visibleChars),
      };
    }
    case "slide_up": {
      const distance = intensityScale(intensity, 30, 60, 100);
      const s = spring({
        frame: localFrame,
        fps,
        config: {
          damping: intensityScale(intensity, 18, 14, 8),
          mass: 0.8,
          stiffness: 180,
        },
      });
      const translateY = interpolate(s, [0, 1], [distance, 0]);
      return {
        style: {
          transform: `translateY(${translateY}px)`,
          display: "inline-block",
        },
      };
    }
    case "bounce_in": {
      const distance = intensityScale(intensity, -40, -80, -140);
      const s = spring({
        frame: localFrame,
        fps,
        config: {
          damping: intensityScale(intensity, 10, 6, 3),
          mass: 0.6,
          stiffness: 200,
        },
      });
      const translateY = interpolate(s, [0, 1], [distance, 0]);
      return {
        style: {
          transform: `translateY(${translateY}px)`,
          display: "inline-block",
        },
      };
    }
    case "rotate_in": {
      const rotation = intensityScale(intensity, -8, -15, -25);
      const startScale = intensityScale(intensity, 0.85, 0.7, 0.5);
      const s = spring({
        frame: localFrame,
        fps,
        config: {
          damping: intensityScale(intensity, 16, 12, 6),
          mass: 0.5,
          stiffness: 180,
        },
      });
      const rot = interpolate(s, [0, 1], [rotation, 0]);
      const scale = interpolate(s, [0, 1], [startScale, 1]);
      return {
        style: {
          transform: `rotate(${rot}deg) scale(${scale})`,
          display: "inline-block",
          transformOrigin: "center center",
        },
      };
    }
    case "glitch": {
      const glitchFrames = intensityScale(intensity, 5, 8, 14);
      const magnitude = intensityScale(intensity, 1.5, 3, 6);
      const rgbMagnitude = intensityScale(intensity, 1, 2, 4);
      if (localFrame < glitchFrames) {
        const offsetX = Math.sin(localFrame * 13) * magnitude;
        const offsetY = Math.cos(localFrame * 9) * (magnitude * 0.66);
        const rgbShift = Math.floor(localFrame * rgbMagnitude) + 2;
        return {
          style: {
            transform: `translate(${offsetX}px, ${offsetY}px)`,
            display: "inline-block",
            textShadow: `${rgbShift}px 0 #ff0040, ${-rgbShift}px 0 #00ff88, 0 4px 16px rgba(0,0,0,0.9)`,
          },
        };
      }
      return { style: {} };
    }
    case "gradient_sweep": {
      const sweepFrames = intensityScale(intensity, 30, 20, 12);
      const sweepProgress = Math.min(1, localFrame / sweepFrames);
      const gradientPos = sweepProgress * 200 - 50;
      return {
        style: {
          background: `linear-gradient(90deg, #fff ${gradientPos - 30}%, ${ACCENT_COLOR} ${gradientPos}%, #38bdf8 ${gradientPos + 30}%, #fff ${gradientPos + 60}%)`,
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          backgroundClip: "text",
          display: "inline-block",
          textShadow: "none",
        },
      };
    }
    default:
      return { style: {} };
  }
}
