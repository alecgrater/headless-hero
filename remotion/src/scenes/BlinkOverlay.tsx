import React from "react";
import type { BlinkOverlayAnchor, BlinkOverlayPoint } from "../types";
import {
  BLINK_OVERLAY_SVG_PROPS,
  blinkBlinkEyeOverlayGeometry,
  blinkMicroOverlay,
  blinkOverlayVisible,
} from "./TreatmentRenderer";

type BlinkResolvedOverlayAnchor = Required<Pick<
  BlinkOverlayAnchor,
  "eye_left" | "eye_right" | "mouth" | "brow_left" | "brow_right"
>> & Pick<BlinkOverlayAnchor, "skin_fill">;

type BlinkOverlay = NonNullable<ReturnType<typeof blinkMicroOverlay>>;

const validAnchorPoint = (point?: BlinkOverlayPoint): point is BlinkOverlayPoint => (
  typeof point?.x === "number"
  && typeof point?.y === "number"
  && point.x >= 0
  && point.x <= 1
  && point.y >= 0
  && point.y <= 1
);

// Conservative absolute bounds for a believable detected eye on a 16:9 frame.
const BLINK_EYE_MIN_SIZE = 0.004;
const BLINK_EYE_MAX_SIZE = 0.14;
const BLINK_EYE_MAX_VERTICAL_DELTA = 0.02;
const BLINK_EYE_MIN_SEPARATION = 0.04;
const BLINK_EYE_MAX_SEPARATION = 0.62;
const BLINK_EYE_MIN_SYMMETRY_RATIO = 0.55;

const eyeSizeInRange = (point: BlinkOverlayPoint): boolean => (
  typeof point.width === "number"
  && typeof point.height === "number"
  && point.width >= BLINK_EYE_MIN_SIZE
  && point.width <= BLINK_EYE_MAX_SIZE
  && point.height >= BLINK_EYE_MIN_SIZE
  && point.height <= BLINK_EYE_MAX_SIZE
);

// Final renderer-side safety net: even when the backend marked an anchor safe,
// refuse to draw an overlay whose geometry would obviously look wrong (missing
// or implausible eye sizes, asymmetric or misaligned eyes, or a separation that
// implies a mark spanning the nose). An unsafe anchor renders nothing.
const anchorIsRenderSafe = (
  eyeLeft: BlinkOverlayPoint,
  eyeRight: BlinkOverlayPoint,
): boolean => {
  if (!eyeSizeInRange(eyeLeft) || !eyeSizeInRange(eyeRight)) {
    return false;
  }
  // Eyes must be in left-to-right order; swapped eyes are a mis-detection.
  if (eyeRight.x <= eyeLeft.x) {
    return false;
  }
  const leftWidth = eyeLeft.width as number;
  const rightWidth = eyeRight.width as number;
  const leftHeight = eyeLeft.height as number;
  const rightHeight = eyeRight.height as number;
  const widthRatio = Math.min(leftWidth, rightWidth) / Math.max(leftWidth, rightWidth);
  const heightRatio = Math.min(leftHeight, rightHeight) / Math.max(leftHeight, rightHeight);
  if (widthRatio < BLINK_EYE_MIN_SYMMETRY_RATIO || heightRatio < BLINK_EYE_MIN_SYMMETRY_RATIO) {
    return false;
  }
  if (Math.abs(eyeLeft.y - eyeRight.y) > BLINK_EYE_MAX_VERTICAL_DELTA) {
    return false;
  }
  const separation = Math.abs(eyeRight.x - eyeLeft.x);
  if (separation < BLINK_EYE_MIN_SEPARATION || separation > BLINK_EYE_MAX_SEPARATION) {
    return false;
  }
  return true;
};

const isBlinkOverlayAnchor = (anchor: unknown): anchor is BlinkOverlayAnchor => (
  typeof anchor === "object" && anchor !== null
);

export const resolveBlinkOverlayAnchor = (anchor: unknown): BlinkResolvedOverlayAnchor | null => {
  if (!isBlinkOverlayAnchor(anchor) || anchor.detected !== true) {
    return null;
  }
  if (
    !validAnchorPoint(anchor.eye_left)
    || !validAnchorPoint(anchor.eye_right)
    || !validAnchorPoint(anchor.mouth)
    || !validAnchorPoint(anchor.brow_left)
    || !validAnchorPoint(anchor.brow_right)
  ) {
    return null;
  }
  if (!anchorIsRenderSafe(anchor.eye_left, anchor.eye_right)) {
    return null;
  }
  return {
    eye_left: anchor.eye_left,
    eye_right: anchor.eye_right,
    mouth: anchor.mouth,
    brow_left: anchor.brow_left,
    brow_right: anchor.brow_right,
    skin_fill: typeof anchor.skin_fill === "string" ? anchor.skin_fill : undefined,
  };
};

const toSvgPoint = (point: BlinkOverlayPoint): BlinkOverlayPoint => ({
  x: point.x * 100,
  y: point.y * 100,
});

export const BlinkMicroExpressionOverlay: React.FC<{
  anchor: BlinkResolvedOverlayAnchor;
  overlay: BlinkOverlay;
  visible: boolean;
  testId?: string;
}> = ({ anchor, overlay, visible, testId }) => {
  const opacity = visible ? 1 : 0;
  const common: React.CSSProperties = {
    position: "absolute",
    left: 0,
    top: 0,
    width: "100%",
    height: "100%",
    inset: 0,
    pointerEvents: "none",
    opacity,
    zIndex: 2,
  };
  const leftEye = toSvgPoint(anchor.eye_left);
  const rightEye = toSvgPoint(anchor.eye_right);
  const mouth = toSvgPoint(anchor.mouth);
  const leftBrow = toSvgPoint(anchor.brow_left);
  const rightBrow = toSvgPoint(anchor.brow_right);

  if (overlay.kind === "mouth") {
    return (
      <svg {...BLINK_OVERLAY_SVG_PROPS} style={common} data-testid={testId}>
        <ellipse cx={mouth.x} cy={mouth.y - 0.4} rx="4.5" ry="2.4" fill="#F4BE91" />
        <ellipse cx={mouth.x} cy={mouth.y} rx="1.6" ry="2.3" fill="#4B1814" stroke="#111" strokeWidth="0.65" />
      </svg>
    );
  }

  if (overlay.kind === "eyes" && overlay.state === "closed") {
    const eyeGeometry = blinkBlinkEyeOverlayGeometry(anchor, anchor.skin_fill ?? "#D9A374");
    const gradients = eyeGeometry
      .map((eye) => eye.mask.gradient)
      .filter((gradient): gradient is NonNullable<(typeof eyeGeometry)[number]["mask"]["gradient"]> => Boolean(gradient));
    return (
      <svg {...BLINK_OVERLAY_SVG_PROPS} style={common} data-testid={testId}>
        {gradients.length > 0 ? (
          <defs>
            {gradients.map((gradient) => (
              <linearGradient
                key={gradient.id}
                id={gradient.id}
                x1="0"
                y1="0"
                x2={gradient.orientation === "horizontal" ? "1" : "0"}
                y2={gradient.orientation === "horizontal" ? "0" : "1"}
              >
                <stop offset="0%" stopColor={gradient.top} />
                <stop offset="100%" stopColor={gradient.bottom} />
              </linearGradient>
            ))}
          </defs>
        ) : null}
        {eyeGeometry.map((eye, index) => {
          const { gradient: _gradient, ...mask } = eye.mask;
          return (
            <g key={index}>
              <rect {...mask} />
              <path d={eye.lid.d} fill="none" stroke={eye.lid.stroke} strokeWidth={eye.lid.strokeWidth} strokeLinecap="round" />
            </g>
          );
        })}
      </svg>
    );
  }

  if (overlay.kind === "eyes" && overlay.state === "glance") {
    return (
      <svg {...BLINK_OVERLAY_SVG_PROPS} style={common} data-testid={testId}>
        <ellipse cx={leftEye.x - 1.1} cy={leftEye.y} rx="1.7" ry="2.2" fill="#111" />
        <ellipse cx={rightEye.x - 1.1} cy={rightEye.y} rx="1.7" ry="2.2" fill="#111" />
      </svg>
    );
  }

  return (
    <svg {...BLINK_OVERLAY_SVG_PROPS} style={common} data-testid={testId}>
      <path d={`M${leftBrow.x - 4.5} ${leftBrow.y} Q${leftBrow.x} ${leftBrow.y - 1.8} ${leftBrow.x + 4.5} ${leftBrow.y - 0.6}`} fill="none" stroke="#111" strokeWidth="1.2" strokeLinecap="round" />
      <path d={`M${rightBrow.x - 4.5} ${rightBrow.y - 0.8} Q${rightBrow.x} ${rightBrow.y - 2.6} ${rightBrow.x + 4.5} ${rightBrow.y - 1.4}`} fill="none" stroke="#111" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
};

export { blinkMicroOverlay, blinkOverlayVisible };
