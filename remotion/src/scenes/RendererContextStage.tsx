import React from "react";
import type { RendererContext } from "../types";

export const RENDERER_CONTEXT_STAGE_VERSION = "renderer-context-stage-v1";

const CONTEXTS = new Set(["plain", "desk", "classroom", "office", "kitchen", "shop", "lab", "street"]);

export interface ContextElement {
  id: string;
  style: React.CSSProperties;
}

export const normalizeRendererContext = (value: unknown): RendererContext => (
  typeof value === "string" && CONTEXTS.has(value) ? value as RendererContext : "plain"
);

const baseElements = (): ContextElement[] => [
  {
    id: "wall-wash",
    style: {
      position: "absolute",
      inset: 0,
      background: "linear-gradient(180deg, rgba(255,255,255,0.16), rgba(0,0,0,0.08))",
    },
  },
  {
    id: "floor-band",
    style: {
      position: "absolute",
      left: 0,
      right: 0,
      bottom: 0,
      height: 260,
      background: "rgba(0,0,0,0.14)",
    },
  },
];

export const rendererContextElements = (context: unknown): ContextElement[] => {
  const normalized = normalizeRendererContext(context);
  const elements = baseElements();

  if (normalized === "desk" || normalized === "office" || normalized === "classroom") {
    elements.push({
      id: "desk-band",
      style: {
        position: "absolute",
        left: 250,
        right: 250,
        bottom: 155,
        height: 88,
        borderRadius: 18,
        background: "rgba(88, 60, 36, 0.34)",
      },
    });
  }

  if (normalized === "classroom") {
    elements.push({
      id: "classroom-board",
      style: {
        position: "absolute",
        left: 560,
        right: 560,
        top: 112,
        height: 235,
        borderRadius: 10,
        border: "10px solid rgba(80, 55, 36, 0.5)",
        background: "rgba(246, 241, 219, 0.62)",
      },
    });
  }

  if (normalized === "office") {
    elements.push({
      id: "office-window",
      style: {
        position: "absolute",
        right: 360,
        top: 130,
        width: 250,
        height: 220,
        borderRadius: 8,
        background: "rgba(160, 200, 215, 0.26)",
      },
    });
  }

  if (normalized === "kitchen" || normalized === "shop") {
    elements.push({
      id: `${normalized}-counter`,
      style: {
        position: "absolute",
        left: 180,
        right: 180,
        bottom: 190,
        height: 105,
        borderRadius: 16,
        background: "rgba(126, 91, 58, 0.38)",
      },
    });
  }

  if (normalized === "lab") {
    elements.push({
      id: "lab-bench",
      style: {
        position: "absolute",
        left: 220,
        right: 220,
        bottom: 180,
        height: 95,
        borderRadius: 16,
        background: "rgba(210, 226, 230, 0.32)",
      },
    });
  }

  if (normalized === "street") {
    elements.push({
      id: "street-horizon",
      style: {
        position: "absolute",
        left: 0,
        right: 0,
        bottom: 260,
        height: 80,
        background: "rgba(70, 80, 90, 0.18)",
      },
    });
  }

  return elements;
};

export const RendererContextStage: React.FC<{ context?: RendererContext }> = ({ context }) => (
  <div style={{ position: "absolute", inset: 0, overflow: "hidden", pointerEvents: "none" }}>
    {rendererContextElements(context).map((element) => (
      <div key={element.id} style={element.style} />
    ))}
  </div>
);
