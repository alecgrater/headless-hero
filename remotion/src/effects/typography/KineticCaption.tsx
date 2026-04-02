/**
 * KineticCaption — frame-timed emphasis words from narration.
 * Each word renders independently at its start_frame→end_frame with a per-word style.
 * One word visible at a time (not full subtitles).
 */
import React from "react";
import { useCurrentFrame, useVideoConfig, spring, interpolate } from "remotion";
import type { EmphasisWord } from "../../types";

interface Props {
  words: EmphasisWord[];
}

const ACCENT_COLOR = "#a78bfa"; // violet-400
const FADE_OUT_FRAMES = 5;

const POSITION_STYLES: Record<string, React.CSSProperties> = {
  bottom_center: { bottom: "15%", left: 0, right: 0, justifyContent: "center" },
  bottom_left: { bottom: "15%", left: "8%", right: "auto", justifyContent: "flex-start" },
  bottom_right: { bottom: "15%", left: "auto", right: "8%", justifyContent: "flex-end" },
  center: { top: "50%", left: 0, right: 0, justifyContent: "center", transform: "translateY(-50%)" },
  top_center: { top: "12%", left: 0, right: 0, justifyContent: "center" },
};

export const KineticCaption: React.FC<Props> = ({ words }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  return (
    <div
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "none",
        zIndex: 10,
      }}
    >
      {words.map((w, i) => (
        <EmphasisWordRenderer key={i} word={w} frame={frame} fps={fps} />
      ))}
    </div>
  );
};

interface WordRendererProps {
  word: EmphasisWord;
  frame: number;
  fps: number;
}

const EmphasisWordRenderer: React.FC<WordRendererProps> = ({ word, frame, fps }) => {
  const localFrame = frame - word.start_frame;
  const duration = word.end_frame - word.start_frame;

  // Not yet visible or fully faded out
  if (localFrame < 0 || localFrame > duration + FADE_OUT_FRAMES) return null;

  // Fade out after end_frame
  const fadeOut = localFrame > duration
    ? interpolate(localFrame, [duration, duration + FADE_OUT_FRAMES], [1, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 1;

  if (fadeOut <= 0) return null;

  const result = renderStyle(word.style, localFrame, fps, word.word);
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

interface StyleResult {
  style: React.CSSProperties;
  displayText?: string;
}

function renderStyle(
  style: string,
  localFrame: number,
  fps: number,
  fullText: string,
): StyleResult {
  switch (style) {
    case "scale_pop": {
      const s = spring({
        frame: localFrame,
        fps,
        config: { damping: 12, mass: 0.5, stiffness: 200 },
      });
      return {
        style: {
          transform: `scale(${0.8 + s * 0.2})`,
          display: "inline-block",
        },
      };
    }
    case "color_flash": {
      const isFlash = localFrame === 0;
      return {
        style: {
          color: isFlash ? ACCENT_COLOR : "#fff",
          textShadow: isFlash
            ? `0 0 20px ${ACCENT_COLOR}, 0 4px 16px rgba(0,0,0,0.9)`
            : "0 4px 16px rgba(0,0,0,0.9), 0 2px 4px rgba(0,0,0,0.5)",
        },
      };
    }
    case "size_burst": {
      const burstFrames = 15;
      const scale = localFrame < burstFrames
        ? interpolate(localFrame, [0, burstFrames], [3, 1], {
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
      const shakeFrames = 10;
      if (localFrame < shakeFrames) {
        const offsetX = Math.sin(localFrame * 7) * 2;
        const offsetY = Math.cos(localFrame * 5) * 2;
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
      const drawDuration = 15;
      const progress = Math.min(1, localFrame / drawDuration);
      return {
        style: {
          borderBottom: "4px solid #fff",
          paddingBottom: "4px",
          backgroundImage: `linear-gradient(#fff, #fff)`,
          backgroundSize: `${progress * 100}% 4px`,
          backgroundPosition: "left bottom",
          backgroundRepeat: "no-repeat",
          borderBottomColor: "transparent",
        },
      };
    }
    case "glow_pulse": {
      // Neon glow that pulses 2-3x via animated text-shadow blur
      const pulsePhase = Math.sin(localFrame * 0.6) * 0.5 + 0.5; // 0→1 oscillation
      const blurRadius = 8 + pulsePhase * 16;
      const spreadRadius = 4 + pulsePhase * 8;
      return {
        style: {
          color: ACCENT_COLOR,
          textShadow: `0 0 ${blurRadius}px ${ACCENT_COLOR}, 0 0 ${spreadRadius}px ${ACCENT_COLOR}, 0 4px 16px rgba(0,0,0,0.9)`,
        },
      };
    }
    case "typewriter": {
      // Characters revealed one at a time left-to-right
      const charsPerFrame = fullText.length / 12; // reveal over ~12 frames
      const visibleChars = Math.min(fullText.length, Math.floor(localFrame * charsPerFrame) + 1);
      return {
        style: {
          fontFamily: "'Courier New', monospace",
        },
        displayText: fullText.slice(0, visibleChars),
      };
    }
    case "slide_up": {
      const s = spring({
        frame: localFrame,
        fps,
        config: { damping: 14, mass: 0.8, stiffness: 180 },
      });
      const translateY = interpolate(s, [0, 1], [60, 0]);
      return {
        style: {
          transform: `translateY(${translateY}px)`,
          display: "inline-block",
        },
      };
    }
    case "bounce_in": {
      // Drops from above with bouncy spring (low damping)
      const s = spring({
        frame: localFrame,
        fps,
        config: { damping: 6, mass: 0.6, stiffness: 200 },
      });
      const translateY = interpolate(s, [0, 1], [-80, 0]);
      return {
        style: {
          transform: `translateY(${translateY}px)`,
          display: "inline-block",
        },
      };
    }
    case "rotate_in": {
      const s = spring({
        frame: localFrame,
        fps,
        config: { damping: 12, mass: 0.5, stiffness: 180 },
      });
      const rotation = interpolate(s, [0, 1], [-15, 0]);
      const scale = interpolate(s, [0, 1], [0.7, 1]);
      return {
        style: {
          transform: `rotate(${rotation}deg) scale(${scale})`,
          display: "inline-block",
          transformOrigin: "center center",
        },
      };
    }
    case "glitch": {
      // RGB split + position jitter for ~8 frames, then clean
      const glitchFrames = 8;
      if (localFrame < glitchFrames) {
        const offsetX = Math.sin(localFrame * 13) * 3;
        const offsetY = Math.cos(localFrame * 9) * 2;
        const rgbShift = Math.floor(localFrame * 1.5) + 2;
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
      // Color gradient sweeps across word via background-clip: text
      const sweepProgress = Math.min(1, localFrame / 20);
      const gradientPos = sweepProgress * 200 - 50; // -50% → 150%
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
