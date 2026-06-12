import { describe, expect, it } from "vitest";
import type React from "react";

import {
  comparisonBoardLayerStyle,
  comparisonLabel,
  flipflopActiveLayer,
  flipflopMicroOverlay,
  flipflopOverlayVisible,
  flipflopLayerFrameStyle,
  layerChromeStyle,
  layerFrameStyle,
  popupOrbitFrameStyle,
} from "@remotion-src/scenes/TreatmentRenderer";
import {
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

describe("RendererContextStage", () => {
  it("normalizes unknown contexts to plain", () => {
    expect(normalizeRendererContext("classroom")).toBe("classroom");
    expect(normalizeRendererContext("unknown")).toBe("plain");
    expect(normalizeRendererContext(undefined)).toBe("plain");
  });

  it("defines a stable version for render fingerprints", () => {
    expect(RENDERER_CONTEXT_STAGE_VERSION).toBe("renderer-context-stage-v1");
  });

  it("renders deterministic classroom context shapes", () => {
    const elements = rendererContextElements("classroom");

    expect(elements.some((element) => element.id === "classroom-board")).toBe(true);
    expect(elements.some((element) => element.id === "floor-band")).toBe(true);
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

describe("flipflopLayerFrameStyle", () => {
  it("renders flip-flop cutouts centered over the static context", () => {
    const style = flipflopLayerFrameStyle(itemLayer("state-a"));

    expect(style.position).toBe("absolute");
    expect(style.left).toBe("50%");
    expect(style.top).toBe("50%");
    expect(style.width).toBe(760);
    expect(style.height).toBe(820);
    expect(String(style.transform)).toContain("translate(-50%, -50%)");
    expect(style.inset).toBeUndefined();
  });

  it("falls back to full-bleed frame styling for panel layers", () => {
    const style = flipflopLayerFrameStyle(panelLayer("state-a"));

    expect(style.position).toBe("absolute");
    expect(style.inset).toBe(0);
    expect(style.width).toBeUndefined();
    expect(style.height).toBeUndefined();
  });
});

describe("flipflopActiveLayer", () => {
  it("alternates between all states from the start of the scene", () => {
    const layers = [
      { ...itemLayer("state-a"), enter_at_seconds: 0 },
      { ...itemLayer("state-b"), enter_at_seconds: 2.1 },
    ];

    expect(flipflopActiveLayer(layers, 0, 30)?.id).toBe("state-a");
    expect(flipflopActiveLayer(layers, 15, 30)?.id).toBe("state-b");
    expect(flipflopActiveLayer(layers, 30, 30)?.id).toBe("state-a");
  });

  it("ignores static background layers when alternating flip-flop states", () => {
    const layers = [
      { ...panelLayer("background"), asset_kind: "full_frame" as const },
      { ...itemLayer("state-a"), enter_at_seconds: 0 },
      { ...itemLayer("state-b"), enter_at_seconds: 0 },
    ];

    expect(flipflopActiveLayer(layers, 0, 30)?.id).toBe("state-a");
    expect(flipflopActiveLayer(layers, 15, 30)?.id).toBe("state-b");
    expect(flipflopActiveLayer(layers, 30, 30)?.id).toBe("state-a");
  });
});

describe("flipflopOverlayVisible", () => {
  it("toggles renderer-owned micro-expression overlays every half second", () => {
    expect(flipflopOverlayVisible(0, 30)).toBe(false);
    expect(flipflopOverlayVisible(14, 30)).toBe(false);
    expect(flipflopOverlayVisible(15, 30)).toBe(true);
    expect(flipflopOverlayVisible(30, 30)).toBe(false);
  });
});

describe("flipflopMicroOverlay", () => {
  it("defines a deterministic speaking mouth overlay", () => {
    expect(flipflopMicroOverlay("speaking_mouth")).toMatchObject({
      kind: "mouth",
      state: "open",
    });
  });

  it("does not create overlays for pose-changing legacy actions", () => {
    expect(flipflopMicroOverlay("head_nod")).toBeNull();
    expect(flipflopMicroOverlay("small_shrug")).toBeNull();
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
