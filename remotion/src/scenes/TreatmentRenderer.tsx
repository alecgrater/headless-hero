import React from "react";
import { Img, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { SceneInput, VisualLayer } from "../types";

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

const Flipflop: React.FC<Props> = ({ scene, fallbackVisualLayer }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const layers = validImageLayers(scene);

  logTreatmentOnce(scene, "flipflop", layers.length);

  if (layers.length === 0) {
    return <>{fallbackVisualLayer}</>;
  }

  const activeLayer = flipflopActiveLayer(layers, frame, fps);
  if (!activeLayer) {
    return <>{fallbackVisualLayer}</>;
  }

  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <div style={layerFrameStyle(activeLayer)}>
        <div style={layerChromeStyle(activeLayer)}>
          <Img
            src={activeLayer.image_path ?? ""}
            style={layerImageStyle(activeLayer)}
          />
        </div>
      </div>
    </div>
  );
};

export const flipflopActiveLayer = (layers: VisualLayer[], frame: number, fps: number): VisualLayer | undefined => {
  if (layers.length === 0) {
    return undefined;
  }
  const intervalFrames = Math.max(1, Math.round(fps * 0.5));
  const activeIndex = Math.floor(Math.max(0, frame) / intervalFrames) % layers.length;
  return layers[activeIndex];
};

export const TreatmentRenderer: React.FC<Props> = ({ scene, fallbackVisualLayer }) => {
  switch (scene.visual_mode) {
    case "popup_sequence":
      return <PopupSequence scene={scene} fallbackVisualLayer={fallbackVisualLayer} />;
    case "flipflop":
      return <Flipflop scene={scene} fallbackVisualLayer={fallbackVisualLayer} />;
    case "full_frame":
    default:
      logTreatmentOnce(scene, scene.visual_mode ?? "full_frame", scene.visual_layers?.length ?? 0);
      return <>{fallbackVisualLayer}</>;
  }
};
