import React from "react";
import { Img, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { BlinkOverlayAnchor, BlinkOverlayPoint, SceneInput, VisualLayer } from "../types";
import { RendererContextStage } from "./RendererContextStage";
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

export const blinkLayerFrameStyle = (layer: VisualLayer): React.CSSProperties => {
  if (layer.asset_kind !== "cutout") {
    return layerFrameStyle(layer);
  }
  return {
    position: "absolute",
    left: "50%",
    top: "50%",
    width: 760,
    height: 820,
    transform: "translate(-50%, -50%)",
    transformOrigin: "center",
  };
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

const Blink: React.FC<Props> = ({ scene, fallbackVisualLayer }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const layers = validImageLayers(scene);
  const stateLayers = blinkStateLayers(layers);

  logTreatmentOnce(scene, "blink", layers.length);

  if (stateLayers.length === 0) {
    return <>{fallbackVisualLayer}</>;
  }

  const deterministicOverlay = blinkMicroOverlay(scene.blink_action);
  const overlayVisible = deterministicOverlay ? blinkOverlayVisible(frame, fps, scene.id) : false;
  const activeLayer = stateLayers.length === 1
    ? stateLayers[0]
    : blinkActiveLayer(stateLayers, frame, fps, scene.id);
  if (!activeLayer) {
    return <>{fallbackVisualLayer}</>;
  }
  const overlayAnchor = deterministicOverlay ? blinkOverlayAnchor(activeLayer) : null;

  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <RendererContextStage context={scene.renderer_context} />
      <div style={blinkLayerFrameStyle(activeLayer)}>
        <div style={layerChromeStyle(activeLayer)}>
          <Img
            src={activeLayer.image_path ?? ""}
            style={layerImageStyle(activeLayer)}
          />
          {deterministicOverlay && overlayAnchor ? (
            <BlinkMicroExpressionOverlay
              anchor={overlayAnchor}
              overlay={deterministicOverlay}
              visible={overlayVisible}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
};

export const blinkStateLayers = (layers: VisualLayer[]): VisualLayer[] => (
  layers.filter((layer) => layer.asset_kind === "cutout")
);

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

const validAnchorPoint = (point?: BlinkOverlayPoint): point is BlinkOverlayPoint => (
  typeof point?.x === "number"
  && typeof point?.y === "number"
  && point.x >= 0
  && point.x <= 1
  && point.y >= 0
  && point.y <= 1
);

export const blinkOverlayAnchor = (layer: VisualLayer): BlinkResolvedOverlayAnchor | null => {
  const anchor = layer.visual_source_metadata?.blink_overlay_anchor;
  if (!anchor?.detected) {
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

const normalizedEyeWidth = (point: BlinkOverlayPoint): number | null => (
  typeof point.width === "number" && point.width > 0 ? point.width * 100 : null
);

const normalizedEyeHeight = (point: BlinkOverlayPoint): number | null => (
  typeof point.height === "number" && point.height > 0 ? point.height * 100 : null
);

const isMinimalistDotEye = (point: BlinkOverlayPoint): boolean => (
  typeof point.width === "number"
  && typeof point.height === "number"
  && point.width > 0
  && point.height > 0
  && point.width <= 0.018
  && point.height <= 0.018
);

const eraseBoxMask = (
  point: BlinkOverlayPoint,
  skinFill: string,
  index: number,
  sharedTop?: number,
  sharedBottom?: number,
  brow?: BlinkOverlayPoint,
): BlinkClosedEyeGeometry["mask"] | null => {
  if (isMinimalistDotEye(point)) {
    const eyeWidth = point.width as number;
    const eyeHeight = point.height as number;
    const maskWidth = clamp(eyeWidth * 100 * 2.6, 2.4, 4.0);
    const maskHeight = clamp(eyeHeight * 100 * 2.2, 2.0, 3.2);
    return {
      x: roundSvgNumber(point.x * 100 - maskWidth / 2),
      y: roundSvgNumber(point.y * 100 - maskHeight / 2),
      width: roundSvgNumber(maskWidth),
      height: roundSvgNumber(maskHeight),
      rx: roundSvgNumber(maskHeight / 2),
      fill: skinFill,
    };
  }

  const box = point.erase_box;
  if (
    typeof box?.left !== "number"
    || typeof box.top !== "number"
    || typeof box.right !== "number"
    || typeof box.bottom !== "number"
    || box.right <= box.left
    || box.bottom <= box.top
  ) {
    return null;
  }
  const boxHeight = box.bottom - box.top;
  const usesBrowInclusiveEraseBox = (
    typeof point.height === "number"
    && point.height > 0
    && boxHeight > point.height * 3
    && box.top < point.y - point.height * 2
  );
  const horizontalBounds = !usesBrowInclusiveEraseBox && typeof point.width === "number" && point.width > 0
    ? {
      left: Math.max(box.left, point.x - point.width * 0.85),
      right: Math.min(box.right, point.x + point.width * 0.85),
    }
    : { left: box.left, right: box.right };
  const resolvedHorizontalBounds = horizontalBounds.right > horizontalBounds.left
    ? horizontalBounds
    : { left: box.left, right: box.right };
  const x = resolvedHorizontalBounds.left * 100;
  const requestedTop = typeof sharedTop === "number" ? sharedTop : box.top;
  const browGap = (
    brow
    && typeof brow.y === "number"
    && typeof point.y === "number"
    && brow.y < point.y
  ) ? point.y - brow.y : null;
  const browAwareTop = brow && typeof brow.y === "number" && browGap !== null
    ? brow.y + browGap * 0.45
    : requestedTop;
  const browSafeTop = brow && typeof brow.y === "number" && browGap !== null
    ? brow.y + browGap * 0.30
    : requestedTop;
  const top = usesBrowInclusiveEraseBox
    ? requestedTop
    : Math.max(Math.min(requestedTop, browAwareTop), browSafeTop);
  const bottom = typeof sharedBottom === "number" ? sharedBottom : box.bottom;
  const y = top * 100;
  const width = (resolvedHorizontalBounds.right - resolvedHorizontalBounds.left) * 100;
  const height = (bottom - top) * 100;
  const sideDistance = colorDistance(point.fill_left, point.fill_right);
  const verticalDistance = colorDistance(point.fill_top, point.fill_bottom);
  const useSideGradient = sideDistance !== null && (verticalDistance === null || sideDistance >= verticalDistance);
  const gradient = useSideGradient ? {
    id: `blink-blink-eye-${index}-gradient`,
    top: point.fill_left as string,
    bottom: point.fill_right as string,
    orientation: "horizontal" as const,
  } : verticalDistance !== null ? {
    id: `blink-blink-eye-${index}-gradient`,
    top: point.fill_top as string,
    bottom: point.fill_bottom as string,
    orientation: "vertical" as const,
  } : undefined;
  return {
    x: roundSvgNumber(x),
    y: roundSvgNumber(y),
    width: roundSvgNumber(width),
    height: roundSvgNumber(height),
    rx: roundSvgNumber(usesBrowInclusiveEraseBox ? Math.min(height * 0.18, width * 0.25) : height / 2),
    fill: gradient ? `url(#${gradient.id})` : skinFill,
    ...(gradient ? { gradient } : {}),
  };
};

export const blinkBlinkEyeOverlayGeometry = (
  anchor: BlinkResolvedOverlayAnchor,
  skinFill = BLINK_FALLBACK_SKIN_FILL,
): BlinkClosedEyeGeometry[] => {
  const leftEye = toSvgPoint(anchor.eye_left);
  const rightEye = toSvgPoint(anchor.eye_right);
  const eyeDistance = Math.abs(rightEye.x - leftEye.x);
  const detectedEyeWidths = [normalizedEyeWidth(anchor.eye_left), normalizedEyeWidth(anchor.eye_right)]
    .filter((width): width is number => width !== null);
  const averageEyeWidth = detectedEyeWidths.length > 0
    ? detectedEyeWidths.reduce((sum, width) => sum + width, 0) / detectedEyeWidths.length
    : null;
  const detectedEyeHeights = [normalizedEyeHeight(anchor.eye_left), normalizedEyeHeight(anchor.eye_right)]
    .filter((height): height is number => height !== null);
  const averageEyeHeight = detectedEyeHeights.length > 0
    ? detectedEyeHeights.reduce((sum, height) => sum + height, 0) / detectedEyeHeights.length
    : null;
  const maskRx = averageEyeWidth === null
    ? clamp(eyeDistance * 0.45, 7.0, 10.5)
    : clamp(averageEyeWidth * 0.65, 3.2, 10.5);
  const maskRy = averageEyeHeight === null
    ? clamp(maskRx * 0.38, 2.4, 4.2)
    : clamp(averageEyeHeight * 1.35, 2.2, 4.2);
  const maskWidth = maskRx * 2;
  const maskHeight = maskRy * 2;
  const lidHalfWidth = maskRx * 0.72;
  const lidLift = maskRy * 0.24;
  const eraseBoxes = [anchor.eye_left.erase_box, anchor.eye_right.erase_box].filter(
    (box): box is NonNullable<BlinkOverlayPoint["erase_box"]> => (
      typeof box?.top === "number"
      && typeof box.bottom === "number"
      && box.bottom > box.top
    ),
  );
  const sharedEraseTop = eraseBoxes.length === 2
    ? Math.min(...eraseBoxes.map((box) => box.top))
    : undefined;
  const sharedEraseBottom = eraseBoxes.length === 2
    ? Math.max(...eraseBoxes.map((box) => box.bottom))
    : undefined;
  return [leftEye, rightEye].map((eye, index) => {
    const sourcePoint = index === 0 ? anchor.eye_left : anchor.eye_right;
    const minimalistDotEye = isMinimalistDotEye(sourcePoint);
    const dotEyeLift = minimalistDotEye && typeof sourcePoint.height === "number"
      ? clamp(sourcePoint.height * 100 * 0.18, 0.12, 0.32)
      : 0;
    const lidY = eye.y - dotEyeLift;
    const resolvedLidHalfWidth = minimalistDotEye && typeof sourcePoint.width === "number"
      ? clamp(sourcePoint.width * 100 * (5 / 6), 0.85, 1.25)
      : lidHalfWidth;
    const resolvedLidLift = minimalistDotEye ? 0 : lidLift;
    const maskY = eye.y + maskRy * 1.02;
    const metadataMask = eraseBoxMask(
      sourcePoint,
      skinFill,
      index,
      sharedEraseTop,
      sharedEraseBottom,
      index === 0 ? anchor.brow_left : anchor.brow_right,
    );
    return {
      mask: metadataMask ?? {
        x: roundSvgNumber(eye.x - maskWidth / 2),
        y: roundSvgNumber(maskY - maskHeight / 2),
        width: roundSvgNumber(maskWidth),
        height: roundSvgNumber(maskHeight),
        rx: roundSvgNumber(maskHeight / 2),
        fill: skinFill,
      },
      lid: {
        d: `M${roundSvgNumber(eye.x - resolvedLidHalfWidth)} ${roundSvgNumber(lidY)} Q${roundSvgNumber(eye.x)} ${roundSvgNumber(lidY - resolvedLidLift)} ${roundSvgNumber(eye.x + resolvedLidHalfWidth)} ${roundSvgNumber(lidY)}`,
        y: roundSvgNumber(lidY),
        stroke: BLINK_EYELID_STROKE,
        strokeWidth: roundSvgNumber(minimalistDotEye ? 0.68 : clamp(maskRx * 0.17, 0.95, 1.3)),
      },
    };
  });
};

const BlinkMicroExpressionOverlay: React.FC<{
  anchor: BlinkResolvedOverlayAnchor;
  overlay: BlinkOverlay;
  visible: boolean;
}> = ({ anchor, overlay, visible }) => {
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
      <svg {...BLINK_OVERLAY_SVG_PROPS} style={common}>
        <ellipse cx={mouth.x} cy={mouth.y - 0.4} rx="4.5" ry="2.4" fill="#F4BE91" />
        <ellipse cx={mouth.x} cy={mouth.y} rx="1.6" ry="2.3" fill="#4B1814" stroke="#111" strokeWidth="0.65" />
      </svg>
    );
  }

  if (overlay.kind === "eyes" && overlay.state === "closed") {
    const eyeGeometry = blinkBlinkEyeOverlayGeometry(anchor, anchor.skin_fill ?? BLINK_FALLBACK_SKIN_FILL);
    const gradients = eyeGeometry
      .map((eye) => eye.mask.gradient)
      .filter((gradient): gradient is NonNullable<BlinkClosedEyeGeometry["mask"]["gradient"]> => Boolean(gradient));
    return (
      <svg {...BLINK_OVERLAY_SVG_PROPS} style={common}>
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
      <svg {...BLINK_OVERLAY_SVG_PROPS} style={common}>
        <ellipse cx={leftEye.x - 1.1} cy={leftEye.y} rx="1.7" ry="2.2" fill="#111" />
        <ellipse cx={rightEye.x - 1.1} cy={rightEye.y} rx="1.7" ry="2.2" fill="#111" />
      </svg>
    );
  }

  return (
    <svg {...BLINK_OVERLAY_SVG_PROPS} style={common}>
      <path d={`M${leftBrow.x - 4.5} ${leftBrow.y} Q${leftBrow.x} ${leftBrow.y - 1.8} ${leftBrow.x + 4.5} ${leftBrow.y - 0.6}`} fill="none" stroke="#111" strokeWidth="1.2" strokeLinecap="round" />
      <path d={`M${rightBrow.x - 4.5} ${rightBrow.y - 0.8} Q${rightBrow.x} ${rightBrow.y - 2.6} ${rightBrow.x + 4.5} ${rightBrow.y - 1.4}`} fill="none" stroke="#111" strokeWidth="1.2" strokeLinecap="round" />
    </svg>
  );
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

export const blinkActiveLayer = (layers: VisualLayer[], frame: number, fps: number, seed = ""): VisualLayer | undefined => {
  const stateLayers = blinkStateLayers(layers);
  if (stateLayers.length === 0) {
    return undefined;
  }
  const blinkWindow = blinkWindowAtFrame(frame, fps, seed);
  const activeIndex = blinkWindow.active
    ? 1 + (blinkWindow.index % Math.max(1, stateLayers.length - 1))
    : 0;
  return stateLayers[activeIndex];
};

export const TreatmentRenderer: React.FC<Props> = ({ scene, fallbackVisualLayer }) => {
  switch (scene.visual_mode) {
    case "popup_sequence":
      return <PopupSequence scene={scene} fallbackVisualLayer={fallbackVisualLayer} />;
    case "blink":
      return <Blink scene={scene} fallbackVisualLayer={fallbackVisualLayer} />;
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
