/**
 * SegmentTimer — countdown overlay showing seconds remaining in the current segment.
 * Renders a glowing white circle with an animated ring that traces 360° as the segment progresses.
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

const SIZE = 72;
const RADIUS = 28;
const STROKE_WIDTH = 3;
const CENTER = SIZE / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;
const FADE_FRAMES = 15;

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

  // Fade in/out at segment boundaries
  const opacity = interpolate(
    elapsed,
    [0, FADE_FRAMES, segmentDuration - FADE_FRAMES, segmentDuration],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  // Ring progress: starts as a dot, traces clockwise to full circle
  const dashOffset = CIRCUMFERENCE * (1 - progress);

  return (
    <div
      style={{
        position: "absolute",
        bottom: 50,
        left: 30,
        zIndex: 7,
        width: SIZE,
        height: SIZE,
        opacity,
      }}
    >
      <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`}>
        <defs>
          <filter id="timer-glow">
            <feGaussianBlur stdDeviation="3" result="blur" />
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
          fill="rgba(0, 0, 0, 0.5)"
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
          stroke="white"
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
          fontSize="18"
          fontFamily="monospace"
          fontWeight="bold"
          filter="url(#timer-glow)"
        >
          {remainingSeconds}s
        </text>
      </svg>
    </div>
  );
};
