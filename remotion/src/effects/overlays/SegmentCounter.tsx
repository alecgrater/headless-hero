/**
 * SegmentCounter — segmented ring overlay showing progress through segments.
 * Positioned bottom-right to mirror the SegmentTimer on the bottom-left.
 */
import React from "react";
import { useCurrentFrame, useVideoConfig, interpolate, spring } from "remotion";

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
const FADE_FRAMES = 15;
const GAP_DEGREES = 4;

function describeArc(
  cx: number,
  cy: number,
  r: number,
  startAngle: number,
  endAngle: number,
): string {
  const startRad = ((startAngle - 90) * Math.PI) / 180;
  const endRad = ((endAngle - 90) * Math.PI) / 180;
  const x1 = cx + r * Math.cos(startRad);
  const y1 = cy + r * Math.sin(startRad);
  const x2 = cx + r * Math.cos(endRad);
  const y2 = cy + r * Math.sin(endRad);
  const largeArc = endAngle - startAngle > 180 ? 1 : 0;
  return `M ${x1} ${y1} A ${r} ${r} 0 ${largeArc} 1 ${x2} ${y2}`;
}

export const SegmentCounter: React.FC<Props> = ({ segmentRanges }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const totalSegments = segmentRanges.length;
  if (totalSegments === 0) return null;

  const currentIndex = segmentRanges.findIndex(
    (r) => frame >= r.start_frame && frame < r.end_frame,
  );
  if (currentIndex === -1) return null;

  const currentRange = segmentRanges[currentIndex];
  const segmentDuration = currentRange.end_frame - currentRange.start_frame;
  const elapsed = frame - currentRange.start_frame;

  const fadeSafe = Math.min(FADE_FRAMES, Math.floor(segmentDuration / 2));
  const opacity = interpolate(
    elapsed,
    [0, fadeSafe, segmentDuration - fadeSafe, segmentDuration],
    [0, 0.74, 0.74, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  // Spring pop when entering a new segment
  const fillSpring = spring({
    frame: elapsed,
    fps,
    config: { damping: 12, mass: 0.6, stiffness: 120 },
    durationInFrames: 15,
  });
  const popScale = interpolate(fillSpring, [0, 1], [1.08, 1.0]);

  const sliceDegrees = (360 - GAP_DEGREES * totalSegments) / totalSegments;

  const slices: React.ReactNode[] = [];
  for (let i = 0; i < totalSegments; i++) {
    const startAngle = i * (sliceDegrees + GAP_DEGREES);
    const endAngle = startAngle + sliceDegrees;

    let color: string;
    let sliceOpacity: number;
    if (i < currentIndex) {
      color = "rgba(140, 120, 255, 0.95)";
      sliceOpacity = 1;
    } else if (i === currentIndex) {
      color = "rgba(140, 120, 255, 0.95)";
      sliceOpacity = interpolate(fillSpring, [0, 1], [0.3, 1.0]);
    } else {
      color = "rgba(255, 255, 255, 0.15)";
      sliceOpacity = 1;
    }

    slices.push(
      <path
        key={i}
        d={describeArc(CENTER, CENTER, RADIUS, startAngle, endAngle)}
        fill="none"
        stroke={color}
        strokeWidth={STROKE_WIDTH}
        strokeLinecap="round"
        opacity={sliceOpacity}
      />,
    );
  }

  const counterText = `${currentIndex + 1}/${totalSegments}`;

  return (
    <div
      style={{
        position: "absolute",
        bottom: 50,
        right: 30,
        zIndex: 7,
        width: SIZE,
        height: SIZE,
        opacity,
        transform: `scale(${popScale})`,
        transformOrigin: "center center",
        filter:
          "drop-shadow(0 0 10px rgba(0, 0, 0, 0.7)) drop-shadow(0 0 20px rgba(140, 120, 255, 0.15))",
      }}
    >
      <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`}>
        <defs>
          <filter id="counter-glow">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <circle
          cx={CENTER}
          cy={CENTER}
          r={RADIUS + 2}
          fill="rgba(0, 0, 0, 0.9)"
        />

        {slices}

        <text
          x={CENTER}
          y={CENTER}
          textAnchor="middle"
          dominantBaseline="central"
          fill="white"
          fontSize={24}
          fontFamily="monospace"
          fontWeight="bold"
          filter="url(#counter-glow)"
        >
          {counterText}
        </text>
      </svg>
    </div>
  );
};
