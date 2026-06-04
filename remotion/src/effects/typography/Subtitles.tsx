/**
 * SubtitleOverlay — routed subtitle renderer timed to word_timestamps.
 */
import React, { useMemo } from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import type { CSSProperties } from "react";
import type { Orientation, SceneInput, SubtitleSettingsConfig, WordTimestamp } from "../../types";
import { VERTICAL_LAYOUT } from "../../scenes/VerticalSceneLayout";
import { formatSubtitleText } from "../../utils/subtitleText";
import {
  groupIntoSubtitlePhrases,
  isWordActive,
  resolveSubtitleStyle,
  type ResolvedSubtitleStyle,
  type SubtitlePhrase,
  wordProgress,
} from "./subtitleRouting";

interface Props {
  scene: SceneInput;
  highlightEnabled?: boolean;
  orientation?: Orientation;
  subtitleSettings?: SubtitleSettingsConfig | null;
}

interface TreatmentProps {
  phrase: SubtitlePhrase;
  frame: number;
  fps: number;
  highlightEnabled?: boolean;
  orientation: Orientation;
}

const FADE_OUT_FRAMES = 5;
const SUBTITLE_FONT_FAMILY = "Inter, Arial, sans-serif";

function overlayStyle(orientation: Orientation, phraseOpacity: number): CSSProperties {
  if (orientation === "vertical") {
    return {
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
    };
  }

  return {
    position: "absolute",
    bottom: "8%",
    left: 0,
    right: 0,
    display: "flex",
    justifyContent: "center",
    opacity: phraseOpacity,
    zIndex: 10,
  };
}

function wordsForDisplay(words: WordTimestamp[]): Array<{ word: WordTimestamp; displayWord: string }> {
  return words
    .map((word) => ({ word, displayWord: formatSubtitleText(word.word) }))
    .filter(({ displayWord }) => displayWord.length > 0);
}

function CleanSubtitleOverlay({ phrase, frame, fps, highlightEnabled, orientation }: TreatmentProps) {
  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        justifyContent: "center",
        gap: orientation === "vertical" ? "0 14px" : "0 8px",
        maxWidth: orientation === "vertical" ? "96%" : "80%",
        padding: orientation === "vertical" ? "16px 28px" : "8px 16px",
        borderRadius: orientation === "vertical" ? "10px" : "6px",
        backgroundColor: "rgba(0, 0, 0, 0.48)",
      }}
    >
      {wordsForDisplay(phrase.words).map(({ word, displayWord }, i) => {
        const isActive = highlightEnabled && isWordActive(word, frame, fps);
        const pop = isActive ? interpolate(wordProgress(word, frame, fps), [0, 0.35, 1], [1, 1.12, 1.06]) : 1;

        return (
          <span
            key={`${word.start_ms}-${i}`}
            style={{
              fontSize: orientation === "vertical" ? "70px" : "32px",
              fontWeight: orientation === "vertical" ? 800 : 700,
              lineHeight: 1.25,
              color: isActive ? "#FACC15" : "#fff",
              transform: `scale(${pop})`,
              transformOrigin: "center bottom",
              textShadow: isActive
                ? "0 0 18px rgba(250, 204, 21, 0.52), 0 3px 12px rgba(0, 0, 0, 0.9)"
                : "0 2px 10px rgba(0, 0, 0, 0.85)",
            }}
          >
            {displayWord}
          </span>
        );
      })}
    </div>
  );
}

function KineticSubtitleOverlay({ phrase, frame, fps, highlightEnabled, orientation }: TreatmentProps) {
  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        justifyContent: "center",
        gap: orientation === "vertical" ? "12px 14px" : "8px 10px",
        maxWidth: orientation === "vertical" ? "96%" : "82%",
      }}
    >
      {wordsForDisplay(phrase.words).map(({ word, displayWord }, i) => {
        const isActive = highlightEnabled && isWordActive(word, frame, fps);
        const entrance = interpolate(frame, [phrase.startFrame + i * 2, phrase.startFrame + i * 2 + 5], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        const pop = isActive ? interpolate(wordProgress(word, frame, fps), [0, 0.25, 1], [1, 1.18, 1.08]) : 1;

        return (
          <span
            key={`${word.start_ms}-${i}`}
            style={{
              display: "inline-block",
              padding: orientation === "vertical" ? "6px 12px" : "4px 9px",
              borderRadius: orientation === "vertical" ? "8px" : "5px",
              backgroundColor: isActive ? "#EF4444" : "#F8FAFC",
              color: isActive ? "#fff" : "#09090B",
              fontSize: orientation === "vertical" ? "62px" : "30px",
              fontWeight: 900,
              lineHeight: 1.05,
              opacity: entrance,
              transform: `translateY(${(1 - entrance) * 14 - (isActive ? 8 : 0)}px) rotate(${isActive ? 1.5 : 0}deg) scale(${pop})`,
              boxShadow: orientation === "vertical" ? "8px 9px 0 rgba(0,0,0,0.72)" : "5px 6px 0 rgba(0,0,0,0.78)",
              textShadow: isActive ? "0 2px 8px rgba(0,0,0,0.45)" : "none",
            }}
          >
            {displayWord}
          </span>
        );
      })}
    </div>
  );
}

function BurstSubtitleOverlay({ phrase, frame, fps, highlightEnabled, orientation }: TreatmentProps) {
  const displayWords = wordsForDisplay(phrase.words);
  const activeIndex = displayWords.findIndex(({ word }) => highlightEnabled && isWordActive(word, frame, fps));
  const burstIndex = activeIndex >= 0 ? activeIndex : Math.max(0, displayWords.length - 1);

  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        justifyContent: "center",
        alignItems: "baseline",
        gap: orientation === "vertical" ? "6px 16px" : "4px 10px",
        maxWidth: orientation === "vertical" ? "96%" : "82%",
      }}
    >
      {displayWords.map(({ word, displayWord }, i) => {
        const isBurst = i === burstIndex;
        const isActive = highlightEnabled && isWordActive(word, frame, fps);
        const pop = isBurst ? interpolate(wordProgress(word, frame, fps), [0, 0.3, 1], [0.92, 1.22, 1.08], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        }) : 1;

        return (
          <span
            key={`${word.start_ms}-${i}`}
            style={{
              display: "inline-block",
              color: isBurst ? "#FFD84D" : "#F4F4F5",
              fontFamily: SUBTITLE_FONT_FAMILY,
              fontSize: isBurst
                ? (orientation === "vertical" ? "76px" : "40px")
                : (orientation === "vertical" ? "62px" : "32px"),
              fontWeight: isBurst ? 900 : 850,
              lineHeight: 1.05,
              textTransform: "none",
              WebkitTextStroke: isBurst ? (orientation === "vertical" ? "2px #080808" : "1.5px #080808") : "0",
              transform: `scale(${pop}) translateY(${isActive && isBurst ? -5 : 0}px)`,
              transformOrigin: "center bottom",
              textShadow: isBurst
                ? "0 4px 0 #080808, 0 12px 24px rgba(0,0,0,0.72)"
                : "0 4px 12px rgba(0,0,0,0.9)",
            }}
          >
            {displayWord}
          </span>
        );
      })}
    </div>
  );
}

function renderTreatment(style: ResolvedSubtitleStyle, props: TreatmentProps) {
  if (style === "none") return null;
  if (style === "kinetic") return <KineticSubtitleOverlay {...props} />;
  if (style === "burst") return <BurstSubtitleOverlay {...props} />;
  return <CleanSubtitleOverlay {...props} />;
}

export const SubtitleOverlay: React.FC<Props> = ({ scene, highlightEnabled, orientation = "horizontal", subtitleSettings }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const wordTimestamps = scene.word_timestamps ?? [];

  const phrases = useMemo(
    () => groupIntoSubtitlePhrases(wordTimestamps, fps),
    [wordTimestamps, fps],
  );

  if (wordTimestamps.length === 0) return null;

  const activePhrase = phrases.find(
    (p) => frame >= p.startFrame && frame <= p.endFrame + FADE_OUT_FRAMES,
  );

  if (!activePhrase) return null;

  const phraseOver = frame > activePhrase.endFrame;
  const phraseOpacity = phraseOver
    ? interpolate(frame, [activePhrase.endFrame, activePhrase.endFrame + FADE_OUT_FRAMES], [1, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 1;

  if (phraseOpacity <= 0) return null;

  const style = resolveSubtitleStyle(scene, orientation, subtitleSettings);
  if (style === "none") return null;

  return (
    <div style={overlayStyle(orientation, phraseOpacity)}>
      {renderTreatment(style, {
        phrase: activePhrase,
        frame,
        fps,
        highlightEnabled,
        orientation,
      })}
    </div>
  );
};
