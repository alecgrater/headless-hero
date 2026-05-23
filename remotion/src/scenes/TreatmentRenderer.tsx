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

const layerFrameStyle = (layer: VisualLayer): React.CSSProperties => {
  if (layer.asset_kind === "full_frame") {
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

const layerChromeStyle = (layer: VisualLayer, scale = 1): React.CSSProperties => ({
  width: "100%",
  height: "100%",
  transform: `scale(${scale})`,
  transformOrigin: "center",
  border: layer.asset_kind === "panel" ? "10px solid #111" : "none",
  boxShadow: layer.asset_kind === "full_frame" ? "none" : "0 24px 60px rgba(0, 0, 0, 0.45)",
  overflow: "hidden",
  backgroundColor: layer.asset_kind === "cutout" ? "transparent" : "#111",
});

const PopupSequence: React.FC<Props> = ({ scene, fallbackVisualLayer }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const layers = validImageLayers(scene);

  logTreatmentOnce(scene, "popup_sequence", layers.length);

  if (layers.length === 0) {
    return <>{fallbackVisualLayer}</>;
  }

  return (
    <div style={{ position: "absolute", inset: 0 }}>
      {layers.map((layer) => {
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
              ...layerFrameStyle(layer),
              opacity,
              transformOrigin: "center",
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

  const layerEnterFrame = (layer: VisualLayer) => Math.round((layer.enter_at_seconds ?? 0) * fps);
  const eligibleLayers = layers.filter((layer) => frame >= layerEnterFrame(layer));
  const activeLayers = eligibleLayers.length > 0 ? eligibleLayers : [layers[0]];
  const intervalFrames = Math.max(1, Math.round(fps * 0.5));
  const latestEnterFrame = Math.max(...activeLayers.map(layerEnterFrame));
  const newestEligibleIndex = Math.max(0, activeLayers.findIndex((layer) => layerEnterFrame(layer) === latestEnterFrame));
  const ticksSinceLatestEntry = Math.floor(Math.max(0, frame - latestEnterFrame) / intervalFrames);
  const activeIndex = activeLayers.length === 1
    ? 0
    : (newestEligibleIndex + ticksSinceLatestEntry) % activeLayers.length;
  const activeLayer = activeLayers[activeIndex];

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

export const TreatmentRenderer: React.FC<Props> = ({ scene, fallbackVisualLayer }) => {
  switch (scene.visual_treatment) {
    case "popup_sequence":
      return <PopupSequence scene={scene} fallbackVisualLayer={fallbackVisualLayer} />;
    case "flipflop":
      return <Flipflop scene={scene} fallbackVisualLayer={fallbackVisualLayer} />;
    case "full_frame":
    default:
      logTreatmentOnce(scene, scene.visual_treatment ?? "full_frame", scene.visual_layers?.length ?? 0);
      return <>{fallbackVisualLayer}</>;
  }
};
