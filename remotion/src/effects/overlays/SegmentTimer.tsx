/**
 * SegmentTimer — countdown overlay showing time remaining in the current segment.
 * Renders a glowing circle with an animated ring that traces 360° as the segment progresses.
 */
import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate } from "remotion";

interface SegmentRange {
  start_frame: number;
  end_frame: number;
}

interface Props {
  segmentRanges: SegmentRange[];
}

const SIZE = 90;
const RADIUS = 35;
const STROKE_WIDTH = 3.5;
const CENTER = SIZE / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;
const FADE_FRAMES = 15;
const COMPLETION_FRAMES = 18;
const TICK_INTERVAL_SECONDS = 20;
const TICK_PULSE_FRAMES = 10;

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

export const SegmentTimer: React.FC<Props> = ({ segmentRanges }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Find the segment range containing the current frame
  const currentRange = segmentRanges.find(
    (r) => frame >= r.start_frame && frame < r.end_frame,
  );

  if (!currentRange) return null;

  const segmentDuration = currentRange.end_frame - currentRange.start_frame;
  const elapsed = frame - currentRange.start_frame;
  const progress = elapsed / segmentDuration;
  const remainingFrames = currentRange.end_frame - frame;
  const remainingSeconds = Math.ceil(remainingFrames / fps);

  // Fade in/out at segment boundaries (guard against short segments)
  const fadeSafe = Math.min(FADE_FRAMES, Math.floor(segmentDuration / 2));
  const opacity = interpolate(
    elapsed,
    [0, fadeSafe, segmentDuration - fadeSafe, segmentDuration],
    [0, 0.74, 0.74, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  // 20-second tick pulse: subtle scale breathe at every 20s boundary
  const tickIntervalFrames = TICK_INTERVAL_SECONDS * fps;
  const frameIntoTick = elapsed % tickIntervalFrames;
  const tickPulseScale =
    elapsed > 0 && frameIntoTick < TICK_PULSE_FRAMES
      ? interpolate(frameIntoTick, [0, 5, TICK_PULSE_FRAMES], [1.0, 1.06, 1.0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        })
      : 1.0;
  const tickRingBrightness =
    elapsed > 0 && frameIntoTick < TICK_PULSE_FRAMES
      ? interpolate(frameIntoTick, [0, 5, TICK_PULSE_FRAMES], [0, 0.4, 0], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        })
      : 0;

  // Completion flash in last COMPLETION_FRAMES of segment
  const framesFromEnd = segmentDuration - elapsed;
  const isCompleting = framesFromEnd <= COMPLETION_FRAMES && framesFromEnd > 0;
  const completionScale = isCompleting
    ? interpolate(
        framesFromEnd,
        [0, COMPLETION_FRAMES / 2, COMPLETION_FRAMES],
        [1.0, 1.14, 1.0],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
      )
    : 1.0;
  const completionOpacityBoost = isCompleting
    ? interpolate(framesFromEnd, [0, COMPLETION_FRAMES / 2, COMPLETION_FRAMES], [0, 0.2, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 0;

  const combinedScale = tickPulseScale * completionScale;
  const combinedOpacity = Math.min(1, opacity + completionOpacityBoost);

  // Ring color: vivid violet base, brightens during tick pulse, shifts to emerald green during completion
  const completionMix = isCompleting
    ? interpolate(framesFromEnd, [0, COMPLETION_FRAMES / 2, COMPLETION_FRAMES], [0, 1, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : 0;
  const baseR = 140 + tickRingBrightness * 115;
  const baseG = 120 + tickRingBrightness * 135;
  const baseB = 255;
  const ringR = Math.round(baseR + completionMix * (100 - baseR));
  const ringG = Math.round(baseG + completionMix * (220 - baseG));
  const ringB = Math.round(baseB + completionMix * (130 - baseB));
  const ringA = 0.95 + completionMix * 0.05;

  // Ring progress: starts as a dot, traces clockwise to full circle
  const dashOffset = CIRCUMFERENCE * (1 - progress);

  const timeText = formatTime(remainingSeconds);

  return (
    <div
      style={{
        position: "absolute",
        bottom: 50,
        left: 30,
        zIndex: 7,
        width: SIZE,
        height: SIZE,
        opacity: combinedOpacity,
        transform: `scale(${combinedScale})`,
        transformOrigin: "center center",
        filter: "drop-shadow(0 0 10px rgba(0, 0, 0, 0.7)) drop-shadow(0 0 20px rgba(140, 120, 255, 0.15))",
      }}
    >
      <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`}>
        <defs>
          <filter id="timer-glow">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        {/* Dark background circle */}
        <circle
          cx={CENTER}
          cy={CENTER}
          r={RADIUS + 2}
          fill="rgba(0, 0, 0, 0.9)"
        />

        {/* Track ring (subtle) */}
        <circle
          cx={CENTER}
          cy={CENTER}
          r={RADIUS}
          fill="none"
          stroke="rgba(255, 255, 255, 0.15)"
          strokeWidth={STROKE_WIDTH}
        />

        {/* Animated progress ring */}
        <circle
          cx={CENTER}
          cy={CENTER}
          r={RADIUS}
          fill="none"
          stroke={`rgba(${ringR}, ${ringG}, ${ringB}, ${ringA})`}
          strokeWidth={STROKE_WIDTH}
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={dashOffset}
          transform={`rotate(-90 ${CENTER} ${CENTER})`}
          filter="url(#timer-glow)"
        />

        {/* Countdown text */}
        <text
          x={CENTER}
          y={CENTER}
          textAnchor="middle"
          dominantBaseline="central"
          fill="white"
          fontSize={24}
          fontFamily="monospace"
          fontWeight="bold"
          filter="url(#timer-glow)"
        >
          {timeText}
        </text>
      </svg>
    </div>
  );
};
