import React from "react";
import { Img, interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import type { SceneInput, VisualLayer } from "../types";
import { layerChromeStyle } from "./TreatmentRenderer";

interface Props {
  scene: SceneInput;
  fallbackVisualLayer: React.ReactNode;
}

const VIEWPORT_WIDTH = 1920;
const VIEWPORT_HEIGHT = 1080;

const validImageLayers = (scene: SceneInput): VisualLayer[] =>
  (scene.visual_layers ?? []).filter((layer) => layer.type === "image" && layer.image_path);

const isAnchorLayer = (layer: VisualLayer): boolean =>
  layer.id.endsWith("_anchor") || (layer.placement === "center" && (layer.animation === "none" || !layer.animation));

const seededRotation = (id: string): number => {
  let hash = 0;
  for (let i = 0; i < id.length; i += 1) {
    hash = (hash * 31 + id.charCodeAt(i)) | 0;
  }
  // Range: -8deg .. +8deg, deterministic per layer id.
  return ((Math.abs(hash) % 1600) / 100) - 8;
};

const seededOffset = (id: string, salt: string, range: number): number => {
  let hash = 0;
  const seed = `${id}:${salt}`;
  for (let i = 0; i < seed.length; i += 1) {
    hash = (hash * 31 + seed.charCodeAt(i)) | 0;
  }
  // Deterministic offset in [-range/2, +range/2].
  return ((Math.abs(hash) % 1000) / 1000 - 0.5) * range;
};

const ANCHOR_POSITIONS = {
  width: 520,
  height: 620,
  left: VIEWPORT_WIDTH / 2,
  top: VIEWPORT_HEIGHT / 2 + 30,
};

const EVIDENCE_GRID = {
  "top-left":      { left: 320,  top: 240 },
  "top-center":    { left: 960,  top: 200 },
  "top-right":     { left: 1600, top: 240 },
  "bottom-left":   { left: 320,  top: 820 },
  "bottom-center": { left: 960,  top: 880 },
  "bottom-right":  { left: 1600, top: 820 },
} as const;

const EVIDENCE_FALLBACK_ORDER: (keyof typeof EVIDENCE_GRID)[] = [
  "top-left",
  "top-right",
  "bottom-left",
  "bottom-right",
  "top-center",
  "bottom-center",
];

const NETWORK_RING_RADIUS_X = 640;
const NETWORK_RING_RADIUS_Y = 320;
const NETWORK_CENTER_X = VIEWPORT_WIDTH / 2;
const NETWORK_CENTER_Y = VIEWPORT_HEIGHT / 2 + 30;

const evidencePosition = (layer: VisualLayer, fallbackIndex: number): { left: number; top: number } => {
  const placement = (layer.placement ?? "").replace(/_/g, "-") as keyof typeof EVIDENCE_GRID;
  if (EVIDENCE_GRID[placement]) {
    return EVIDENCE_GRID[placement];
  }
  const fallback = EVIDENCE_FALLBACK_ORDER[fallbackIndex % EVIDENCE_FALLBACK_ORDER.length];
  return EVIDENCE_GRID[fallback];
};

const networkPosition = (
  index: number,
  count: number,
  layerId: string,
): { left: number; top: number } => {
  const angle = (Math.PI * 2 * index) / Math.max(1, count) - Math.PI / 2;
  const jitterX = seededOffset(layerId, "x", 60);
  const jitterY = seededOffset(layerId, "y", 60);
  return {
    left: NETWORK_CENTER_X + Math.cos(angle) * NETWORK_RING_RADIUS_X + jitterX,
    top: NETWORK_CENTER_Y + Math.sin(angle) * NETWORK_RING_RADIUS_Y + jitterY,
  };
};

interface DossierLayerPlacement {
  layer: VisualLayer;
  isAnchor: boolean;
  left: number;
  top: number;
  width: number;
  height: number;
}

const computePlacements = (scene: SceneInput): DossierLayerPlacement[] => {
  const layers = validImageLayers(scene);
  if (layers.length === 0) {
    return [];
  }
  const layout = scene.dossier_layout === "network" ? "network" : "anchor";

  if (layout === "anchor") {
    const anchorIndex = layers.findIndex((layer) => isAnchorLayer(layer));
    const safeAnchorIndex = anchorIndex >= 0 ? anchorIndex : 0;
    const anchor = layers[safeAnchorIndex];
    const evidence = layers.filter((_, idx) => idx !== safeAnchorIndex);
    return [
      anchor && {
        layer: anchor,
        isAnchor: true,
        left: ANCHOR_POSITIONS.left,
        top: ANCHOR_POSITIONS.top,
        width: ANCHOR_POSITIONS.width,
        height: ANCHOR_POSITIONS.height,
      },
      ...evidence.map((layer, evIndex) => {
        const pos = evidencePosition(layer, evIndex);
        return {
          layer,
          isAnchor: false,
          left: pos.left,
          top: pos.top,
          width: 360,
          height: 360,
        };
      }),
    ].filter(Boolean) as DossierLayerPlacement[];
  }

  return layers.map((layer, index) => {
    const pos = networkPosition(index, layers.length, layer.id);
    return {
      layer,
      isAnchor: false,
      left: pos.left,
      top: pos.top,
      width: 380,
      height: 380,
    };
  });
};

const StringConnections: React.FC<{
  placements: DossierLayerPlacement[];
  scene: SceneInput;
}> = ({ placements, scene }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const layout = scene.dossier_layout === "network" ? "network" : "anchor";

  if (placements.length < 2) {
    return null;
  }

  const edges: { from: DossierLayerPlacement; to: DossierLayerPlacement; enterAt: number }[] = [];
  if (layout === "anchor") {
    const anchor = placements.find((p) => p.isAnchor);
    if (!anchor) {
      return null;
    }
    for (const placement of placements) {
      if (placement === anchor) continue;
      edges.push({ from: anchor, to: placement, enterAt: placement.layer.enter_at_seconds ?? 0 });
    }
  } else {
    // For 2 placements, draw a single edge to avoid overdrawn duplicate strings.
    const limit = placements.length === 2 ? 1 : placements.length;
    for (let i = 0; i < limit; i += 1) {
      const next = placements[(i + 1) % placements.length];
      edges.push({
        from: placements[i],
        to: next,
        enterAt: Math.max(placements[i].layer.enter_at_seconds ?? 0, next.layer.enter_at_seconds ?? 0),
      });
    }
  }

  return (
    <svg
      viewBox={`0 0 ${VIEWPORT_WIDTH} ${VIEWPORT_HEIGHT}`}
      style={{ position: "absolute", inset: 0, pointerEvents: "none", zIndex: 5 }}
    >
      {edges.map((edge, index) => {
        const enterFrame = Math.round(edge.enterAt * fps);
        const progress = interpolate(frame, [enterFrame, enterFrame + 18], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        const x1 = edge.from.left;
        const y1 = edge.from.top;
        const x2 = x1 + (edge.to.left - x1) * progress;
        const y2 = y1 + (edge.to.top - y1) * progress;
        return (
          <line
            key={`${edge.from.layer.id}-${edge.to.layer.id}-${index}`}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            stroke="#C0392B"
            strokeWidth={6}
            strokeLinecap="round"
            opacity={0.85}
          />
        );
      })}
    </svg>
  );
};

const StickyLabel: React.FC<{ label: string }> = ({ label }) => (
  <div
    style={{
      position: "absolute",
      bottom: -52,
      left: "50%",
      transform: "translateX(-50%) rotate(-2deg)",
      padding: "6px 16px",
      background: "#FEF3A2",
      color: "#0F172A",
      fontFamily: "Arial Black, Arial, sans-serif",
      fontSize: 22,
      letterSpacing: 1,
      textTransform: "uppercase",
      boxShadow: "0 4px 14px rgba(0, 0, 0, 0.45)",
      whiteSpace: "nowrap",
      maxWidth: 320,
      overflow: "hidden",
      textOverflow: "ellipsis",
      zIndex: 30,
    }}
  >
    {label}
  </div>
);

const Pushpin: React.FC<{ rotation: number }> = ({ rotation }) => (
  <div
    style={{
      position: "absolute",
      top: -10,
      left: "50%",
      transform: `translateX(-50%) rotate(${rotation}deg)`,
      width: 24,
      height: 24,
      borderRadius: "50%",
      background: "radial-gradient(circle at 35% 30%, #FF6B6B 0%, #B22222 70%, #5A0E0E 100%)",
      boxShadow: "0 3px 5px rgba(0, 0, 0, 0.6)",
      zIndex: 25,
    }}
  />
);

const TapeStrip: React.FC<{ rotation: number }> = ({ rotation }) => (
  <div
    style={{
      position: "absolute",
      top: -18,
      left: "50%",
      transform: `translateX(-50%) rotate(${rotation}deg)`,
      width: 90,
      height: 28,
      background: "rgba(255, 235, 130, 0.78)",
      border: "1px solid rgba(255, 220, 100, 0.55)",
      boxShadow: "0 2px 6px rgba(0, 0, 0, 0.35)",
      zIndex: 24,
    }}
  />
);

const CaseHeader: React.FC<{ title: string }> = ({ title }) => (
  <div
    style={{
      position: "absolute",
      top: 50,
      left: "50%",
      transform: "translateX(-50%)",
      padding: "14px 38px",
      background: "#0F172A",
      color: "#F6C54A",
      fontFamily: "Impact, Arial Black, sans-serif",
      fontSize: 46,
      letterSpacing: 4,
      textTransform: "uppercase",
      border: "4px solid #F6C54A",
      boxShadow: "0 6px 18px rgba(0, 0, 0, 0.55)",
      zIndex: 60,
    }}
  >
    {title}
  </div>
);

export const DossierBoard: React.FC<Props> = ({ scene, fallbackVisualLayer }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const placements = computePlacements(scene);

  if (placements.length === 0) {
    return <>{fallbackVisualLayer}</>;
  }

  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}>
      {/* Cork-board surface — CSS-only texture so we don't depend on a bundled asset. */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(ellipse at center, #C49767 0%, #9B7042 65%, #6B4A26 100%)",
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          opacity: 0.18,
          backgroundImage:
            "radial-gradient(circle at 25% 35%, rgba(0, 0, 0, 0.4) 0%, transparent 28%)," +
            "radial-gradient(circle at 70% 60%, rgba(0, 0, 0, 0.35) 0%, transparent 26%)," +
            "radial-gradient(circle at 50% 80%, rgba(0, 0, 0, 0.3) 0%, transparent 22%)",
        }}
      />

      <StringConnections placements={placements} scene={scene} />

      {placements.map((placement, index) => {
        const enterFrame = Math.round((placement.layer.enter_at_seconds ?? 0) * fps);
        const opacity = interpolate(frame, [enterFrame, enterFrame + 10], [0, 1], {
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        });
        const popScale = placement.layer.animation === "pop_in"
          ? spring({
              frame: Math.max(0, frame - enterFrame),
              fps,
              config: { damping: 14, mass: 0.7, stiffness: 180 },
            })
          : 1;
        const scale = placement.layer.animation === "pop_in"
          ? interpolate(popScale, [0, 1], [0.86, 1], {
              extrapolateLeft: "clamp",
              extrapolateRight: "clamp",
            })
          : 1;
        const tilt = placement.isAnchor ? 0 : seededRotation(placement.layer.id);
        const useTape = !placement.isAnchor && index % 2 === 1;
        return (
          <div
            key={placement.layer.id}
            style={{
              position: "absolute",
              left: placement.left,
              top: placement.top,
              width: placement.width,
              height: placement.height,
              transform: `translate(-50%, -50%) rotate(${tilt}deg) scale(${scale})`,
              transformOrigin: "center",
              opacity,
              zIndex: 10 + index,
            }}
          >
            {useTape ? (
              <TapeStrip rotation={tilt > 0 ? -6 : 6} />
            ) : (
              !placement.isAnchor && <Pushpin rotation={tilt > 0 ? -8 : 8} />
            )}
            <div
              style={{
                ...layerChromeStyle(placement.layer, 1),
                width: "100%",
                height: "100%",
                position: "relative",
              }}
            >
              <Img
                src={placement.layer.image_path ?? ""}
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "contain",
                  display: "block",
                }}
              />
            </div>
            {placement.layer.label ? <StickyLabel label={placement.layer.label} /> : null}
          </div>
        );
      })}

      {scene.dossier_title ? <CaseHeader title={scene.dossier_title} /> : null}
    </div>
  );
};
