import React from "react";
import { Img, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { BlinkOverlayAnchor, BlinkOverlayPoint, SceneInput, VisualLayer } from "../types";
import { StatCard } from "./StatCard";

interface Props {
  scene: SceneInput;
  fallbackVisualLayer: React.ReactNode;
}

const loggedTreatments = new Set<string>();

const logTreatmentOnce = (scene: SceneInput, treatment: string, validLayerCount: number) => {
  const key = `${scene.id}:${treatment}:${validLayerCount}`;
  if (loggedTreatments.has(key)) {
    return;
  }
  loggedTreatments.add(key);
  console.debug("[REMOTION_TREATMENT]", {
    sceneId: scene.id,
    treatment,
    validLayerCount,
  });
};

const validImageLayers = (scene: SceneInput): VisualLayer[] => {
  return (scene.visual_layers ?? []).filter((layer) => layer.type === "image" && layer.image_path);
};

const panelPlacementStyle = (placement?: string): React.CSSProperties => {
  const normalized = (placement ?? "center").replace(/-/g, "_");
  const base: React.CSSProperties = {
    position: "absolute",
    width: 700,
    height: 520,
  };

  switch (normalized) {
    case "left":
      return { ...base, left: 160, top: "50%", transform: "translateY(-50%)" };
    case "right":
      return { ...base, right: 160, top: "50%", transform: "translateY(-50%)" };
    case "top":
      return { ...base, left: "50%", top: 90, transform: "translateX(-50%)" };
    case "bottom":
      return { ...base, left: "50%", bottom: 90, transform: "translateX(-50%)" };
    case "top_left":
      return { ...base, left: 120, top: 90 };
    case "top_right":
      return { ...base, right: 120, top: 90 };
    case "bottom_left":
      return { ...base, left: 120, bottom: 90 };
    case "bottom_right":
      return { ...base, right: 120, bottom: 90 };
    case "center":
    default:
      return { ...base, left: "50%", top: "50%", transform: "translate(-50%, -50%)" };
  }
};

export const layerFrameStyle = (layer: VisualLayer): React.CSSProperties => {
  if (layer.asset_kind === "full_frame" || layer.asset_kind === "panel") {
    return {
      position: "absolute",
      inset: 0,
    };
  }
  if (layer.asset_kind === "cutout") {
    return {
      ...panelPlacementStyle(layer.placement),
      width: 620,
      height: 620,
    };
  }
  return panelPlacementStyle(layer.placement);
};

const layerImageStyle = (layer: VisualLayer): React.CSSProperties => ({
  width: "100%",
  height: "100%",
  objectFit: layer.asset_kind === "cutout" ? "contain" : "cover",
  display: "block",
});

export const layerChromeStyle = (layer: VisualLayer, scale = 1): React.CSSProperties => {
  const isCutout = layer.asset_kind === "cutout";
  const isFullBleedLayer = layer.asset_kind === "full_frame" || layer.asset_kind === "panel";
  return {
    position: "relative",
    width: "100%",
    height: "100%",
    transform: `scale(${scale})`,
    transformOrigin: "center",
    border: "none",
    boxShadow: isCutout || isFullBleedLayer ? "none" : "0 24px 60px rgba(0, 0, 0, 0.45)",
    overflow: isCutout ? "visible" : "hidden",
    backgroundColor: isCutout || isFullBleedLayer ? "transparent" : "#111",
  };
};

interface PopupOrbitStyleOptions {
  layerIndex: number;
  itemIndex: number;
  itemCount: number;
  frame: number;
  fps: number;
}

const POPUP_ORBIT_CENTER_X = 960;
const POPUP_ORBIT_CENTER_Y = 540;
const POPUP_ORBIT_RADIUS_X = 430;
const POPUP_ORBIT_RADIUS_Y = 260;
const POPUP_ORBIT_SECONDS = 5;

export const popupOrbitFrameStyle = (
  layer: VisualLayer,
  options: PopupOrbitStyleOptions,
): React.CSSProperties => {
  if (layer.asset_kind !== "cutout" || options.itemIndex < 0 || options.itemCount <= 0) {
    return {
      ...layerFrameStyle(layer),
      opacity: 1,
      transformOrigin: "center",
    };
  }

  const baseAngle = (Math.PI * 2 * options.itemIndex) / options.itemCount;
  const orbitProgress = options.frame / Math.max(1, options.fps * POPUP_ORBIT_SECONDS);
  const angle = baseAngle + orbitProgress * Math.PI * 2;
  const width = 340;
  const height = 340;

  return {
    position: "absolute",
    width,
    height,
    left: POPUP_ORBIT_CENTER_X + Math.cos(angle) * POPUP_ORBIT_RADIUS_X,
    top: POPUP_ORBIT_CENTER_Y + Math.sin(angle) * POPUP_ORBIT_RADIUS_Y,
    transform: "translate(-50%, -50%)",
    transformOrigin: "center",
    zIndex: 10 + options.layerIndex,
  };
};

const isPopupAnchorLayer = (layer: VisualLayer, index: number): boolean => (
  layer.asset_kind === "cutout"
  && (index === 0 || layer.id.endsWith("_anchor") || layer.animation === "none")
);

const PopupSequence: React.FC<Props> = ({ scene, fallbackVisualLayer }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const layers = validImageLayers(scene);
  const popupItemLayers = layers.filter((layer, index) => !isPopupAnchorLayer(layer, index));

  logTreatmentOnce(scene, "popup_sequence", layers.length);

  if (layers.length === 0) {
    return <>{fallbackVisualLayer}</>;
  }

  return (
    <div style={{ position: "absolute", inset: 0 }}>
      {layers.map((layer, layerIndex) => {
        const itemIndex = popupItemLayers.findIndex((itemLayer) => itemLayer.id === layer.id);
        const enterFrame = Math.round((layer.enter_at_seconds ?? 0) * fps);
        const opacity = interpolate(frame, [enterFrame, enterFrame + 8], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        const popScale = layer.animation === "pop_in"
          ? spring({
              frame: Math.max(0, frame - enterFrame),
              fps,
              config: {
                damping: 14,
                mass: 0.7,
                stiffness: 180,
              },
            })
          : 1;
        const scale = layer.animation === "pop_in"
          ? interpolate(popScale, [0, 1], [0.86, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            })
          : 1;

        return (
          <div
            key={layer.id}
            style={{
              ...popupOrbitFrameStyle(layer, {
                layerIndex,
                itemIndex,
                itemCount: popupItemLayers.length,
                frame,
                fps,
              }),
              opacity,
            }}
          >
            <div style={layerChromeStyle(layer, scale)}>
              <Img
                src={layer.image_path ?? ""}
                style={layerImageStyle(layer)}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
};

type BlinkOverlay =
  | { kind: "mouth"; state: "open" }
  | { kind: "eyes"; state: "closed" }
  | { kind: "eyes"; state: "glance" }
  | { kind: "brows"; state: "raised" };

type BlinkResolvedOverlayAnchor = Required<Pick<
  BlinkOverlayAnchor,
  "eye_left" | "eye_right" | "mouth" | "brow_left" | "brow_right"
>> & Pick<BlinkOverlayAnchor, "skin_fill">;

type BlinkClosedEyeGeometry = {
  mask: {
    x: number;
    y: number;
    width: number;
    height: number;
    rx: number;
    fill: string;
    gradient?: {
      id: string;
      top: string;
      bottom: string;
      orientation: "horizontal" | "vertical";
    };
  };
  lid: {
    d: string;
    y: number;
    stroke: string;
    strokeWidth: number;
  };
};

const BLINK_FALLBACK_SKIN_FILL = "#D9A374";
const BLINK_EYELID_STROKE = "#2A1712";
export const BLINK_OVERLAY_ASPECT = 16 / 9;
export const BLINK_OVERLAY_SVG_PROPS = {
  viewBox: "0 0 100 100",
  preserveAspectRatio: "none",
} as const;

const hashString = (value: string): number => {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
};

const blinkNoise = (index: number, seed = ""): number => {
  const hash = hashString(`${seed}:${index}`);
  return ((hash ^ (hash >>> 16)) >>> 0) / 4294967295;
};

const blinkWindowAtFrame = (
  frame: number,
  fps: number,
  seed = "",
): { active: boolean; index: number } => {
  const safeFrame = Math.max(0, frame);
  const safeFps = Math.max(1, fps);
  let startFrame = seed
    ? Math.round(safeFps * (1.0 + blinkNoise(0, seed) * 1.8))
    : Math.round(safeFps * 1.8);
  let blinkIndex = 0;

  while (startFrame <= safeFrame + Math.round(safeFps * 6)) {
    const durationFrames = Math.max(2, Math.round(safeFps * (0.09 + blinkNoise(blinkIndex * 4 + 1, seed) * 0.08)));
    if (safeFrame >= startFrame && safeFrame < startFrame + durationFrames) {
      return { active: true, index: blinkIndex };
    }

    const doubleBlink = blinkNoise(blinkIndex * 4 + 2, seed) < 0.18;
    if (doubleBlink) {
      const doubleStart = startFrame + durationFrames + Math.round(safeFps * (0.16 + blinkNoise(blinkIndex * 4 + 3, seed) * 0.12));
      const doubleDuration = Math.max(2, Math.round(safeFps * 0.08));
      if (safeFrame >= doubleStart && safeFrame < doubleStart + doubleDuration) {
        return { active: true, index: blinkIndex + 1 };
      }
    }

    startFrame += Math.round(safeFps * (1.9 + blinkNoise(blinkIndex * 4 + 4, seed) * 3.7));
    blinkIndex += doubleBlink ? 2 : 1;
  }

  return { active: false, index: blinkIndex };
};

export const blinkOverlayVisible = (frame: number, fps: number, seed = ""): boolean => {
  return blinkWindowAtFrame(frame, fps, seed).active;
};

export const blinkMicroOverlay = (action?: string | null): BlinkOverlay | null => {
  switch (action) {
    case "blink":
      return { kind: "eyes", state: "closed" };
    default:
      return null;
  }
};

const toSvgPoint = (point: BlinkOverlayPoint): BlinkOverlayPoint => ({
  x: point.x * 100,
  y: point.y * 100,
});

const clamp = (value: number, min: number, max: number): number => (
  Math.max(min, Math.min(max, value))
);

const roundSvgNumber = (value: number): number => (
  Number(value.toFixed(3))
);

const hexColorPattern = /^#[0-9a-f]{6}$/i;

const parseHexColor = (color?: string): [number, number, number] | null => {
  if (!hexColorPattern.test(color ?? "")) {
    return null;
  }
  const hex = (color as string).slice(1);
  return [
    Number.parseInt(hex.slice(0, 2), 16),
    Number.parseInt(hex.slice(2, 4), 16),
    Number.parseInt(hex.slice(4, 6), 16),
  ];
};

const colorDistance = (first?: string, second?: string): number | null => {
  const firstRgb = parseHexColor(first);
  const secondRgb = parseHexColor(second);
  if (!firstRgb || !secondRgb) {
    return null;
  }
  const redDelta = firstRgb[0] - secondRgb[0];
  const greenDelta = firstRgb[1] - secondRgb[1];
  const blueDelta = firstRgb[2] - secondRgb[2];
  return Math.sqrt(redDelta * redDelta + greenDelta * greenDelta + blueDelta * blueDelta);
};

const eyeGradient = (
  point: BlinkOverlayPoint,
  index: number,
): NonNullable<BlinkClosedEyeGeometry["mask"]["gradient"]> | undefined => {
  const sideDistance = colorDistance(point.fill_left, point.fill_right);
  const verticalDistance = colorDistance(point.fill_top, point.fill_bottom);
  const useSideGradient = sideDistance !== null
    && (verticalDistance === null || sideDistance >= verticalDistance);
  if (useSideGradient) {
    return {
      id: `blink-blink-eye-${index}-gradient`,
      top: point.fill_left as string,
      bottom: point.fill_right as string,
      orientation: "horizontal",
    };
  }
  if (verticalDistance !== null) {
    return {
      id: `blink-blink-eye-${index}-gradient`,
      top: point.fill_top as string,
      bottom: point.fill_bottom as string,
      orientation: "vertical",
    };
  }
  return undefined;
};

const detectedEyeSize = (point: BlinkOverlayPoint): { width: number; height: number } | null => {
  if (
    typeof point.width !== "number"
    || typeof point.height !== "number"
    || point.width <= 0
    || point.height <= 0
  ) {
    return null;
  }
  return { width: point.width, height: point.height };
};

// Closed-eye marks must never read as a horizontal bar after the viewBox is
// stretched to the 16:9 frame: cap their on-screen width-to-height ratio.
const BLINK_MAX_ON_SCREEN_ASPECT = 2.4;

export const blinkBlinkEyeOverlayGeometry = (
  anchor: BlinkResolvedOverlayAnchor,
  skinFill = BLINK_FALLBACK_SKIN_FILL,
  aspect = BLINK_OVERLAY_ASPECT,
): BlinkClosedEyeGeometry[] => {
  // Drive every extent from the detected eye box. With no detected eye size we
  // suppress the overlay entirely rather than guessing from inter-eye distance
  // (guessing is what produced the oversized bars that crossed the nose).
  const leftSize = detectedEyeSize(anchor.eye_left);
  const rightSize = detectedEyeSize(anchor.eye_right);
  if (!leftSize || !rightSize) {
    return [];
  }

  const leftEye = toSvgPoint(anchor.eye_left);
  const rightEye = toSvgPoint(anchor.eye_right);
  const eyeDistance = Math.abs(rightEye.x - leftEye.x);
  // Coincident/degenerate eyes would collapse to zero-width marks: suppress.
  if (!(eyeDistance > 0)) {
    return [];
  }
  const midpointX = (leftEye.x + rightEye.x) / 2;
  const noseMargin = Math.max(eyeDistance * 0.1, 1.0);
  const safeAspect = aspect > 0 ? aspect : BLINK_OVERLAY_ASPECT;

  return [
    { point: anchor.eye_left, eye: leftEye, size: leftSize, side: "left" as const, index: 0 },
    { point: anchor.eye_right, eye: rightEye, size: rightSize, side: "right" as const, index: 1 },
  ].map(({ point, eye, size, side, index }) => {
    const eyeWidthVB = size.width * 100;
    const eyeHeightVB = size.height * 100;

    // Mask = the skin patch that covers the open eye. Slightly larger than the
    // detected eye, hard-capped so the two masks can never meet at the nose and
    // never read as a wide bar once the viewBox stretches across the frame.
    const maskHalfHeight = Math.max(eyeHeightVB * 0.85, eyeHeightVB * 0.5 + 0.4);
    let maskHalfWidth = eyeWidthVB * 0.6;
    maskHalfWidth = Math.min(maskHalfWidth, eyeDistance * 0.22);
    maskHalfWidth = Math.min(
      maskHalfWidth,
      (maskHalfHeight * BLINK_MAX_ON_SCREEN_ASPECT) / safeAspect,
    );

    let maskLeft = eye.x - maskHalfWidth;
    let maskRight = eye.x + maskHalfWidth;
    if (side === "left") {
      maskRight = Math.min(maskRight, midpointX - noseMargin);
    } else {
      maskLeft = Math.max(maskLeft, midpointX + noseMargin);
    }
    const maskWidth = Math.max(0, maskRight - maskLeft);
    const maskHeight = maskHalfHeight * 2;
    const maskTop = eye.y - maskHalfHeight;

    const gradient = eyeGradient(point, index);

    // Lid = a shallow closed-eye curve drawn at the detected eye center, kept
    // inside the mask so it can never stretch toward the nose.
    const lidHalfWidth = Math.max(0, Math.min(
      eyeWidthVB * 0.5,
      eyeDistance * 0.22,
      eye.x - maskLeft,
      maskRight - eye.x,
    ));
    const lidLift = maskHalfHeight * 0.3;
    const strokeWidth = clamp(eyeHeightVB * 0.28, 0.4, 0.9);

    return {
      mask: {
        x: roundSvgNumber(maskLeft),
        y: roundSvgNumber(maskTop),
        width: roundSvgNumber(maskWidth),
        height: roundSvgNumber(maskHeight),
        rx: roundSvgNumber(Math.min(maskWidth, maskHeight) / 2),
        fill: gradient ? `url(#${gradient.id})` : skinFill,
        ...(gradient ? { gradient } : {}),
      },
      lid: {
        d: `M${roundSvgNumber(eye.x - lidHalfWidth)} ${roundSvgNumber(eye.y)} Q${roundSvgNumber(eye.x)} ${roundSvgNumber(eye.y - lidLift)} ${roundSvgNumber(eye.x + lidHalfWidth)} ${roundSvgNumber(eye.y)}`,
        y: roundSvgNumber(eye.y),
        stroke: BLINK_EYELID_STROKE,
        strokeWidth: roundSvgNumber(strokeWidth),
      },
    };
  });
};

export const comparisonBoardLayerStyle = (
  layer: VisualLayer,
  layerIndex: number,
  layerCount: number,
  frame: number,
  fps: number,
): React.CSSProperties => {
  const positionsByCount = layerCount >= 3 ? ["20%", "50%", "80%"] : ["25%", "75%"];
  const normalizedPlacement = (layer.placement ?? "").replace(/_/g, "-");
  const placementIndex = normalizedPlacement === "left"
    ? 0
    : normalizedPlacement === "center"
      ? 1
      : normalizedPlacement === "right"
        ? Math.min(layerCount - 1, positionsByCount.length - 1)
        : layerIndex;
  const enterFrame = Math.round((layer.enter_at_seconds ?? 0) * fps);
  const float = Math.sin((frame + layerIndex * 12) / 28) * 10;
  const slide = interpolate(frame, [enterFrame, enterFrame + 14], [layerIndex === 0 ? -180 : 180, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const width = layerCount >= 3 ? 440 : 560;
  const height = layerCount >= 3 ? 580 : 640;

  return {
    position: "absolute",
    width,
    height,
    left: positionsByCount[Math.min(placementIndex, positionsByCount.length - 1)],
    top: "53%",
    transform: `translate(-50%, -50%) translateX(${slide}px) translateY(${float}px) scale(1)`,
    transformOrigin: "center",
    zIndex: 20 + layerIndex,
  };
};

const isDisplayableComparisonLabel = (label: string): boolean => {
  const normalized = label.trim();
  if (!normalized) {
    return false;
  }
  if (/^(left|right|center)\s+subject$/i.test(normalized)) {
    return false;
  }
  if (/^option\s+\d+$/i.test(normalized)) {
    return false;
  }
  return normalized.split(/\s+/).length <= 3 && normalized.length <= 28;
};

export const comparisonLabel = (layer: VisualLayer): string | null => {
  const explicitLabel = layer.label?.trim();
  if (explicitLabel && isDisplayableComparisonLabel(explicitLabel)) {
    return explicitLabel;
  }
  return null;
};

const ComparisonBoard: React.FC<Props> = ({ scene, fallbackVisualLayer }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const layers = validImageLayers(scene).slice(0, 3);

  logTreatmentOnce(scene, "comparison_board", layers.length);

  if (layers.length < 2) {
    return <>{fallbackVisualLayer}</>;
  }

  const dividerOpacity = interpolate(frame, [0, 12], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}>
      <div
        style={{
          position: "absolute",
          inset: "76px 84px 92px",
          border: "6px solid rgba(0, 0, 0, 0.82)",
          borderRadius: 24,
          opacity: dividerOpacity,
        }}
      />
      {layers.length === 2 ? (
        <div
          style={{
            position: "absolute",
            left: "50%",
            top: 92,
            bottom: 108,
            width: 8,
            background: "rgba(0, 0, 0, 0.82)",
            transform: "translateX(-50%)",
            opacity: dividerOpacity,
          }}
        />
      ) : (
        <>
          <div style={{ position: "absolute", left: "35%", top: 92, bottom: 108, width: 7, background: "rgba(0, 0, 0, 0.82)", opacity: dividerOpacity }} />
          <div style={{ position: "absolute", left: "65%", top: 92, bottom: 108, width: 7, background: "rgba(0, 0, 0, 0.82)", opacity: dividerOpacity }} />
        </>
      )}
      {layers.length === 2 && (
        <div
          style={{
            position: "absolute",
            left: "50%",
            top: 90,
            transform: "translateX(-50%)",
            width: 132,
            height: 132,
            borderRadius: 999,
            background: "#111111",
            color: "#F6C54A",
            border: "6px solid #FFFFFF",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: "Impact, Arial Black, sans-serif",
            fontSize: 54,
            letterSpacing: 0,
            opacity: dividerOpacity,
          }}
        >
          VS
        </div>
      )}
      {layers.map((layer, layerIndex) => {
        const enterFrame = Math.round((layer.enter_at_seconds ?? 0) * fps);
        const opacity = interpolate(frame, [enterFrame, enterFrame + 10], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        const label = comparisonLabel(layer);
        return (
          <React.Fragment key={layer.id}>
            {label ? (
              <div
                style={{
                  position: "absolute",
                  left: comparisonBoardLayerStyle(layer, layerIndex, layers.length, frame, fps).left,
                  top: 114,
                  transform: "translateX(-50%)",
                  padding: "12px 30px",
                  borderRadius: 999,
                  background: "#111111",
                  color: "#FFFFFF",
                  border: "4px solid #FFFFFF",
                  fontFamily: "Arial Black, Arial, sans-serif",
                  fontSize: 34,
                  textTransform: "uppercase",
                  letterSpacing: 0,
                  opacity,
                  zIndex: 50,
                }}
              >
                {label}
              </div>
            ) : null}
            <div
              style={{
                ...comparisonBoardLayerStyle(layer, layerIndex, layers.length, frame, fps),
                opacity,
              }}
            >
              <div style={layerChromeStyle(layer, 1)}>
                <Img
                  src={layer.image_path ?? ""}
                  style={layerImageStyle(layer)}
                />
              </div>
            </div>
          </React.Fragment>
        );
      })}
    </div>
  );
};

export const TreatmentRenderer: React.FC<Props> = ({ scene, fallbackVisualLayer }) => {
  switch (scene.visual_mode) {
    case "popup_sequence":
      return <PopupSequence scene={scene} fallbackVisualLayer={fallbackVisualLayer} />;
    case "comparison_board":
      return <ComparisonBoard scene={scene} fallbackVisualLayer={fallbackVisualLayer} />;
    case "stat_card":
      logTreatmentOnce(scene, "stat_card", scene.visual_layers?.length ?? 0);
      return <StatCard scene={scene} />;
    case "full_frame":
    default:
      logTreatmentOnce(scene, scene.visual_mode ?? "full_frame", scene.visual_layers?.length ?? 0);
      return <>{fallbackVisualLayer}</>;
  }
};
