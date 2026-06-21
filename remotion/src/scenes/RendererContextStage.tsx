import React from "react";
import type { RendererContext } from "../types";

export const RENDERER_CONTEXT_STAGE_VERSION = "renderer-context-stage-v4";

export const RENDERER_CONTEXTS = [
  "outdoor",
  "indoor",
] as const satisfies readonly RendererContext[];

const CONTEXTS = new Set<RendererContext>(RENDERER_CONTEXTS);
const LEGACY_INDOOR_CONTEXTS = new Set([
  "desk",
  "classroom",
  "office",
  "kitchen",
  "lab",
]);

export interface ContextElement {
  id: string;
  style: React.CSSProperties;
}

export const normalizeRendererContext = (value: unknown): RendererContext => {
  if (typeof value !== "string") return "outdoor";
  const candidate = value as RendererContext;
  if (CONTEXTS.has(candidate)) return candidate;
  return LEGACY_INDOOR_CONTEXTS.has(value) ? "indoor" : "outdoor";
};

const lineStyle = (extra: React.CSSProperties): React.CSSProperties => ({
  position: "absolute",
  height: 5,
  borderRadius: 999,
  background: "rgba(16, 18, 20, 0.72)",
  ...extra,
});

const outdoorElements = (): ContextElement[] => [
  {
    id: "sky-fill",
    style: {
      position: "absolute",
      inset: 0,
      background: "#8fc0ee",
    },
  },
  {
    id: "grass-band",
    style: {
      position: "absolute",
      left: 0,
      right: 0,
      bottom: 0,
      height: 255,
      background: "#91c987",
    },
  },
  {
    id: "horizon-line",
    style: lineStyle({
      left: -60,
      right: -60,
      bottom: 252,
      transform: "rotate(-0.8deg)",
    }),
  },
];

const indoorElements = (): ContextElement[] => [
  {
    id: "indoor-wall-fill",
    style: {
      position: "absolute",
      inset: 0,
      background: "#d8c8ad",
    },
  },
  {
    id: "indoor-floor-band",
    style: {
      position: "absolute",
      left: 0,
      right: 0,
      bottom: 0,
      height: 255,
      background: "#b69a75",
    },
  },
  {
    id: "indoor-horizon-line",
    style: lineStyle({
      left: -60,
      right: -60,
      bottom: 252,
      transform: "rotate(-0.8deg)",
    }),
  },
  {
    id: "indoor-window-frame",
    style: {
      position: "absolute",
      right: 290,
      top: 125,
      width: 360,
      height: 250,
      borderRadius: 8,
      border: "6px solid rgba(16, 18, 20, 0.72)",
      background: "#9ac5ec",
    },
  },
  {
    id: "indoor-window-vertical-pane",
    style: lineStyle({
      right: 467,
      top: 130,
      width: 5,
      height: 240,
      borderRadius: 0,
    }),
  },
  {
    id: "indoor-window-horizontal-pane",
    style: lineStyle({
      right: 295,
      top: 247,
      width: 350,
      height: 5,
      borderRadius: 0,
    }),
  },
];

export const rendererContextElements = (context: unknown): ContextElement[] =>
  normalizeRendererContext(context) === "indoor" ? indoorElements() : outdoorElements();

export const RendererContextStage: React.FC<{ context?: RendererContext }> = ({ context }) => (
  <div style={{ position: "absolute", inset: 0, overflow: "hidden", pointerEvents: "none" }}>
    {rendererContextElements(context).map((element) => (
      <div key={element.id} style={element.style} />
    ))}
  </div>
);
