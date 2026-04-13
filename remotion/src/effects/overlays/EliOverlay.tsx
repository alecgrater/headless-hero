/**
 * EliOverlay — Renders the Eli character overlay in the bottom-right corner.
 *
 * Selects which pose frame to show based on animation keyframes from Claude.
 * Mouth state (open/closed) is determined from word_timestamps — open when
 * a word is being spoken, closed during gaps > 200ms.
 */
import React from "react";
import { useCurrentFrame, useVideoConfig, Img } from "remotion";
import type { EliOverlay as EliOverlayType, EliKeyframe, WordTimestamp } from "../../types";

/** Simple string hash for deterministic pseudo-random seeding. */
function hashCode(s: string): number {
  let hash = 0;
  for (let i = 0; i < s.length; i++) {
    hash = ((hash << 5) - hash + s.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

/**
 * Build a pseudo-random variant sequence from a seed.
 * Creates an 8-12 item sequence that's mostly sequential but occasionally
 * repeats or skips for an organic, not-perfectly-predictable feel.
 */
function buildVariantSequence(seed: number, variantCount: number): number[] {
  const seqLength = 8 + (seed % 5); // 8-12 items
  const sequence: number[] = [];
  let rng = seed;

  for (let i = 0; i < seqLength; i++) {
    // Simple LCG for deterministic pseudo-random
    rng = (rng * 1664525 + 1013904223) & 0x7fffffff;
    const variant = (rng % variantCount) + 1; // 1-based variant number
    sequence.push(variant);
  }

  return sequence;
}

/**
 * Determine which variant to show at a given frame within a keyframe.
 * Cycles through variants every ~6 frames (~200ms at 30fps) using a
 * seeded pseudo-random sequence for organic feel.
 */
function getVariant(
  frame: number,
  keyframe: EliKeyframe,
  variantCount: number,
): number {
  if (variantCount <= 1) return 1;

  const cycleLength = 6; // frames per variant hold (~200ms at 30fps)
  const seed = hashCode(keyframe.frame_id + String(keyframe.start_frame));
  const sequence = buildVariantSequence(seed, variantCount);
  const cycleIndex = Math.floor((frame - keyframe.start_frame) / cycleLength);
  return sequence[cycleIndex % sequence.length];
}

interface Props {
  overlay: EliOverlayType;
  wordTimestamps?: WordTimestamp[] | null;
  characterFramesBaseUrl: string;
  variantCounts?: Record<string, number> | null;
}

function isSpeaking(
  frame: number,
  fps: number,
  wordTimestamps: WordTimestamp[] | null | undefined,
): boolean {
  if (!wordTimestamps || wordTimestamps.length === 0) return false;
  const timeMs = (frame / fps) * 1000;
  // Mouth is open if we're within any word's time range (with 50ms grace for natural feel)
  for (const ts of wordTimestamps) {
    if (timeMs >= ts.start_ms - 50 && timeMs <= ts.end_ms + 50) {
      return true;
    }
  }
  return false;
}

function getCurrentKeyframe(
  frame: number,
  keyframes: EliKeyframe[],
): { current: EliKeyframe; next: EliKeyframe | null; transitionProgress: number } | null {
  if (keyframes.length === 0) return null;

  for (let i = 0; i < keyframes.length; i++) {
    const kf = keyframes[i];
    if (frame >= kf.start_frame && frame < kf.end_frame) {
      const nextKf = i + 1 < keyframes.length ? keyframes[i + 1] : null;

      // Check if we're in a crossfade transition zone (last 6 frames of keyframe)
      const CROSSFADE_FRAMES = 6; // ~200ms at 30fps
      let transitionProgress = 0;
      if (nextKf && nextKf.transition === "crossfade") {
        const transitionStart = kf.end_frame - CROSSFADE_FRAMES;
        if (frame >= transitionStart) {
          transitionProgress = (frame - transitionStart) / CROSSFADE_FRAMES;
        }
      }

      return { current: kf, next: nextKf, transitionProgress };
    }
  }

  // Fallback to last keyframe
  return { current: keyframes[keyframes.length - 1], next: null, transitionProgress: 0 };
}

export const EliOverlay: React.FC<Props> = ({
  overlay,
  wordTimestamps,
  characterFramesBaseUrl,
  variantCounts,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (!overlay.enabled || overlay.keyframes.length === 0) return null;

  const kfState = getCurrentKeyframe(frame, overlay.keyframes);
  if (!kfState) return null;

  const { current, next, transitionProgress } = kfState;
  const speaking = isSpeaking(frame, fps, wordTimestamps);
  const mouthSuffix = speaking ? "open" : "closed";

  // Variant cycling for current keyframe
  const currentVariantCount = variantCounts?.[current.frame_id] ?? 1;
  const currentVariant = getVariant(frame, current, currentVariantCount);
  const currentVariantSuffix = currentVariant === 1 ? "" : `_v${currentVariant}`;
  const currentSrc = `${characterFramesBaseUrl}/${current.frame_id}${currentVariantSuffix}_${mouthSuffix}.png`;

  // Variant cycling for next keyframe (during crossfade)
  let nextSrc: string | null = null;
  if (next && transitionProgress > 0) {
    const nextVariantCount = variantCounts?.[next.frame_id] ?? 1;
    const nextVariant = getVariant(frame, next, nextVariantCount);
    const nextVariantSuffix = nextVariant === 1 ? "" : `_v${nextVariant}`;
    nextSrc = `${characterFramesBaseUrl}/${next.frame_id}${nextVariantSuffix}_${mouthSuffix}.png`;
  }

  // Subtle breathing animation: sinusoidal Y translate ~2px at ~0.5Hz
  const breathY = Math.sin((frame / fps) * Math.PI) * 2;

  // Container size: 16:9 aspect ratio, ~25% of frame width
  const containerWidth = 480; // 25% of 1920
  const containerHeight = 270; // 16:9 ratio

  // Position: use overlay.position if provided, otherwise default (bottom-right)
  const posX = overlay.position?.x ?? 1410; // 1920 - 480 - 30
  const posY = overlay.position?.y ?? 720;  // 1080 - 270 - 90

  return (
    <div
      style={{
        position: "absolute",
        left: posX,
        top: posY,
        width: containerWidth,
        height: containerHeight,
        zIndex: 5,
        pointerEvents: "none",
        transform: `translateY(${breathY}px)`,
        borderRadius: 14,
        overflow: "hidden",
        border: "2px solid rgba(0, 220, 220, 0.6)",
        boxShadow:
          "0 0 20px rgba(0, 200, 200, 0.4), 0 0 40px rgba(0, 200, 200, 0.15)",
      }}
    >
      {/* Main character frame */}
      <div
        style={{
          width: "100%",
          height: "100%",
          position: "relative",
        }}
      >
        <Img
          src={currentSrc}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            opacity: transitionProgress > 0 ? 1 - transitionProgress : 1,
          }}
        />

        {/* Crossfade next frame */}
        {nextSrc && transitionProgress > 0 && (
          <Img
            src={nextSrc}
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              objectFit: "cover",
              opacity: transitionProgress,
            }}
          />
        )}
      </div>
    </div>
  );
};
