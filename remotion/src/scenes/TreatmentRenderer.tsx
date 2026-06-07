import React from "react";
import { Img, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { SceneInput, VisualLayer } from "../types";
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

export const flipflopLayerFrameStyle = (layer: VisualLayer): React.CSSProperties => {
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
  const backgroundLayers = flipflopBackgroundLayers(layers);
  const stateLayers = flipflopStateLayers(layers);

  logTreatmentOnce(scene, "flipflop", layers.length);

  if (stateLayers.length === 0) {
    return <>{fallbackVisualLayer}</>;
  }

  const activeLayer = flipflopActiveLayer(stateLayers, frame, fps);
  if (!activeLayer) {
    return <>{fallbackVisualLayer}</>;
  }

  return (
    <div style={{ position: "absolute", inset: 0 }}>
      {backgroundLayers.map((layer) => (
        <div key={layer.id} style={layerFrameStyle(layer)}>
          <div style={layerChromeStyle(layer)}>
            <Img
              src={layer.image_path ?? ""}
              style={layerImageStyle(layer)}
            />
          </div>
        </div>
      ))}
      <div style={flipflopLayerFrameStyle(activeLayer)}>
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

export const flipflopBackgroundLayers = (layers: VisualLayer[]): VisualLayer[] => (
  layers.filter((layer) => layer.asset_kind === "full_frame" || layer.asset_kind === "panel")
);

export const flipflopStateLayers = (layers: VisualLayer[]): VisualLayer[] => (
  layers.filter((layer) => layer.asset_kind === "cutout")
);

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

export const flipflopActiveLayer = (layers: VisualLayer[], frame: number, fps: number): VisualLayer | undefined => {
  const stateLayers = flipflopStateLayers(layers);
  if (stateLayers.length === 0) {
    return undefined;
  }
  const intervalFrames = Math.max(1, Math.round(fps * 0.5));
  const activeIndex = Math.floor(Math.max(0, frame) / intervalFrames) % stateLayers.length;
  return stateLayers[activeIndex];
};

export const TreatmentRenderer: React.FC<Props> = ({ scene, fallbackVisualLayer }) => {
  switch (scene.visual_mode) {
    case "popup_sequence":
      return <PopupSequence scene={scene} fallbackVisualLayer={fallbackVisualLayer} />;
    case "flipflop":
      return <Flipflop scene={scene} fallbackVisualLayer={fallbackVisualLayer} />;
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
