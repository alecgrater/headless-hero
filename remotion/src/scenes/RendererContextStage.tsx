import React from "react";
import type { RendererContext } from "../types";

export const RENDERER_CONTEXT_STAGE_VERSION = "renderer-context-stage-v3";

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

const roomBaseElements = (
  prefix: string,
  wall: string,
  floor: string,
  horizonBottom = 248,
): ContextElement[] => [
  {
    id: `${prefix}-wall-fill`,
    style: {
      position: "absolute",
      inset: 0,
      background: wall,
    },
  },
  {
    id: `${prefix}-floor-band`,
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
    id: `${prefix}-horizon-line`,
    style: lineStyle({
      left: -40,
      right: -40,
      bottom: horizonBottom,
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

const deskElements = (): ContextElement[] => [
  ...roomBaseElements("desk", "#f0d2a6", "#c7965c", 265),
  {
    id: "desk-surface",
    style: {
      position: "absolute",
      left: 120,
      right: 120,
      bottom: 205,
      height: 125,
      borderRadius: "18px 18px 10px 10px",
      borderTop: "6px solid rgba(16, 18, 20, 0.72)",
      background: "#8d5e3d",
    },
  },
  {
    id: "desk-laptop",
    style: {
      position: "absolute",
      left: 410,
      bottom: 330,
      width: 210,
      height: 125,
      borderRadius: "10px 10px 4px 4px",
      border: "5px solid rgba(16, 18, 20, 0.72)",
      background: "#b8c9d3",
    },
  },
  {
    id: "desk-book-stack",
    style: {
      position: "absolute",
      right: 430,
      bottom: 332,
      width: 160,
      height: 42,
      borderRadius: 8,
      border: "5px solid rgba(16, 18, 20, 0.72)",
      background: "#f0e9c9",
    },
  },
  {
    id: "desk-lamp",
    style: {
      position: "absolute",
      right: 635,
      bottom: 333,
      width: 90,
      height: 90,
      borderRadius: "999px 999px 24px 24px",
      border: "5px solid rgba(16, 18, 20, 0.72)",
      background: "#f7dc73",
    },
  },
];

const classroomElements = (): ContextElement[] => [
  ...roomBaseElements("classroom", "#cfe2bb", "#b58b5e", 235),
  {
    id: "classroom-board",
    style: {
      position: "absolute",
      left: "50%",
      top: 105,
      width: "54%",
      maxWidth: 980,
      height: 285,
      transform: "translateX(-50%)",
      borderRadius: 8,
      border: "6px solid rgba(16, 18, 20, 0.72)",
      background: "#527d65",
    },
  },
  {
    id: "classroom-chalk-rail",
    style: lineStyle({
      left: 520,
      right: 520,
      top: 394,
      height: 8,
      background: "rgba(16, 18, 20, 0.58)",
    }),
  },
  {
    id: "classroom-desk-left",
    style: {
      position: "absolute",
      left: 185,
      bottom: 150,
      width: 335,
      height: 86,
      borderRadius: "16px 16px 8px 8px",
      borderTop: "5px solid rgba(16, 18, 20, 0.72)",
      background: "#a6784a",
    },
  },
  {
    id: "classroom-desk-right",
    style: {
      position: "absolute",
      right: 185,
      bottom: 150,
      width: 335,
      height: 86,
      borderRadius: "16px 16px 8px 8px",
      borderTop: "5px solid rgba(16, 18, 20, 0.72)",
      background: "#a6784a",
    },
  },
];

const officeElements = (): ContextElement[] => [
  ...roomBaseElements("office", "#c7d8e4", "#a8aaac", 250),
  {
    id: "office-window",
    style: {
      position: "absolute",
      right: 300,
      top: 115,
      width: 330,
      height: 270,
      borderRadius: 10,
      border: "6px solid rgba(16, 18, 20, 0.72)",
      background: "#9cc7ef",
    },
  },
  {
    id: "office-desk",
    style: {
      position: "absolute",
      left: 170,
      right: 450,
      bottom: 190,
      height: 110,
      borderRadius: "18px 18px 10px 10px",
      borderTop: "6px solid rgba(16, 18, 20, 0.72)",
      background: "#7a5d46",
    },
  },
  {
    id: "office-monitor",
    style: {
      position: "absolute",
      left: 430,
      bottom: 308,
      width: 240,
      height: 150,
      borderRadius: 10,
      border: "6px solid rgba(16, 18, 20, 0.72)",
      background: "#2f3e47",
    },
  },
  {
    id: "office-plant",
    style: {
      position: "absolute",
      right: 245,
      bottom: 230,
      width: 115,
      height: 180,
      borderRadius: "60px 60px 24px 24px",
      border: "5px solid rgba(16, 18, 20, 0.72)",
      background: "#5f9a67",
    },
  },
];

const kitchenElements = (): ContextElement[] => [
  ...roomBaseElements("kitchen", "#f2c08f", "#c77f54", 255),
  {
    id: "kitchen-cabinets",
    style: {
      position: "absolute",
      left: 170,
      right: 170,
      top: 88,
      height: 180,
      borderRadius: 12,
      border: "6px solid rgba(16, 18, 20, 0.72)",
      background: "#d8a15f",
    },
  },
  {
    id: "kitchen-backsplash",
    style: {
      position: "absolute",
      left: 120,
      right: 120,
      bottom: 295,
      height: 165,
      borderTop: "5px solid rgba(16, 18, 20, 0.48)",
      borderBottom: "5px solid rgba(16, 18, 20, 0.48)",
      background: "#f1e1bb",
    },
  },
  {
    id: "kitchen-counter",
    style: {
      position: "absolute",
      left: 105,
      right: 105,
      bottom: 215,
      height: 120,
      borderRadius: "18px 18px 10px 10px",
      borderTop: "6px solid rgba(16, 18, 20, 0.72)",
      background: "#9b6847",
    },
  },
  {
    id: "kitchen-fridge",
    style: {
      position: "absolute",
      right: 165,
      bottom: 335,
      width: 205,
      height: 305,
      borderRadius: 14,
      border: "6px solid rgba(16, 18, 20, 0.72)",
      background: "#cbd9d7",
    },
  },
];

const labElements = (): ContextElement[] => [
  ...roomBaseElements("lab", "#cde5e9", "#9db5b5", 245),
  {
    id: "lab-shelf",
    style: lineStyle({
      left: 320,
      right: 320,
      top: 155,
      height: 8,
    }),
  },
  {
    id: "lab-bench",
    style: {
      position: "absolute",
      left: 130,
      right: 130,
      bottom: 205,
      height: 120,
      borderRadius: "18px 18px 10px 10px",
      borderTop: "6px solid rgba(16, 18, 20, 0.72)",
      background: "#d7e0df",
    },
  },
  {
    id: "lab-flask",
    style: {
      position: "absolute",
      left: 530,
      bottom: 330,
      width: 86,
      height: 115,
      borderRadius: "12px 12px 38px 38px",
      border: "6px solid rgba(16, 18, 20, 0.72)",
      background: "#a8ddd6",
    },
  },
  {
    id: "lab-microscope",
    style: {
      position: "absolute",
      right: 455,
      bottom: 330,
      width: 150,
      height: 155,
      borderRadius: "70px 70px 18px 18px",
      border: "6px solid rgba(16, 18, 20, 0.72)",
      background: "#7f8f97",
    },
  },
];

export const rendererContextElements = (context: unknown): ContextElement[] => {
  const normalized = normalizeRendererContext(context);
  if (normalized === "outdoor") {
    return outdoorElements();
  }
  if (normalized === "desk") {
    return deskElements();
  }
  if (normalized === "classroom") {
    return classroomElements();
  }
  if (normalized === "office") {
    return officeElements();
  }
  if (normalized === "kitchen") {
    return kitchenElements();
  }
  if (normalized === "lab") {
    return labElements();
  }
  return outdoorElements();
};

export const RendererContextStage: React.FC<{ context?: RendererContext }> = ({ context }) => (
  <div style={{ position: "absolute", inset: 0, overflow: "hidden", pointerEvents: "none" }}>
    {rendererContextElements(context).map((element) => (
      <div key={element.id} style={element.style} />
    ))}
  </div>
);
