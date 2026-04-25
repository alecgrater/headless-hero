/**
 * EliOverlay — Renders the Eli character overlay with spring-physics
 * transitions, continuous mouth blending, compound breathing, variant
 * cycling, and entrance/exit animations.
 *
 * Mouth openness is derived from phrase_timestamps as a continuous 0-1
 * value. Both open and closed frames are rendered stacked with
 * complementary opacities for smooth blending.
 */
import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  Img,
  interpolate,
  spring,
  Easing,
} from "remotion";
import type {
  EliOverlay as EliOverlayType,
  EliKeyframe,
  PhraseTimestamp,
} from "../../types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Simple string hash for deterministic pseudo-random seeding. */
function hashCode(s: string): number {
  let hash = 0;
  for (let i = 0; i < s.length; i++) {
    hash = ((hash << 5) - hash + s.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

/**
 * Build a pseudo-random variant sequence avoiding consecutive duplicates.
 * Cached by (seed, variantCount) to avoid allocation on every frame.
 */
const variantSequenceCache = new Map<string, number[]>();

function buildVariantSequence(seed: number, variantCount: number): number[] {
  const cacheKey = `${seed}:${variantCount}`;
  const cached = variantSequenceCache.get(cacheKey);
  if (cached) return cached;

  const seqLength = 8 + (seed % 5);
  const sequence: number[] = [];
  let rng = seed;
  let lastVariant = -1;

  for (let i = 0; i < seqLength; i++) {
    rng = (rng * 1664525 + 1013904223) & 0x7fffffff;
    let variant = (rng % variantCount) + 1;
    // Re-roll once if same as previous
    if (variant === lastVariant && variantCount > 1) {
      rng = (rng * 1664525 + 1013904223) & 0x7fffffff;
      variant = (rng % variantCount) + 1;
    }
    sequence.push(variant);
    lastVariant = variant;
  }

  variantSequenceCache.set(cacheKey, sequence);
  return sequence;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Variant cycle length in frames (3s at 30fps). */
const VARIANT_CYCLE_FRAMES = 90;

/** Fraction of the cycle spent crossfading between variants (continuous). */
const VARIANT_BLEND_FRACTION = 1.0;

/** Number of frames for pose crossfade zone. */
const CROSSFADE_FRAMES = 20;

/** Entrance animation duration in frames. */
const ENTRANCE_FRAMES = 18;

/** Exit animation duration in frames. */
const EXIT_FRAMES = 10;

/** Corner presets for per-scene Eli placement. */
const CORNER_PRESETS: Record<string, { x: number; y: number }> = {
  TL: { x: 140, y: 30 },
  TR: { x: 1400, y: 30 },
  BL: { x: 140, y: 835 },
  BR: { x: 1400, y: 835 },
};

/** Expression → breathing rate multiplier. */
const BREATH_RATES: Record<string, number> = {
  excited: 1.3, surprised: 1.3, hyping: 1.3,
  neutral: 1.0, explaining: 1.0, thinking: 1.0, curious: 1.0,
  smiling: 0.9, relaxed: 0.8, calm: 0.8, serious: 0.9,
};

// ---------------------------------------------------------------------------
// Mouth openness (continuous 0-1)
// ---------------------------------------------------------------------------

/**
 * Compute continuous mouth openness at a given frame using phrase timestamps.
 * Snap open (~40ms), hold 1.0 during phrase, fade close (~110ms).
 */
function getMouthOpenness(
  frame: number,
  fps: number,
  phraseTimestamps: PhraseTimestamp[] | null | undefined,
): number {
  if (!phraseTimestamps || phraseTimestamps.length === 0) return 0;
  const timeMs = (frame / fps) * 1000;

  const RAMP_OPEN_MS = 40;
  const RAMP_CLOSE_MS = 110;

  for (let i = 0; i < phraseTimestamps.length; i++) {
    const phrase = phraseTimestamps[i];

    // Ramp open before phrase start
    if (timeMs >= phrase.start_ms - RAMP_OPEN_MS && timeMs < phrase.start_ms) {
      return interpolate(
        timeMs,
        [phrase.start_ms - RAMP_OPEN_MS, phrase.start_ms],
        [0, 1],
        { easing: Easing.inOut(Easing.ease) },
      );
    }

    // During phrase — fully open
    if (timeMs >= phrase.start_ms && timeMs <= phrase.end_ms) {
      return 1.0;
    }

    // Ramp close after phrase end
    if (timeMs > phrase.end_ms && timeMs <= phrase.end_ms + RAMP_CLOSE_MS) {
      return interpolate(
        timeMs,
        [phrase.end_ms, phrase.end_ms + RAMP_CLOSE_MS],
        [1, 0],
        { easing: Easing.inOut(Easing.ease) },
      );
    }
  }

  return 0;
}

// ---------------------------------------------------------------------------
// Variant cycling
// ---------------------------------------------------------------------------

interface VariantBlend {
  currentVariant: number;
  nextVariant: number;
  blendProgress: number;
}

function getVariantBlend(
  frame: number,
  keyframe: EliKeyframe,
  variantCount: number,
  frozen: boolean,
): VariantBlend {
  if (variantCount <= 1)
    return { currentVariant: 1, nextVariant: 1, blendProgress: 0 };

  const seed = hashCode(keyframe.frame_id + String(keyframe.start_frame));
  const sequence = buildVariantSequence(seed, variantCount);
  const elapsed = Math.max(0, frame - keyframe.start_frame);
  const cycleIndex = Math.floor(elapsed / VARIANT_CYCLE_FRAMES);
  const currentVariant = sequence[cycleIndex % sequence.length];

  if (frozen) {
    return { currentVariant, nextVariant: currentVariant, blendProgress: 0 };
  }

  const nextVariant = sequence[(cycleIndex + 1) % sequence.length];
  const posInCycle =
    (elapsed % VARIANT_CYCLE_FRAMES) / VARIANT_CYCLE_FRAMES;
  const blendStart = 1 - VARIANT_BLEND_FRACTION;

  let blendProgress = 0;
  if (posInCycle >= blendStart) {
    const raw = (posInCycle - blendStart) / VARIANT_BLEND_FRACTION;
    blendProgress = interpolate(raw, [0, 1], [0, 1], {
      easing: Easing.inOut(Easing.ease),
    });
  }

  return { currentVariant, nextVariant, blendProgress };
}

// ---------------------------------------------------------------------------
// Keyframe lookup
// ---------------------------------------------------------------------------

interface KeyframeState {
  current: EliKeyframe;
  next: EliKeyframe | null;
  prev: EliKeyframe | null;
  transitionProgress: number;
}

function getCurrentKeyframe(
  frame: number,
  keyframes: EliKeyframe[],
): KeyframeState | null {
  if (keyframes.length === 0) return null;

  for (let i = 0; i < keyframes.length; i++) {
    const kf = keyframes[i];
    if (frame >= kf.start_frame && frame < kf.end_frame) {
      const nextKf = i + 1 < keyframes.length ? keyframes[i + 1] : null;
      const prevKf = i > 0 ? keyframes[i - 1] : null;

      let transitionProgress = 0;
      if (nextKf && nextKf.transition === "crossfade") {
        const transitionStart = kf.end_frame - CROSSFADE_FRAMES;
        if (frame >= transitionStart) {
          transitionProgress = (frame - transitionStart) / CROSSFADE_FRAMES;
        }
      }

      return { current: kf, next: nextKf, prev: prevKf, transitionProgress };
    }
  }

  return {
    current: keyframes[keyframes.length - 1],
    next: null,
    prev: keyframes.length > 1 ? keyframes[keyframes.length - 2] : null,
    transitionProgress: 0,
  };
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface Props {
  overlay: EliOverlayType;
  phraseTimestamps?: PhraseTimestamp[] | null;
  characterFramesBaseUrl: string;
  variantCounts?: Record<string, number> | null;
  /** Total scene duration in frames (for exit animation). */
  sceneDurationInFrames?: number;
  /** Text-only scene (e.g. aha_subtitle): enlarge 180% and center above text. */
  isTextOnly?: boolean;
}

export const EliOverlay: React.FC<Props> = ({
  overlay,
  phraseTimestamps,
  characterFramesBaseUrl,
  variantCounts,
  sceneDurationInFrames,
  isTextOnly,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (!overlay.enabled || (overlay.keyframes ?? []).length === 0) return null;

  const kfState = getCurrentKeyframe(frame, overlay.keyframes ?? []);
  if (!kfState) return null;

  const { current, next, prev, transitionProgress } = kfState;

  // --- Mouth openness (continuous 0-1) ---
  const mouthOpenness = getMouthOpenness(frame, fps, phraseTimestamps);

  // --- Eased crossfade progress ---
  const easedTransition = interpolate(
    transitionProgress,
    [0, 1],
    [0, 1],
    { easing: Easing.bezier(0.25, 0.1, 0.25, 1.0) },
  );

  // Freeze variant cycling during pose crossfade
  const variantFrozen = transitionProgress > 0;

  // --- Variant blend for current keyframe ---
  const currentVariantCount = variantCounts?.[current.frame_id] ?? 1;
  const currentBlend = getVariantBlend(
    frame,
    current,
    currentVariantCount,
    variantFrozen,
  );

  // --- Build image srcs ---
  const buildSrc = (
    frameId: string,
    variant: number,
    mouth: "open" | "closed",
  ) => {
    const vSuffix = variant === 1 ? "" : `_v${variant}`;
    return `${characterFramesBaseUrl}/${frameId}${vSuffix}_${mouth}.png`;
  };

  // Current keyframe — variant A open + closed
  const curV1OpenSrc = buildSrc(current.frame_id, currentBlend.currentVariant, "open");
  const curV1ClosedSrc = buildSrc(current.frame_id, currentBlend.currentVariant, "closed");

  // Current keyframe — variant B (during variant crossfade)
  let curV2OpenSrc: string | null = null;
  let curV2ClosedSrc: string | null = null;
  if (
    currentBlend.blendProgress > 0 &&
    currentBlend.currentVariant !== currentBlend.nextVariant
  ) {
    curV2OpenSrc = buildSrc(current.frame_id, currentBlend.nextVariant, "open");
    curV2ClosedSrc = buildSrc(current.frame_id, currentBlend.nextVariant, "closed");
  }

  // Next pose (during pose crossfade)
  let nextOpenSrc: string | null = null;
  let nextClosedSrc: string | null = null;
  if (next && transitionProgress > 0) {
    const nextVariantCount = variantCounts?.[next.frame_id] ?? 1;
    const nextBlend = getVariantBlend(frame, next, nextVariantCount, true);
    nextOpenSrc = buildSrc(next.frame_id, nextBlend.currentVariant, "open");
    nextClosedSrc = buildSrc(next.frame_id, nextBlend.currentVariant, "closed");
  }

  // --- Spring scale overshoot on new keyframe entry ---
  const poseAge = frame - current.start_frame;
  const isReaction = current.mood === "reaction";
  const scaleSpring = spring({
    frame: poseAge,
    fps,
    config: {
      damping: isReaction ? 10 : 14,
      mass: isReaction ? 0.5 : 0.7,
      stiffness: isReaction ? 140 : 100,
    },
    durationInFrames: 20,
  });
  const poseScale = interpolate(
    scaleSpring,
    [0, 1],
    [isReaction ? 1.02 : 1.008, 1.0],
  );

  // --- Compound breathing animation ---
  const expression = current.frame_id.split("_")[0];
  const breathRate = BREATH_RATES[expression] ?? 1.0;
  const t = (frame / fps) * breathRate;

  const breathY = Math.sin(t * Math.PI) * 2;
  const breathScale = 1 + Math.sin(t * Math.PI + 0.3) * 0.003;
  const breathRotate = Math.sin(t * Math.PI + 1.2) * 0.3;

  // Secondary idle: slower ambient drift
  const idleT = (frame / fps) * 0.63;
  const idleY = Math.sin(idleT * Math.PI) * 1;
  const idleRotate = Math.sin(idleT * Math.PI) * 0.2;

  // --- Entrance animation ---
  const entranceSpring = spring({
    frame: Math.min(frame, ENTRANCE_FRAMES),
    fps,
    config: { damping: 14, mass: 0.7, stiffness: 100 },
    durationInFrames: ENTRANCE_FRAMES,
  });
  const entranceY = interpolate(entranceSpring, [0, 1], [50, 0]);
  const entranceOpacity = interpolate(entranceSpring, [0, 1], [0, 1]);

  // --- Exit animation ---
  const totalFrames =
    sceneDurationInFrames ??
    (overlay.keyframes ?? []).reduce(
      (max, kf) => Math.max(max, kf.end_frame),
      0,
    );
  const framesFromEnd = totalFrames - frame;
  const exitOpacity =
    framesFromEnd <= EXIT_FRAMES
      ? interpolate(framesFromEnd, [0, EXIT_FRAMES], [0, 1], {
          easing: Easing.inOut(Easing.ease),
        })
      : 1;

  // Container size — 180% larger for text-only scenes
  const TEXT_ONLY_SCALE = 1.8;
  const baseWidth = 360;
  const baseHeight = 215;
  const containerWidth = isTextOnly ? baseWidth * TEXT_ONLY_SCALE : baseWidth;
  const containerHeight = isTextOnly ? baseHeight * TEXT_ONLY_SCALE : baseHeight;

  // --- Position: centered above text for text-only scenes, corner preset otherwise ---
  const resolveCornerPos = () => {
    if (isTextOnly) {
      return {
        x: (1920 - containerWidth) / 2,
        y: 120,
      };
    }
    if (overlay.corner && CORNER_PRESETS[overlay.corner]) {
      return CORNER_PRESETS[overlay.corner];
    }
    if (overlay.position) {
      return { x: overlay.position.x, y: overlay.position.y };
    }
    return CORNER_PRESETS.BR;
  };

  const { x: posX, y: posY } = resolveCornerPos();

  // --- Combined transforms ---
  const combinedScale = breathScale * poseScale;
  const combinedY = breathY + idleY + entranceY;
  const combinedRotate = breathRotate + idleRotate;
  const combinedOpacity = entranceOpacity * exitOpacity;

  // --- Render helper for a blended open/closed image pair ---
  const renderMouthBlend = (
    openSrc: string,
    closedSrc: string,
    layerOpacity: number,
    isAbsolute: boolean,
  ) => (
    <div
      style={{
        position: isAbsolute ? "absolute" : "relative",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        opacity: layerOpacity,
      }}
    >
      {/* Closed mouth layer */}
      <Img
        src={closedSrc}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          position: "absolute",
          top: 0,
          left: 0,
          opacity: 1 - mouthOpenness,
        }}
      />
      {/* Open mouth layer */}
      <Img
        src={openSrc}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          position: "absolute",
          top: 0,
          left: 0,
          opacity: mouthOpenness,
        }}
      />
    </div>
  );

  // --- Compute layer opacities ---
  // Current variant A opacity
  let curV1Opacity: number;
  if (easedTransition > 0) {
    curV1Opacity = 1 - easedTransition;
  } else if (curV2OpenSrc) {
    curV1Opacity = 1 - currentBlend.blendProgress;
  } else {
    curV1Opacity = 1;
  }

  // Current variant B opacity
  const curV2Opacity =
    easedTransition > 0 ? 0 : currentBlend.blendProgress;

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
        opacity: combinedOpacity,
        transform: `translateY(${combinedY}px) scale(${combinedScale}) rotate(${combinedRotate}deg)`,
        borderRadius: 14,
        overflow: "hidden",
        border: "2px solid rgba(0, 220, 220, 0.6)",
        boxShadow:
          "0 0 20px rgba(0, 200, 200, 0.4), 0 0 40px rgba(0, 200, 200, 0.15)",
      }}
    >
      <div
        style={{
          width: "100%",
          height: "100%",
          position: "relative",
        }}
      >
        {/* Current variant A — mouth-blended */}
        {renderMouthBlend(curV1OpenSrc, curV1ClosedSrc, curV1Opacity, false)}

        {/* Current variant B — mouth-blended (variant crossfade) */}
        {curV2OpenSrc &&
          curV2ClosedSrc &&
          curV2Opacity > 0 &&
          renderMouthBlend(curV2OpenSrc, curV2ClosedSrc, curV2Opacity, true)}

        {/* Next pose — mouth-blended (pose crossfade) */}
        {nextOpenSrc &&
          nextClosedSrc &&
          easedTransition > 0 &&
          renderMouthBlend(nextOpenSrc, nextClosedSrc, easedTransition, true)}
      </div>
    </div>
  );
};
