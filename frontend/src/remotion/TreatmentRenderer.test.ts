import { describe, expect, it } from "vitest";
import type React from "react";

import {
  comparisonBoardLayerStyle,
  BLINK_OVERLAY_SVG_PROPS,
  comparisonLabel,
  blinkActiveLayer,
  blinkOverlayAnchor,
  blinkMicroOverlay,
  blinkBlinkEyeOverlayGeometry,
  blinkOverlayVisible,
  blinkLayerFrameStyle,
  layerChromeStyle,
  layerFrameStyle,
  popupOrbitFrameStyle,
} from "@remotion-src/scenes/TreatmentRenderer";
import {
  RENDERER_CONTEXTS,
  RENDERER_CONTEXT_STAGE_VERSION,
  normalizeRendererContext,
  rendererContextElements,
} from "@remotion-src/scenes/RendererContextStage";
import { StatCard } from "@remotion-src/scenes/StatCard";
import type { VisualLayer } from "@remotion-src/types";

const itemLayer = (id: string): VisualLayer => ({
  id,
  type: "image",
  asset_kind: "cutout",
  image_path: `/tmp/${id}.png`,
  animation: "pop_in",
});

const panelLayer = (id: string): VisualLayer => ({
  id,
  type: "image",
  asset_kind: "panel",
  image_path: `/tmp/${id}.png`,
  animation: "pop_in",
});

describe("popupOrbitFrameStyle", () => {
  it("keeps the anchor centered while item cutouts orbit clockwise", () => {
    const layers = [
      { ...itemLayer("anchor"), animation: "none" as const },
      itemLayer("bubble-1"),
      itemLayer("bubble-2"),
      itemLayer("bubble-3"),
    ];

    const anchor = popupOrbitFrameStyle(layers[0], {
      layerIndex: 0,
      itemIndex: -1,
      itemCount: 3,
      frame: 30,
      fps: 30,
    });
    const firstAtStart = popupOrbitFrameStyle(layers[1], {
      layerIndex: 1,
      itemIndex: 0,
      itemCount: 3,
      frame: 0,
      fps: 30,
    });
    const firstLater = popupOrbitFrameStyle(layers[1], {
      layerIndex: 1,
      itemIndex: 0,
      itemCount: 3,
      frame: 30,
      fps: 30,
    });
    const secondAtStart = popupOrbitFrameStyle(layers[2], {
      layerIndex: 2,
      itemIndex: 1,
      itemCount: 3,
      frame: 0,
      fps: 30,
    });
    const secondLater = popupOrbitFrameStyle(layers[2], {
      layerIndex: 2,
      itemIndex: 1,
      itemCount: 3,
      frame: 30,
      fps: 30,
    });
    const thirdLater = popupOrbitFrameStyle(layers[3], {
      layerIndex: 3,
      itemIndex: 2,
      itemCount: 3,
      frame: 30,
      fps: 30,
    });

    expect(anchor.left).toBe("50%");
    expect(anchor.top).toBe("50%");
    expect(anchor.transform).toBe("translate(-50%, -50%)");

    expect(firstAtStart.left).toBeGreaterThan(960);
    expect(firstLater.top).toBeGreaterThan(firstAtStart.top as number);
    expect(firstLater.left).toBeLessThan(firstAtStart.left as number);
    expect(secondAtStart.left).toBeLessThan(960);
    expect(secondAtStart.top).toBeGreaterThan(540);

    const center = { x: 960, y: 540 };
    const radius = { x: 430, y: 260 };
    const angleFor = (style: React.CSSProperties) => Math.atan2(
      ((style.top as number) - center.y) / radius.y,
      ((style.left as number) - center.x) / radius.x,
    );
    const positiveDelta = (from: number, to: number) => (
      (to - from + Math.PI * 2) % (Math.PI * 2)
    );
    const firstAngle = angleFor(firstLater);
    const secondAngle = angleFor(secondLater);
    const thirdAngle = angleFor(thirdLater);
    const expectedSpacing = (Math.PI * 2) / 3;

    expect(positiveDelta(firstAngle, secondAngle)).toBeCloseTo(expectedSpacing, 5);
    expect(positiveDelta(secondAngle, thirdAngle)).toBeCloseTo(expectedSpacing, 5);
  });
});

describe("layerChromeStyle", () => {
  it("anchors cutout overlays to the cutout image frame", () => {
    expect(layerChromeStyle(itemLayer("cutout"))).toMatchObject({
      position: "relative",
      width: "100%",
      height: "100%",
    });
  });
});

describe("RendererContextStage", () => {
  it("normalizes unknown contexts to plain", () => {
    expect(normalizeRendererContext("classroom")).toBe("classroom");
    expect(normalizeRendererContext("outdoor")).toBe("outdoor");
    expect(normalizeRendererContext("unknown")).toBe("plain");
    expect(normalizeRendererContext("street")).toBe("plain");
    expect(normalizeRendererContext(undefined)).toBe("plain");
  });

  it("defines a stable version for render fingerprints", () => {
    expect(RENDERER_CONTEXT_STAGE_VERSION).toBe("renderer-context-stage-v3");
  });

  it("exposes exactly six illustrated presets plus the plain fallback", () => {
    expect(RENDERER_CONTEXTS).toEqual([
      "plain",
      "outdoor",
      "desk",
      "classroom",
      "office",
      "kitchen",
      "lab",
    ]);
  });

  it("renders screenshot-inspired outdoor context shapes", () => {
    const elements = rendererContextElements("outdoor");

    expect(elements.some((element) => element.id === "sky-fill")).toBe(true);
    expect(elements.some((element) => element.id === "grass-band")).toBe(true);
    expect(elements.some((element) => element.id === "horizon-line")).toBe(true);
  });

  it("renders deterministic classroom context shapes", () => {
    const elements = rendererContextElements("classroom");

    expect(elements.some((element) => element.id === "classroom-wall-fill")).toBe(true);
    expect(elements.some((element) => element.id === "classroom-floor-band")).toBe(true);
    expect(elements.some((element) => element.id === "classroom-board")).toBe(true);
    expect(elements.some((element) => element.id === "floor-band")).toBe(false);
  });

  it("renders distinct indoor stages instead of the shared outdoor-like room", () => {
    const expectations = {
      desk: ["desk-wall-fill", "desk-floor-band", "desk-surface", "desk-laptop"],
      office: ["office-wall-fill", "office-floor-band", "office-window", "office-plant"],
      kitchen: ["kitchen-wall-fill", "kitchen-floor-band", "kitchen-cabinets", "kitchen-counter"],
      lab: ["lab-wall-fill", "lab-floor-band", "lab-bench", "lab-shelf"],
    };

    for (const [context, ids] of Object.entries(expectations)) {
      const elementIds = rendererContextElements(context).map((element) => element.id);

      for (const id of ids) {
        expect(elementIds).toContain(id);
      }
      expect(elementIds).not.toContain("floor-band");
      expect(elementIds).not.toContain("desk-band");
    }
  });
});

describe("layerChromeStyle", () => {
  it("does not draw wrapper borders around generated panels", () => {
    const style = layerChromeStyle(panelLayer("state-a"), 1);

    expect(style.border).toBe("none");
    expect(style.boxShadow).toBe("none");
    expect(style.backgroundColor).toBe("transparent");
  });

  it("does not draw wrapper shadows or clipping boxes around transparent cutouts", () => {
    const style = layerChromeStyle(itemLayer("bubble"), 1);

    expect(style.boxShadow).toBe("none");
    expect(style.overflow).toBe("visible");
    expect(style.backgroundColor).toBe("transparent");
  });
});

describe("layerFrameStyle", () => {
  it("renders generated panels full screen instead of revealing canvas color", () => {
    const style = layerFrameStyle(panelLayer("state-a"));

    expect(style.position).toBe("absolute");
    expect(style.inset).toBe(0);
    expect(style.width).toBeUndefined();
    expect(style.height).toBeUndefined();
  });
});

describe("blinkLayerFrameStyle", () => {
  it("renders blink cutouts centered over the static context", () => {
    const style = blinkLayerFrameStyle(itemLayer("state-a"));

    expect(style.position).toBe("absolute");
    expect(style.left).toBe("50%");
    expect(style.top).toBe("50%");
    expect(style.width).toBe(760);
    expect(style.height).toBe(820);
    expect(String(style.transform)).toContain("translate(-50%, -50%)");
    expect(style.inset).toBeUndefined();
  });

  it("falls back to full-bleed frame styling for panel layers", () => {
    const style = blinkLayerFrameStyle(panelLayer("state-a"));

    expect(style.position).toBe("absolute");
    expect(style.inset).toBe(0);
    expect(style.width).toBeUndefined();
    expect(style.height).toBeUndefined();
  });
});

describe("blinkActiveLayer", () => {
  it("alternates between all states from the start of the scene", () => {
    const layers = [
      { ...itemLayer("state-a"), enter_at_seconds: 0 },
      { ...itemLayer("state-b"), enter_at_seconds: 2.1 },
    ];

    expect(blinkActiveLayer(layers, 0, 30)?.id).toBe("state-a");
    expect(blinkActiveLayer(layers, 15, 30)?.id).toBe("state-b");
    expect(blinkActiveLayer(layers, 30, 30)?.id).toBe("state-a");
  });

  it("ignores static background layers when alternating blink states", () => {
    const layers = [
      { ...panelLayer("background"), asset_kind: "full_frame" as const },
      { ...itemLayer("state-a"), enter_at_seconds: 0 },
      { ...itemLayer("state-b"), enter_at_seconds: 0 },
    ];

    expect(blinkActiveLayer(layers, 0, 30)?.id).toBe("state-a");
    expect(blinkActiveLayer(layers, 15, 30)?.id).toBe("state-b");
    expect(blinkActiveLayer(layers, 30, 30)?.id).toBe("state-a");
  });
});

describe("blinkOverlayVisible", () => {
  it("toggles renderer-owned micro-expression overlays every half second", () => {
    expect(blinkOverlayVisible(0, 30)).toBe(false);
    expect(blinkOverlayVisible(14, 30)).toBe(false);
    expect(blinkOverlayVisible(15, 30)).toBe(true);
    expect(blinkOverlayVisible(30, 30)).toBe(false);
  });
});

describe("blinkMicroOverlay", () => {
  it("defines a deterministic blink overlay", () => {
    expect(blinkMicroOverlay("blink")).toMatchObject({
      kind: "eyes",
      state: "closed",
    });
  });

  it("does not create overlays for unsupported legacy actions", () => {
    expect(blinkMicroOverlay("talking")).toBeNull();
    expect(blinkMicroOverlay("looking_sideways")).toBeNull();
    expect(blinkMicroOverlay("walking")).toBeNull();
  });
});

describe("blinkBlinkEyeOverlayGeometry", () => {
  it("stretches blink overlays to the non-square layer frame", () => {
    expect(BLINK_OVERLAY_SVG_PROPS).toMatchObject({
      viewBox: "0 0 100 100",
      preserveAspectRatio: "none",
    });
  });

  it("covers open eyes before drawing closed eyelids", () => {
    const geometry = blinkBlinkEyeOverlayGeometry(
      {
        eye_left: { x: 0.42, y: 0.33 },
        eye_right: { x: 0.58, y: 0.33 },
        mouth: { x: 0.5, y: 0.48 },
        brow_left: { x: 0.42, y: 0.26 },
        brow_right: { x: 0.58, y: 0.26 },
      },
      "#D9A374",
    );

    expect(geometry).toHaveLength(2);
    expect(geometry[0].mask).toMatchObject({
      fill: "#D9A374",
    });
    expect(geometry[0].mask.width).toBeGreaterThanOrEqual(14);
    expect(geometry[0].mask.y + geometry[0].mask.height / 2).toBeGreaterThan(33);
    expect(geometry[0].mask.width / 2).toBeGreaterThan(geometry[0].lid.strokeWidth);
    expect(geometry[0].lid.strokeWidth).toBeLessThanOrEqual(1.35);
    expect(geometry[0].lid.stroke).toBe("#2A1712");
    expect(geometry[0].lid.d).toContain("Q42");
    expect(geometry[1].mask).toMatchObject({
      fill: "#D9A374",
    });
    expect(geometry[1].mask.y + geometry[1].mask.height / 2).toBeGreaterThan(33);
    expect(geometry[1].lid.d).toContain("Q58");
  });

  it("sizes blink lids from detected eye width when available", () => {
    const geometry = blinkBlinkEyeOverlayGeometry(
      {
        eye_left: { x: 0.42, y: 0.33, width: 0.045, height: 0.02 },
        eye_right: { x: 0.58, y: 0.33, width: 0.045, height: 0.02 },
        mouth: { x: 0.5, y: 0.48 },
        brow_left: { x: 0.42, y: 0.26 },
        brow_right: { x: 0.58, y: 0.26 },
      },
      "#D9A374",
    );

    expect(geometry[0].mask.width / 2).toBeLessThan(7);
    expect(geometry[0].mask.height / 2).toBeLessThan(4);
    expect(geometry[0].mask.y + geometry[0].mask.height / 2).toBeGreaterThan(geometry[0].lid.y);
    expect(geometry[0].mask.x).toBeGreaterThan(38);
    expect(geometry[0].mask.width).toBeLessThan(7);
    expect(geometry[0].lid.d).toContain("Q42");
  });

  it("keeps minimalist dot-eye blink masks local to tiny eyes", () => {
    const geometry = blinkBlinkEyeOverlayGeometry(
      {
        eye_left: {
          x: 0.455,
          y: 0.2017,
          width: 0.012,
          height: 0.0125,
          erase_box: { left: 0.4335, top: 0.1382, right: 0.4764, bottom: 0.229 },
          fill_top: "#E4DECC",
          fill_bottom: "#9F9C90",
          fill_left: "#9B998A",
          fill_right: "#E4DECC",
        },
        eye_right: {
          x: 0.546,
          y: 0.2019,
          width: 0.0135,
          height: 0.0125,
          erase_box: { left: 0.5204, top: 0.1382, right: 0.5711, bottom: 0.229 },
          fill_top: "#E4DECC",
          fill_bottom: "#A0998C",
          fill_left: "#E4DECC",
          fill_right: "#9F988A",
        },
        mouth: { x: 0.5005, y: 0.3485 },
        brow_left: { x: 0.455, y: 0.1218 },
        brow_right: { x: 0.546, y: 0.1218 },
        skin_fill: "#E4DECC",
      },
      "#E4DECC",
    );

    expect(geometry[0].mask.width).toBeLessThan(4.5);
    expect(geometry[0].mask.height).toBeLessThan(3.5);
    expect(geometry[0].mask.y).toBeGreaterThan(18.5);
    expect(geometry[0].mask.gradient).toBeUndefined();
    expect(geometry[0].lid.strokeWidth).toBeLessThanOrEqual(0.7);
    expect(geometry[0].lid.y).toBeLessThan(20.17);
    expect(geometry[0].lid.d).toContain(`Q45.5 ${geometry[0].lid.y}`);
    expect(geometry[0].lid.d).toContain("Q45.5");
    expect(geometry[1].mask.width).toBeLessThan(4.5);
    expect(geometry[1].mask.height).toBeLessThan(3.5);
    expect(geometry[1].mask.gradient).toBeUndefined();
    expect(geometry[1].lid.y).toBeLessThan(20.19);
    expect(geometry[1].lid.strokeWidth).toBeLessThanOrEqual(0.7);
    expect(geometry[1].lid.d).toContain(`Q54.6 ${geometry[1].lid.y}`);
    expect(geometry[1].lid.d).toContain("Q54.6");
  });

  it("uses detected eye erase boxes for skin fill bounds when available", () => {
    const geometry = blinkBlinkEyeOverlayGeometry(
      {
        eye_left: {
          x: 0.42,
          y: 0.33,
          width: 0.045,
          height: 0.02,
          erase_box: { left: 0.39, top: 0.315, right: 0.45, bottom: 0.37 },
        },
        eye_right: {
          x: 0.58,
          y: 0.33,
          width: 0.045,
          height: 0.02,
          erase_box: { left: 0.55, top: 0.315, right: 0.61, bottom: 0.37 },
        },
        mouth: { x: 0.5, y: 0.48 },
        brow_left: { x: 0.42, y: 0.26 },
        brow_right: { x: 0.58, y: 0.26 },
      },
      "#D9A374",
    );

    expect(geometry[0].mask).toMatchObject({
      x: 39,
      y: 29.15,
      width: 6,
      height: 7.85,
    });
    expect(geometry[1].mask).toMatchObject({
      x: 55,
      y: 29.15,
      width: 6,
      height: 7.85,
    });
    expect(geometry[0].lid.d).toContain("Q42");
  });

  it("shares detected eye erase box height across both blink masks", () => {
    const geometry = blinkBlinkEyeOverlayGeometry(
      {
        eye_left: {
          x: 0.42,
          y: 0.33,
          width: 0.045,
          height: 0.02,
          erase_box: { left: 0.39, top: 0.315, right: 0.45, bottom: 0.39 },
        },
        eye_right: {
          x: 0.58,
          y: 0.33,
          width: 0.045,
          height: 0.02,
          erase_box: { left: 0.55, top: 0.32, right: 0.61, bottom: 0.36 },
        },
        mouth: { x: 0.5, y: 0.48 },
        brow_left: { x: 0.42, y: 0.26 },
        brow_right: { x: 0.58, y: 0.26 },
      },
      "#D9A374",
    );

    expect(geometry[0].mask).toMatchObject({
      x: 39,
      y: 29.15,
      width: 6,
      height: 9.85,
    });
    expect(geometry[1].mask).toMatchObject({
      x: 55,
      y: 29.15,
      width: 6,
      height: 9.85,
    });
  });

  it("clamps broad erase boxes horizontally to a wider eye-detail band", () => {
    const geometry = blinkBlinkEyeOverlayGeometry(
      {
        eye_left: {
          x: 0.42,
          y: 0.33,
          width: 0.05,
          height: 0.02,
          erase_box: { left: 0.34, top: 0.315, right: 0.50, bottom: 0.39 },
        },
        eye_right: {
          x: 0.58,
          y: 0.33,
          width: 0.05,
          height: 0.02,
          erase_box: { left: 0.50, top: 0.315, right: 0.66, bottom: 0.39 },
        },
        mouth: { x: 0.5, y: 0.48 },
        brow_left: { x: 0.42, y: 0.26 },
        brow_right: { x: 0.58, y: 0.26 },
      },
      "#D9A374",
    );

    expect(geometry[0].mask).toMatchObject({
      x: 37.75,
      y: 29.15,
      width: 8.5,
      height: 9.85,
    });
    expect(geometry[1].mask).toMatchObject({
      x: 53.75,
      y: 29.15,
      width: 8.5,
      height: 9.85,
    });
  });

  it("covers eyelid remnants outside the narrow dark aperture", () => {
    const geometry = blinkBlinkEyeOverlayGeometry(
      {
        eye_left: {
          x: 0.42,
          y: 0.33,
          width: 0.05,
          height: 0.02,
          erase_box: { left: 0.36, top: 0.30, right: 0.48, bottom: 0.41 },
        },
        eye_right: {
          x: 0.58,
          y: 0.33,
          width: 0.05,
          height: 0.02,
          erase_box: { left: 0.52, top: 0.30, right: 0.64, bottom: 0.41 },
        },
        mouth: { x: 0.5, y: 0.48 },
        brow_left: { x: 0.42, y: 0.26 },
        brow_right: { x: 0.58, y: 0.26 },
      },
      "#D9A374",
    );

    expect(geometry[0].mask.x).toBeLessThanOrEqual(37.8);
    expect(geometry[0].mask.x + geometry[0].mask.width).toBeGreaterThanOrEqual(46.2);
    expect(geometry[1].mask.x).toBeLessThanOrEqual(53.8);
    expect(geometry[1].mask.x + geometry[1].mask.width).toBeGreaterThanOrEqual(62.2);
  });

  it("expands upward toward old open lashes while staying below eyebrows", () => {
    const geometry = blinkBlinkEyeOverlayGeometry(
      {
        eye_left: {
          x: 0.42,
          y: 0.33,
          width: 0.05,
          height: 0.02,
          erase_box: { left: 0.39, top: 0.315, right: 0.45, bottom: 0.40 },
        },
        eye_right: {
          x: 0.58,
          y: 0.33,
          width: 0.05,
          height: 0.02,
          erase_box: { left: 0.55, top: 0.315, right: 0.61, bottom: 0.40 },
        },
        mouth: { x: 0.5, y: 0.48 },
        brow_left: { x: 0.42, y: 0.26 },
        brow_right: { x: 0.58, y: 0.26 },
      },
      "#D9A374",
    );

    expect(geometry[0].mask.y).toBeLessThanOrEqual(29.2);
    expect(geometry[0].mask.y).toBeGreaterThan(26);
    expect(geometry[1].mask.y).toBeLessThanOrEqual(29.2);
    expect(geometry[1].mask.y).toBeGreaterThan(26);
  });

  it("honors brow-inclusive erase boxes from the backend", () => {
    const geometry = blinkBlinkEyeOverlayGeometry(
      {
        eye_left: {
          x: 0.42,
          y: 0.33,
          width: 0.05,
          height: 0.02,
          erase_box: { left: 0.39, top: 0.22, right: 0.45, bottom: 0.40 },
        },
        eye_right: {
          x: 0.58,
          y: 0.33,
          width: 0.05,
          height: 0.02,
          erase_box: { left: 0.55, top: 0.22, right: 0.61, bottom: 0.40 },
        },
        mouth: { x: 0.5, y: 0.48 },
        brow_left: { x: 0.42, y: 0.26 },
        brow_right: { x: 0.58, y: 0.26 },
      },
      "#D9A374",
    );

    expect(geometry[0].mask).toMatchObject({
      x: 39,
      y: 22,
      width: 6,
      height: 18,
      rx: 1.5,
    });
    expect(geometry[1].mask).toMatchObject({
      x: 55,
      y: 22,
      width: 6,
      height: 18,
      rx: 1.5,
    });
  });

  it("keeps detected upper eyelid tops that are below eyebrow space", () => {
    const geometry = blinkBlinkEyeOverlayGeometry(
      {
        eye_left: {
          x: 0.42,
          y: 0.33,
          width: 0.05,
          height: 0.02,
          erase_box: { left: 0.39, top: 0.285, right: 0.45, bottom: 0.40 },
        },
        eye_right: {
          x: 0.58,
          y: 0.33,
          width: 0.05,
          height: 0.02,
          erase_box: { left: 0.55, top: 0.285, right: 0.61, bottom: 0.40 },
        },
        mouth: { x: 0.5, y: 0.48 },
        brow_left: { x: 0.42, y: 0.26 },
        brow_right: { x: 0.58, y: 0.26 },
      },
      "#D9A374",
    );

    expect(geometry[0].mask.y).toBe(28.5);
    expect(geometry[1].mask.y).toBe(28.5);
  });

  it("uses backend eye-aperture bounds and draws closed lashes at the detected eye center", () => {
    const geometry = blinkBlinkEyeOverlayGeometry(
      {
        eye_left: {
          x: 0.42,
          y: 0.33,
          width: 0.05,
          height: 0.02,
          erase_box: { left: 0.39, top: 0.315, right: 0.45, bottom: 0.37 },
        },
        eye_right: {
          x: 0.58,
          y: 0.33,
          width: 0.05,
          height: 0.02,
          erase_box: { left: 0.55, top: 0.315, right: 0.61, bottom: 0.37 },
        },
        mouth: { x: 0.5, y: 0.48 },
        brow_left: { x: 0.42, y: 0.26 },
        brow_right: { x: 0.58, y: 0.26 },
      },
      "#D9A374",
    );

    expect(geometry[0].mask).toMatchObject({
      y: 29.15,
      height: 7.85,
    });
    expect(geometry[1].mask).toMatchObject({
      y: 29.15,
      height: 7.85,
    });
    expect(geometry[0].lid.y).toBeCloseTo(33, 1);
    expect(geometry[1].lid.y).toBeCloseTo(33, 1);
  });

  it("uses per-eye skin gradients for blink masks when sampled colors are available", () => {
    const geometry = blinkBlinkEyeOverlayGeometry(
      {
        eye_left: {
          x: 0.42,
          y: 0.33,
          width: 0.045,
          height: 0.02,
          erase_box: { left: 0.39, top: 0.315, right: 0.45, bottom: 0.37 },
          fill_top: "#F5B97D",
          fill_bottom: "#C3784B",
        },
        eye_right: {
          x: 0.58,
          y: 0.33,
          width: 0.045,
          height: 0.02,
          erase_box: { left: 0.55, top: 0.315, right: 0.61, bottom: 0.37 },
          fill_top: "#E4A46A",
          fill_bottom: "#B96E43",
        },
        mouth: { x: 0.5, y: 0.48 },
        brow_left: { x: 0.42, y: 0.26 },
        brow_right: { x: 0.58, y: 0.26 },
      },
      "#D9A374",
    );

    expect(geometry[0].mask.fill).toBe("url(#blink-blink-eye-0-gradient)");
    expect(geometry[0].mask.gradient).toEqual({
      id: "blink-blink-eye-0-gradient",
      top: "#F5B97D",
      bottom: "#C3784B",
      orientation: "vertical",
    });
    expect(geometry[1].mask.fill).toBe("url(#blink-blink-eye-1-gradient)");
    expect(geometry[1].mask.gradient).toEqual({
      id: "blink-blink-eye-1-gradient",
      top: "#E4A46A",
      bottom: "#B96E43",
      orientation: "vertical",
    });
  });

  it("prefers horizontal per-eye skin gradients when side lighting is available", () => {
    const geometry = blinkBlinkEyeOverlayGeometry(
      {
        eye_left: {
          x: 0.42,
          y: 0.33,
          width: 0.045,
          height: 0.02,
          erase_box: { left: 0.39, top: 0.315, right: 0.45, bottom: 0.37 },
          fill_left: "#F5B97D",
          fill_right: "#C3784B",
          fill_top: "#D58E5B",
          fill_bottom: "#D28A58",
        },
        eye_right: {
          x: 0.58,
          y: 0.33,
          width: 0.045,
          height: 0.02,
          erase_box: { left: 0.55, top: 0.315, right: 0.61, bottom: 0.37 },
          fill_left: "#C3784B",
          fill_right: "#B96E43",
        },
        mouth: { x: 0.5, y: 0.48 },
        brow_left: { x: 0.42, y: 0.26 },
        brow_right: { x: 0.58, y: 0.26 },
      },
      "#D9A374",
    );

    expect(geometry[0].mask.gradient).toEqual({
      id: "blink-blink-eye-0-gradient",
      top: "#F5B97D",
      bottom: "#C3784B",
      orientation: "horizontal",
    });
    expect(geometry[1].mask.gradient).toEqual({
      id: "blink-blink-eye-1-gradient",
      top: "#C3784B",
      bottom: "#B96E43",
      orientation: "horizontal",
    });
  });

  it("prefers vertical per-eye skin gradients when vertical lighting changes more", () => {
    const geometry = blinkBlinkEyeOverlayGeometry(
      {
        eye_left: {
          x: 0.42,
          y: 0.33,
          width: 0.045,
          height: 0.02,
          erase_box: { left: 0.39, top: 0.315, right: 0.45, bottom: 0.37 },
          fill_left: "#D58E5B",
          fill_right: "#D28A58",
          fill_top: "#F5B97D",
          fill_bottom: "#C3784B",
        },
        eye_right: {
          x: 0.58,
          y: 0.33,
          width: 0.045,
          height: 0.02,
          erase_box: { left: 0.55, top: 0.315, right: 0.61, bottom: 0.37 },
        },
        mouth: { x: 0.5, y: 0.48 },
        brow_left: { x: 0.42, y: 0.26 },
        brow_right: { x: 0.58, y: 0.26 },
      },
      "#D9A374",
    );

    expect(geometry[0].mask.gradient).toEqual({
      id: "blink-blink-eye-0-gradient",
      top: "#F5B97D",
      bottom: "#C3784B",
      orientation: "vertical",
    });
  });
});

describe("blinkOverlayAnchor", () => {
  it("reads normalized overlay anchors from layer metadata", () => {
    const anchor = blinkOverlayAnchor({
      ...itemLayer("base"),
      visual_source_metadata: {
        blink_overlay_anchor: {
          detected: true,
          mouth: { x: 0.52, y: 0.48 },
          eye_left: { x: 0.42, y: 0.33 },
          eye_right: { x: 0.58, y: 0.33 },
          brow_left: { x: 0.42, y: 0.27 },
          brow_right: { x: 0.58, y: 0.27 },
        },
      },
    });

    expect(anchor).not.toBeNull();
    if (!anchor) {
      throw new Error("Expected detected blink anchor metadata");
    }
    expect(anchor.mouth).toEqual({ x: 0.52, y: 0.48 });
    expect(anchor.eye_left).toEqual({ x: 0.42, y: 0.33 });
  });

  it("falls back when overlay anchor metadata is missing or invalid", () => {
    const anchor = blinkOverlayAnchor({
      ...itemLayer("base"),
      visual_source_metadata: {
        blink_overlay_anchor: {
          mouth: { x: 2, y: -1 },
        },
      },
    });

    expect(anchor).toBeNull();
  });
});

describe("comparisonBoardLayerStyle", () => {
  it("places comparison cutouts into stable side-by-side columns", () => {
    const left = comparisonBoardLayerStyle(itemLayer("before"), 0, 2, 30, 30);
    const right = comparisonBoardLayerStyle(itemLayer("after"), 1, 2, 30, 30);

    expect(left.left).toBe("25%");
    expect(right.left).toBe("75%");
    expect(left.width).toBe(560);
    expect(left.height).toBe(640);
    expect(left.transform).toContain("translate(-50%, -50%)");
    expect(left.transform).toContain("scale(");
  });

  it("supports a three-column variant", () => {
    const middle = comparisonBoardLayerStyle(itemLayer("reality"), 1, 3, 0, 30);

    expect(middle.left).toBe("50%");
    expect(middle.top).toBe("53%");
    expect(middle.width).toBe(440);
    expect(middle.height).toBe(580);
  });
});

describe("comparisonLabel", () => {
  it("uses explicit comparison labels instead of assuming before and after", () => {
    expect(comparisonLabel({ ...itemLayer("left"), label: "Myth" })).toBe("Myth");
    expect(comparisonLabel({ ...itemLayer("right"), label: "Reality" })).toBe("Reality");
  });

  it("hides labels when no high-confidence semantic label is available", () => {
    expect(comparisonLabel(itemLayer("left"))).toBeNull();
    expect(comparisonLabel({ ...itemLayer("right"), label: "Option 2" })).toBeNull();
    expect(comparisonLabel({ ...itemLayer("placeholder"), prompt: "Comparison board transparent cutout for left subject: scene." })).toBeNull();
    expect(comparisonLabel({ ...itemLayer("prompt-label"), prompt: "Comparison board transparent cutout for Myth: scene." })).toBeNull();
  });
});

describe("StatCard", () => {
  it("is a renderable React component", () => {
    expect(typeof StatCard).toBe("function");
  });
});
