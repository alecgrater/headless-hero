/**
 * EliOverlay — Procedural idle animation for the Eli character overlay.
 *
 * Renders a single pose PNG with layered procedural motion:
 * breathing, body sway, head micro-tilts, blinks, lip sync,
 * and scene entrance/exit transitions.
 *
 * All randomness is seeded from hash(sceneId + frameId) for deterministic renders.
 */
import React from "react";
import {
  useCurrentFrame,
  useVideoConfig,
  Img,
  interpolate,
  spring,
} from "remotion";
import type {
  EliOverlay as EliOverlayType,
  PhraseTimestamp,
  Orientation,
} from "../../types";

// ---------------------------------------------------------------------------
// Seeded PRNG (deterministic per scene)
// ---------------------------------------------------------------------------

function hashCode(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = (Math.imul(31, h) + s.charCodeAt(i)) | 0;
  }
  return h >>> 0;
}

function seededRandom(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 1664525 + 1013904223) | 0;
    return (s >>> 0) / 4294967296;
  };
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const OVERLAY_SIZE = 280;
const OVERLAY_SIZE_VERTICAL = 380;
const TOP_MARGIN_VERTICAL = 80; // px inset from the top edge in vertical mode
const CORNER_MARGIN = 24;
const PHI = 1.618033988749895;
const SQRT2 = 1.4142135623730951;

// Entrance/exit
const ENTRANCE_FRAMES = 14;
const EXIT_FRAMES = 12;
const ENTRANCE_OFFSET = 60;

// ---------------------------------------------------------------------------
// Corner positioning
// ---------------------------------------------------------------------------

function cornerStyle(
  corner: string | null | undefined,
  orientation: Orientation | undefined,
): React.CSSProperties {
  // Vertical mode overrides corner: Eli is always top-center, larger
  if (orientation === "vertical") {
    return {
      position: "absolute",
      width: OVERLAY_SIZE_VERTICAL,
      height: OVERLAY_SIZE_VERTICAL,
      top: TOP_MARGIN_VERTICAL,
      left: "50%",
      transform: "translateX(-50%)",
    };
  }

  const c = corner ?? "BR";
  const base: React.CSSProperties = {
    position: "absolute",
    width: OVERLAY_SIZE,
    height: OVERLAY_SIZE,
  };
  switch (c) {
    case "TL":
      return { ...base, top: CORNER_MARGIN, left: CORNER_MARGIN };
    case "TR":
      return { ...base, top: CORNER_MARGIN, right: CORNER_MARGIN };
    case "BL":
      return { ...base, bottom: CORNER_MARGIN, left: CORNER_MARGIN };
    case "BR":
    default:
      return { ...base, bottom: CORNER_MARGIN, right: CORNER_MARGIN };
  }
}

// ---------------------------------------------------------------------------
// Lip sync helpers
// ---------------------------------------------------------------------------

function getMouthOpenness(
  frame: number,
  fps: number,
  phraseTimestamps: PhraseTimestamp[] | null | undefined,
): number {
  if (!phraseTimestamps || phraseTimestamps.length === 0) return 0;

  const timeMs = (frame / fps) * 1000;
  const RAMP_BEFORE = 40;
  const FADE_AFTER = 110;

  let openness = 0;
  for (const phrase of phraseTimestamps) {
    const start = phrase.start_ms - RAMP_BEFORE;
    const end = phrase.end_ms + FADE_AFTER;

    if (timeMs >= start && timeMs <= end) {
      if (timeMs < phrase.start_ms) {
        openness = Math.max(openness, (timeMs - start) / RAMP_BEFORE);
      } else if (timeMs > phrase.end_ms) {
        openness = Math.max(openness, 1 - (timeMs - phrase.end_ms) / FADE_AFTER);
      } else {
        openness = 1;
      }
    }
  }
  return Math.max(0, Math.min(1, openness));
}

// ---------------------------------------------------------------------------
// Blink schedule
// ---------------------------------------------------------------------------

interface BlinkEvent {
  startFrame: number;
  durationFrames: number;
}

function generateBlinkSchedule(
  totalFrames: number,
  rng: () => number,
): BlinkEvent[] {
  const blinks: BlinkEvent[] = [];
  let frame = Math.round(30 + rng() * 60); // first blink 1-3s in

  while (frame < totalFrames - 10) {
    const duration = rng() < 0.1 ? 5 : rng() < 0.2 ? 6 : 4; // slow blink 10%, double 20%, normal 70%
    blinks.push({ startFrame: frame, durationFrames: duration });

    // Double blink: 20% chance
    if (rng() < 0.2) {
      frame += duration + 3;
      if (frame < totalFrames - 10) {
        blinks.push({ startFrame: frame, durationFrames: 3 });
      }
    }

    // Next blink interval: 3-6 seconds
    frame += Math.round((3 + rng() * 3) * 30);
  }

  return blinks;
}

function getBlinkAmount(frame: number, blinks: BlinkEvent[]): number {
  for (const blink of blinks) {
    const localFrame = frame - blink.startFrame;
    if (localFrame >= 0 && localFrame < blink.durationFrames) {
      const mid = blink.durationFrames / 2;
      if (localFrame < mid) {
        return localFrame / mid;
      }
      return 1 - (localFrame - mid) / (blink.durationFrames - mid);
    }
  }
  return 0;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

interface Props {
  overlay: EliOverlayType;
  phraseTimestamps?: PhraseTimestamp[] | null;
  characterFramesBaseUrl: string;
  sceneDurationInFrames: number;
  sceneId: string;
  orientation?: Orientation;
}

export const EliOverlay: React.FC<Props> = ({
  overlay,
  phraseTimestamps,
  characterFramesBaseUrl,
  sceneDurationInFrames,
  sceneId,
  orientation,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const frameId = overlay.frame_id;
  const seed = hashCode(`${sceneId}_${frameId}`);
  const rng = seededRandom(seed);

  // Pre-generate blink schedule (deterministic from seed)
  const blinks = React.useMemo(
    () => generateBlinkSchedule(sceneDurationInFrames, seededRandom(seed)),
    [sceneDurationInFrames, seed],
  );

  // Phase offsets (seeded)
  const breathPhase = rng() * Math.PI * 2;
  const swayPhase = rng() * Math.PI * 2;
  const tiltPhase = rng() * Math.PI * 2;

  // Time in seconds
  const t = frame / fps;

  // --- Breathing (~3.5s base cycle) ---
  const breathCycle = 2 * Math.PI / 3.5;
  const breathPrimary = Math.sin(breathCycle * t + breathPhase);
  const breathSecondary = Math.sin(breathCycle * PHI * t + breathPhase + 1.2);
  const breathScaleY = 1.0 + 0.004 * breathPrimary + 0.0015 * breathSecondary;
  const breathTranslateY = -2 * breathPrimary;

  // --- Body Sway (~7s cycle) ---
  const swayCycle = 2 * Math.PI / 7;
  const swayX = 3 * Math.sin(swayCycle * t + swayPhase);
  const swayRotate = 0.8 * Math.sin(swayCycle * t + swayPhase + Math.PI / 4);

  // --- Head Micro-Tilts (~5s cycle, √2 offset from sway) ---
  const tiltCycle = 2 * Math.PI / 5;
  const rawTilt = Math.sin(tiltCycle * t + tiltPhase + SQRT2);
  // Ease into holds: cubic ease-out feel
  const tiltRotate = 1.5 * Math.sign(rawTilt) * Math.pow(Math.abs(rawTilt), 0.7);

  // --- Blinks ---
  const blinkAmount = getBlinkAmount(frame, blinks);
  const blinkScaleY = 1 - blinkAmount * 0.08;
  const blinkTranslateY = blinkAmount * 3;

  // --- Lip Sync ---
  const mouthOpenness = getMouthOpenness(frame, fps, phraseTimestamps);

  // --- Entrance / Exit ---
  let entranceProgress = 1;
  let exitProgress = 0;

  if (frame < ENTRANCE_FRAMES) {
    const sp = spring({
      frame,
      fps,
      config: { damping: 12, stiffness: 120, mass: 0.8 },
      durationInFrames: ENTRANCE_FRAMES,
    });
    entranceProgress = sp;
  }

  const exitStart = sceneDurationInFrames - EXIT_FRAMES;
  if (frame >= exitStart) {
    exitProgress = interpolate(
      frame,
      [exitStart, sceneDurationInFrames],
      [0, 1],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
    );
  }

  const entranceY = (1 - entranceProgress) * ENTRANCE_OFFSET;
  const entranceOpacity = entranceProgress;
  const exitY = exitProgress * ENTRANCE_OFFSET;
  const exitOpacity = 1 - exitProgress;

  // --- Compose transforms ---
  const totalTranslateX = swayX;
  const totalTranslateY = breathTranslateY + blinkTranslateY + entranceY + exitY;
  const totalRotate = swayRotate + tiltRotate;
  const totalScaleY = breathScaleY * blinkScaleY;
  const totalOpacity = entranceOpacity * exitOpacity;

  // --- Image URLs ---
  const closedUrl = `${characterFramesBaseUrl}/${frameId}_closed.png`;
  const openUrl = `${characterFramesBaseUrl}/${frameId}_open.png`;

  // Size used for any sub-element style calculations that depend on the outer overlay size
  const overlaySize = orientation === "vertical" ? OVERLAY_SIZE_VERTICAL : OVERLAY_SIZE;

  return (
    <div
      style={{
        ...cornerStyle(overlay.corner, orientation),
        zIndex: 5,
        transform: `translate(${totalTranslateX}px, ${totalTranslateY}px) rotate(${totalRotate}deg) scaleY(${totalScaleY})`,
        opacity: totalOpacity,
        transformOrigin: "center bottom",
        pointerEvents: "none",
      }}
    >
      {/* Closed mouth layer */}
      <Img
        src={closedUrl}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "contain",
          position: "absolute",
          top: 0,
          left: 0,
          opacity: 1 - mouthOpenness,
        }}
      />
      {/* Open mouth layer */}
      <Img
        src={openUrl}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "contain",
          position: "absolute",
          top: 0,
          left: 0,
          opacity: mouthOpenness,
        }}
      />
    </div>
  );
};
