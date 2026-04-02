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

  const style = renderStyle(word.style, localFrame, fps);

  return (
    <div
      style={{
        position: "absolute",
        bottom: "15%",
        left: 0,
        right: 0,
        display: "flex",
        justifyContent: "center",
        alignItems: "center",
        opacity: fadeOut,
      }}
    >
      <span
        style={{
          fontSize: "64px",
          fontWeight: 800,
          color: "#fff",
          textShadow: "0 4px 16px rgba(0,0,0,0.9), 0 2px 4px rgba(0,0,0,0.5)",
          textTransform: "uppercase",
          letterSpacing: "0.02em",
          ...style,
        }}
      >
        {word.word}
      </span>
    </div>
  );
};

function renderStyle(
  style: string,
  localFrame: number,
  fps: number,
): React.CSSProperties {
  switch (style) {
    case "scale_pop": {
      const s = spring({
        frame: localFrame,
        fps,
        config: { damping: 12, mass: 0.5, stiffness: 200 },
      });
      return {
        transform: `scale(${0.8 + s * 0.2})`,
        display: "inline-block",
      };
    }
    case "color_flash": {
      const isFlash = localFrame === 0;
      return {
        color: isFlash ? ACCENT_COLOR : "#fff",
        textShadow: isFlash
          ? `0 0 20px ${ACCENT_COLOR}, 0 4px 16px rgba(0,0,0,0.9)`
          : "0 4px 16px rgba(0,0,0,0.9), 0 2px 4px rgba(0,0,0,0.5)",
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
        transform: `scale(${scale})`,
        display: "inline-block",
      };
    }
    case "shake": {
      const shakeFrames = 10;
      if (localFrame < shakeFrames) {
        const offsetX = Math.sin(localFrame * 7) * 2;
        const offsetY = Math.cos(localFrame * 5) * 2;
        return {
          transform: `translate(${offsetX}px, ${offsetY}px)`,
          display: "inline-block",
        };
      }
      return {};
    }
    case "underline_draw": {
      const drawDuration = 15;
      const progress = Math.min(1, localFrame / drawDuration);
      return {
        borderBottom: "4px solid #fff",
        paddingBottom: "4px",
        backgroundImage: `linear-gradient(#fff, #fff)`,
        backgroundSize: `${progress * 100}% 4px`,
        backgroundPosition: "left bottom",
        backgroundRepeat: "no-repeat",
        borderBottomColor: "transparent",
      };
    }
    default:
      return {};
  }
}
