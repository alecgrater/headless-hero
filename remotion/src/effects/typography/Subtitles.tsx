/**
 * SubtitleOverlay — routed subtitle renderer timed to word_timestamps.
 *
 * Two styles only. `clean` is the default and carries a translucent plate; `kinetic` is
 * the short-punch-beat exception and shares clean's type spine exactly, differing only in
 * behaviour (larger, no plate, staggered entrance, harder pop).
 *
 * INVARIANT: per-word emphasis is expressed through `transform` and `color` only — never
 * through `fontSize` or `fontWeight`. A size or weight change reflows the line as the
 * active word moves, which is the defect that made the deleted `burst` style unusable.
 */
import React, { useMemo } from "react";
import { interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { loadFont } from "@remotion/google-fonts/Inter";
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

const { fontFamily: SUBTITLE_FONT_FAMILY } = loadFont("normal", {
  weights: ["800"],
  subsets: ["latin"],
});

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

/** Base type size. 52px on a 1080p frame is 4.8% of frame height, inside the 4-5% norm
 *  for burned-in captions. Vertical derives from the same base rather than a literal. */
const BASE_FONT_SIZE = 52;
const VERTICAL_FONT_SCALE = 1.35;
/** Kinetic runs larger than clean — it is reserved for two-to-six word punch beats. */
const KINETIC_FONT_SCALE = 1.25;
const ACCENT_COLOR = "#FACC15";
const TEXT_SHADOW = "0 2px 4px rgba(0, 0, 0, 0.55), 0 6px 22px rgba(0, 0, 0, 0.72)";

function baseFontSize(orientation: Orientation): number {
  return orientation === "vertical" ? Math.round(BASE_FONT_SIZE * VERTICAL_FONT_SCALE) : BASE_FONT_SIZE;
}

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

/** Shared by both styles so they can never drift apart typographically. */
function wordTypography(fontSize: number): CSSProperties {
  return {
    display: "inline-block",
    fontFamily: SUBTITLE_FONT_FAMILY,
    fontSize,
    fontWeight: 800,
    lineHeight: 1.2,
    letterSpacing: "-0.012em",
  };
}

function CleanSubtitleOverlay({ phrase, frame, fps, highlightEnabled, orientation }: TreatmentProps) {
  const fontSize = baseFontSize(orientation);

  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        justifyContent: "center",
        alignItems: "baseline",
        gap: `${Math.round(fontSize * 0.12)}px ${Math.round(fontSize * 0.28)}px`,
        maxWidth: orientation === "vertical" ? "94%" : "80%",
        padding: `${Math.round(fontSize * 0.3)}px ${Math.round(fontSize * 0.58)}px`,
        borderRadius: Math.round(fontSize * 0.22),
        backgroundColor: "rgba(0, 0, 0, 0.52)",
        textAlign: "center",
      }}
    >
      {wordsForDisplay(phrase.words).map(({ word, displayWord }, i) => {
        const isActive = highlightEnabled && isWordActive(word, frame, fps);
        // transform-only pop: scaling does not reflow siblings.
        const pop = isActive ? interpolate(wordProgress(word, frame, fps), [0, 0.35, 1], [1, 1.07, 1.04]) : 1;

        return (
          <span
            key={`${word.start_ms}-${i}`}
            style={{
              ...wordTypography(fontSize),
              color: isActive ? ACCENT_COLOR : "#fff",
              transform: `scale(${pop})`,
              transformOrigin: "center bottom",
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
  const fontSize = Math.round(baseFontSize(orientation) * KINETIC_FONT_SCALE);
  const fpms = fps / 1000;

  return (
    <div
      style={{
        display: "flex",
        flexWrap: "wrap",
        justifyContent: "center",
        alignItems: "baseline",
        gap: `${Math.round(fontSize * 0.1)}px ${Math.round(fontSize * 0.26)}px`,
        maxWidth: orientation === "vertical" ? "94%" : "84%",
        textAlign: "center",
      }}
    >
      {wordsForDisplay(phrase.words).map(({ word, displayWord }, i) => {
        const isActive = highlightEnabled && isWordActive(word, frame, fps);
        // Words stagger in on their own start time, so the line assembles as it is spoken.
        const wordStartFrame = Math.round(word.start_ms * fpms);
        const entrance = interpolate(frame, [wordStartFrame, wordStartFrame + Math.max(1, Math.round(fps * 0.12))], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        const pop = isActive ? interpolate(wordProgress(word, frame, fps), [0, 0.22, 1], [1, 1.14, 1.06]) : 1;

        return (
          <span
            key={`${word.start_ms}-${i}`}
            style={{
              ...wordTypography(fontSize),
              // Tighter tracking than clean; size/weight stay uniform across the phrase.
              letterSpacing: "-0.02em",
              color: isActive ? ACCENT_COLOR : "#fff",
              opacity: entrance,
              transform: `translateY(${(1 - entrance) * 18}px) scale(${pop})`,
              transformOrigin: "center bottom",
              textShadow: TEXT_SHADOW,
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
