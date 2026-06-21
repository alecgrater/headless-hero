import React from "react";
import type { RendererContext } from "../types";

export const RENDERER_CONTEXT_STAGE_VERSION = "renderer-context-stage-v2";

export const RENDERER_CONTEXTS = [
  "plain",
  "outdoor",
  "desk",
  "classroom",
  "office",
  "kitchen",
  "lab",
] as const satisfies readonly RendererContext[];

const CONTEXTS = new Set<RendererContext>(RENDERER_CONTEXTS);

export interface ContextElement {
  id: string;
  style: React.CSSProperties;
}

export const normalizeRendererContext = (value: unknown): RendererContext => {
  if (typeof value !== "string") return "plain";
  const candidate = value as RendererContext;
  return CONTEXTS.has(candidate) ? candidate : "plain";
};

const lineStyle = (extra: React.CSSProperties): React.CSSProperties => ({
  position: "absolute",
  height: 5,
  borderRadius: 999,
  background: "rgba(16, 18, 20, 0.72)",
  ...extra,
});

const roomBaseElements = (wall = "#9cc7ef", floor = "#89bd7e"): ContextElement[] => [
  {
    id: "wall-fill",
    style: {
      position: "absolute",
      inset: 0,
      background: wall,
    },
  },
  {
    id: "floor-band",
    style: {
      position: "absolute",
      left: 0,
      right: 0,
      bottom: 0,
      height: 250,
      background: floor,
    },
  },
  {
    id: "horizon-line",
    style: lineStyle({
      left: -40,
      right: -40,
      bottom: 248,
      transform: "rotate(-0.6deg)",
    }),
  },
];

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

export const rendererContextElements = (context: unknown): ContextElement[] => {
  const normalized = normalizeRendererContext(context);
  if (normalized === "outdoor") {
    return outdoorElements();
  }

  const elements = roomBaseElements(
    normalized === "plain" ? "#8fc0ee" : "#99c4ec",
    normalized === "plain" ? "#91c987" : "#7fb07b",
  );

  if (normalized === "desk" || normalized === "office" || normalized === "classroom" || normalized === "lab") {
    elements.push({
      id: "desk-band",
      style: {
        position: "absolute",
        left: 260,
        right: 260,
        bottom: 175,
        height: 92,
        borderRadius: "18px 18px 10px 10px",
        borderTop: "5px solid rgba(20, 18, 16, 0.72)",
        background: normalized === "lab" ? "#d2dfe2" : "#8f6848",
      },
    });
  }

  if (normalized === "classroom") {
    elements.push({
      id: "classroom-board",
      style: {
        position: "absolute",
        left: "50%",
        top: 112,
        width: "42%",
        maxWidth: 820,
        height: 235,
        transform: "translateX(-50%)",
        borderRadius: 8,
        border: "5px solid rgba(16, 18, 20, 0.72)",
        background: "#f0e9c9",
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
        border: "5px solid rgba(16, 18, 20, 0.72)",
        background: "#b7d7ef",
      },
    });
  }

  if (normalized === "kitchen") {
    elements.push({
      id: "kitchen-counter",
      style: {
        position: "absolute",
        left: 180,
        right: 180,
        bottom: 190,
        height: 105,
        borderRadius: "18px 18px 10px 10px",
        borderTop: "5px solid rgba(16, 18, 20, 0.72)",
        background: "#b4865f",
      },
    });
    elements.push({
      id: "kitchen-shelf",
      style: lineStyle({
        left: 430,
        right: 430,
        top: 185,
      }),
    });
  }

  if (normalized === "lab") {
    elements.push({
      id: "lab-flask",
      style: {
        position: "absolute",
        right: 485,
        bottom: 272,
        width: 58,
        height: 76,
        borderRadius: "8px 8px 24px 24px",
        border: "5px solid rgba(16, 18, 20, 0.72)",
        background: "#bfe5e2",
      },
    });
  }

  if (normalized === "desk") {
    elements.push({
      id: "desk-paper",
      style: {
        position: "absolute",
        left: 500,
        bottom: 288,
        width: 120,
        height: 72,
        borderRadius: 6,
        border: "4px solid rgba(16, 18, 20, 0.68)",
        background: "#f4f0da",
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
