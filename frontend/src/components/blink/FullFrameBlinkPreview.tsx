import { assetUrl } from "../../api";

type BlinkAnchorPoint = {
  x: number;
  y: number;
  width?: number;
  height?: number;
};

interface Props {
  imageUrl: string;
  blink: boolean;
  anchor?: Record<string, unknown> | null;
}

export default function FullFrameBlinkPreview({ imageUrl, blink, anchor }: Props) {
  return (
    <div className="relative aspect-video min-h-0 overflow-hidden bg-neutral-950">
      <img src={assetUrl(imageUrl)} alt="" className="h-full w-full object-cover" />
      {blink ? <BlinkAnchorOverlay anchor={anchor} /> : null}
      <span className="absolute left-2 top-2 rounded bg-neutral-950/70 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-neutral-200">
        {blink ? "Blink" : "Still"}
      </span>
    </div>
  );
}

function BlinkAnchorOverlay({ anchor }: { anchor?: Record<string, unknown> | null }) {
  const left = pointFromAnchor(anchor, "eye_left");
  const right = pointFromAnchor(anchor, "eye_right");
  const skinFill = typeof anchor?.skin_fill === "string" ? anchor.skin_fill : "#D9A374";
  if (!left || !right) return null;
  return (
    <svg
      data-testid="full-frame-blink-preview-overlay"
      className="pointer-events-none absolute inset-0 h-full w-full"
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
    >
      {[left, right].map((eye, index) => {
        const geometry = blinkPreviewEyeOverlayGeometry(eye);
        return (
          <g key={index}>
            <rect
              x={geometry.mask.x}
              y={geometry.mask.y}
              width={geometry.mask.width}
              height={geometry.mask.height}
              rx={geometry.mask.rx}
              fill={skinFill}
            />
            <path
              d={`M${geometry.lid.left} ${geometry.lid.y} Q${geometry.lid.center} ${geometry.lid.liftedY} ${geometry.lid.right} ${geometry.lid.y}`}
              fill="none"
              stroke="#2A1712"
              strokeWidth={geometry.lid.strokeWidth}
              strokeLinecap="round"
            />
          </g>
        );
      })}
    </svg>
  );
}

export function blinkPreviewEyeOverlayGeometry(eye: BlinkAnchorPoint) {
  const eyeWidth = eye.width ?? 0.028;
  const eyeHeight = eye.height ?? 0.018;
  const minimalistDotEye = eyeWidth <= 0.018 && eyeHeight <= 0.018;
  const maskWidth = minimalistDotEye
    ? clamp(eyeWidth * 100 * 2.6, 1.2, 2.6)
    : clamp(eyeWidth * 100 * 1.75, 2.4, 6.6);
  const maskHeight = minimalistDotEye
    ? clamp(eyeHeight * 100 * 2.0, 1.0, 2.4)
    : clamp(eyeHeight * 100 * 1.18, 1.6, 7.4);
  const centerX = eye.x * 100;
  const centerY = eye.y * 100;
  const lidHalfWidth = minimalistDotEye
    ? clamp(eyeWidth * 100 * 1.15, 0.9, 1.45)
    : clamp(maskWidth * 0.34, 1.1, 2.3);
  const lidLift = minimalistDotEye ? 0 : clamp(maskHeight * 0.12, 0.12, 0.42);
  const strokeWidth = minimalistDotEye ? 0.48 : 0.62;
  return {
    mask: {
      x: roundSvgNumber(centerX - maskWidth / 2),
      y: roundSvgNumber(centerY - maskHeight / 2),
      width: roundSvgNumber(maskWidth),
      height: roundSvgNumber(maskHeight),
      rx: roundSvgNumber(maskHeight / 2),
    },
    lid: {
      left: roundSvgNumber(centerX - lidHalfWidth),
      center: roundSvgNumber(centerX),
      right: roundSvgNumber(centerX + lidHalfWidth),
      y: roundSvgNumber(centerY),
      liftedY: roundSvgNumber(centerY - lidLift),
      strokeWidth,
    },
  };
}

function pointFromAnchor(anchor: Record<string, unknown> | null | undefined, key: string) {
  const raw = anchor?.[key];
  if (!raw || typeof raw !== "object") return null;
  const point = raw as Record<string, unknown>;
  if (typeof point.x !== "number" || typeof point.y !== "number") return null;
  return {
    x: point.x,
    y: point.y,
    width: typeof point.width === "number" ? point.width : undefined,
    height: typeof point.height === "number" ? point.height : undefined,
  };
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function roundSvgNumber(value: number): number {
  return Math.round(value * 100) / 100;
}
