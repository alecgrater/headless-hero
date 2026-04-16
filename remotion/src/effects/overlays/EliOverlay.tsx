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

/** Variant cycle length in frames (~3s at 30fps). */
const VARIANT_CYCLE_FRAMES = 90;

/** Fraction of the cycle spent crossfading between variants (last 20%). */
const VARIANT_BLEND_FRACTION = 0.2;

interface VariantBlend {
  currentVariant: number;
  nextVariant: number;
  blendProgress: number; // 0 = fully current, 1 = fully next
}

/**
 * Determine which variant(s) to show at a given frame within a keyframe.
 * Returns a blend between two variants — cycles every ~90 frames (~3s)
 * with a smooth crossfade over the last 20% of each cycle.
 *
 * When `frozen` is true (during pose crossfade), variant cycling is
 * paused and only the current variant is returned with no blend.
 */
function getVariantBlend(
  frame: number,
  keyframe: EliKeyframe,
  variantCount: number,
  frozen: boolean,
): VariantBlend {
  if (variantCount <= 1) return { currentVariant: 1, nextVariant: 1, blendProgress: 0 };

  const seed = hashCode(keyframe.frame_id + String(keyframe.start_frame));
  const sequence = buildVariantSequence(seed, variantCount);
  const elapsed = Math.max(0, frame - keyframe.start_frame);
  const cycleIndex = Math.floor(elapsed / VARIANT_CYCLE_FRAMES);
  const currentVariant = sequence[cycleIndex % sequence.length];

  if (frozen) {
    return { currentVariant, nextVariant: currentVariant, blendProgress: 0 };
  }

  const nextVariant = sequence[(cycleIndex + 1) % sequence.length];
  const posInCycle = (elapsed % VARIANT_CYCLE_FRAMES) / VARIANT_CYCLE_FRAMES;
  const blendStart = 1 - VARIANT_BLEND_FRACTION;

  let blendProgress = 0;
  if (posInCycle >= blendStart) {
    blendProgress = (posInCycle - blendStart) / VARIANT_BLEND_FRACTION;
  }

  return { currentVariant, nextVariant, blendProgress };
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

      // Check if we're in a crossfade transition zone (last 15 frames of keyframe)
      const CROSSFADE_FRAMES = 15; // ~500ms at 30fps
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

  if (!overlay.enabled || (overlay.keyframes ?? []).length === 0) return null;

  const kfState = getCurrentKeyframe(frame, overlay.keyframes ?? []);
  if (!kfState) return null;

  const { current, next, transitionProgress } = kfState;
  const speaking = isSpeaking(frame, fps, wordTimestamps);
  const mouthSuffix = speaking ? "open" : "closed";

  // Freeze variant cycling during pose crossfade to avoid compounding blends
  const variantFrozen = transitionProgress > 0;

  // Variant blend for current keyframe
  const currentVariantCount = variantCounts?.[current.frame_id] ?? 1;
  const currentBlend = getVariantBlend(frame, current, currentVariantCount, variantFrozen);

  const currentV1Suffix = currentBlend.currentVariant === 1 ? "" : `_v${currentBlend.currentVariant}`;
  const currentV1Src = `${characterFramesBaseUrl}/${current.frame_id}${currentV1Suffix}_${mouthSuffix}.png`;

  let currentV2Src: string | null = null;
  if (currentBlend.blendProgress > 0 && currentBlend.currentVariant !== currentBlend.nextVariant) {
    const currentV2Suffix = currentBlend.nextVariant === 1 ? "" : `_v${currentBlend.nextVariant}`;
    currentV2Src = `${characterFramesBaseUrl}/${current.frame_id}${currentV2Suffix}_${mouthSuffix}.png`;
  }

  // Next pose frame (during pose crossfade)
  let nextSrc: string | null = null;
  if (next && transitionProgress > 0) {
    const nextVariantCount = variantCounts?.[next.frame_id] ?? 1;
    const nextBlend = getVariantBlend(frame, next, nextVariantCount, true); // frozen — just pick one variant
    const nextVariantSuffix = nextBlend.currentVariant === 1 ? "" : `_v${nextBlend.currentVariant}`;
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
      {/* Main character frame with variant blending */}
      <div
        style={{
          width: "100%",
          height: "100%",
          position: "relative",
        }}
      >
        {/* Current variant layer A */}
        <Img
          src={currentV1Src}
          style={{
            width: "100%",
            height: "100%",
            objectFit: "cover",
            opacity: transitionProgress > 0
              ? 1 - transitionProgress
              : currentV2Src
                ? 1 - currentBlend.blendProgress
                : 1,
          }}
        />

        {/* Current variant layer B (variant crossfade) */}
        {currentV2Src && (
          <Img
            src={currentV2Src}
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: "100%",
              height: "100%",
              objectFit: "cover",
              opacity: transitionProgress > 0
                ? 0 // hidden during pose crossfade
                : currentBlend.blendProgress,
            }}
          />
        )}

        {/* Crossfade next pose frame */}
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
