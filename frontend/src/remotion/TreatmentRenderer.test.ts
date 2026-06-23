import { describe, expect, it } from "vitest";
import type React from "react";

import {
  comparisonBoardLayerStyle,
  BLINK_OVERLAY_SVG_PROPS,
  BLINK_OVERLAY_ASPECT,
  comparisonLabel,
  blinkMicroOverlay,
  blinkBlinkEyeOverlayGeometry,
  blinkOverlayVisible,
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
  it("normalizes contexts to the two-stage vocabulary", () => {
    expect(normalizeRendererContext("indoor")).toBe("indoor");
    expect(normalizeRendererContext("classroom")).toBe("indoor");
    expect(normalizeRendererContext("kitchen")).toBe("indoor");
    expect(normalizeRendererContext("outdoor")).toBe("outdoor");
    expect(normalizeRendererContext("unknown")).toBe("outdoor");
    expect(normalizeRendererContext("street")).toBe("outdoor");
    expect(normalizeRendererContext(undefined)).toBe("outdoor");
  });

  it("defines a stable version for render fingerprints", () => {
    expect(RENDERER_CONTEXT_STAGE_VERSION).toBe("renderer-context-stage-v4");
  });

  it("exposes only outdoor and indoor renderer contexts", () => {
    expect(RENDERER_CONTEXTS).toEqual(["outdoor", "indoor"]);
  });

  it("renders screenshot-inspired outdoor context shapes", () => {
    const elements = rendererContextElements("outdoor");

    expect(elements.some((element) => element.id === "sky-fill")).toBe(true);
    expect(elements.some((element) => element.id === "grass-band")).toBe(true);
    expect(elements.some((element) => element.id === "horizon-line")).toBe(true);
  });

  it("renders indoor as alternate colors plus a window pane", () => {
    const elements = rendererContextElements("indoor");
    const elementIds = elements.map((element) => element.id);

    expect(elementIds).toEqual([
      "indoor-wall-fill",
      "indoor-floor-band",
      "indoor-horizon-line",
      "indoor-window-frame",
      "indoor-window-vertical-pane",
      "indoor-window-horizontal-pane",
    ]);
    expect(elements.some((element) => element.id === "sky-fill")).toBe(false);
    expect(elements.some((element) => element.id === "grass-band")).toBe(false);
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

describe("blinkOverlayVisible", () => {
  it("uses short irregular blink windows for renderer-owned micro-expression overlays", () => {
    expect(blinkOverlayVisible(0, 30)).toBe(false);
    expect(blinkOverlayVisible(14, 30)).toBe(false);
    expect(blinkOverlayVisible(15, 30)).toBe(false);
    expect(blinkOverlayVisible(30, 30)).toBe(false);
    expect(blinkOverlayVisible(54, 30)).toBe(true);
    expect(blinkOverlayVisible(62, 30)).toBe(false);
  });

  it("keeps blinks brief and spaced at irregular intervals so it never reads as a fixed toggle", () => {
    const fps = 30;
    const seed = "scene-irregular";
    const visible: number[] = [];
    for (let frame = 0; frame < fps * 30; frame += 1) {
      if (blinkOverlayVisible(frame, fps, seed)) {
        visible.push(frame);
      }
    }
    expect(visible.length).toBeGreaterThan(0);

    // Group contiguous visible frames into blink pulses.
    const pulses: Array<{ start: number; end: number }> = [];
    for (const frame of visible) {
      const last = pulses[pulses.length - 1];
      if (last && frame === last.end + 1) {
        last.end = frame;
      } else {
        pulses.push({ start: frame, end: frame });
      }
    }

    // Each pulse must be short (a blink, not a hold).
    for (const pulse of pulses) {
      const duration = pulse.end - pulse.start + 1;
      expect(duration).toBeLessThanOrEqual(6);
    }

    // Gaps between pulses must vary (not a fixed-interval toggle).
    expect(pulses.length).toBeGreaterThanOrEqual(3);
    const gaps = pulses.slice(1).map((pulse, index) => pulse.start - pulses[index].end);
    const uniqueGaps = new Set(gaps);
    expect(uniqueGaps.size).toBeGreaterThan(1);
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
  const anchorWithEyes = (overrides: Record<string, unknown> = {}) => ({
    eye_left: { x: 0.42, y: 0.33, width: 0.045, height: 0.02 },
    eye_right: { x: 0.58, y: 0.33, width: 0.045, height: 0.02 },
    mouth: { x: 0.5, y: 0.48 },
    brow_left: { x: 0.42, y: 0.26 },
    brow_right: { x: 0.58, y: 0.26 },
    ...overrides,
  });

  it("keeps the stretched-viewBox placement props", () => {
    expect(BLINK_OVERLAY_SVG_PROPS).toMatchObject({
      viewBox: "0 0 100 100",
      preserveAspectRatio: "none",
    });
    expect(BLINK_OVERLAY_ASPECT).toBeCloseTo(16 / 9, 5);
  });

  it("suppresses the overlay entirely when eye width/height are missing", () => {
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

    expect(geometry).toEqual([]);
  });

  it("suppresses the overlay when only one eye reports a size", () => {
    const geometry = blinkBlinkEyeOverlayGeometry(
      anchorWithEyes({ eye_right: { x: 0.58, y: 0.33 } }),
      "#D9A374",
    );

    expect(geometry).toEqual([]);
  });

  it("sizes closed-eye marks to the detected eye width, not a wide bar", () => {
    const geometry = blinkBlinkEyeOverlayGeometry(anchorWithEyes(), "#D9A374");

    expect(geometry).toHaveLength(2);
    const eyeWidthVB = 0.045 * 100; // 4.5
    for (const eye of geometry) {
      // Mask covers the open eye but stays close to its real width (no bar).
      expect(eye.mask.width).toBeGreaterThanOrEqual(eyeWidthVB);
      expect(eye.mask.width).toBeLessThanOrEqual(eyeWidthVB * 1.25);
    }
  });

  it("centers each closed-eye mark on the detected eye", () => {
    const geometry = blinkBlinkEyeOverlayGeometry(anchorWithEyes(), "#D9A374");

    expect(geometry[0].mask.x + geometry[0].mask.width / 2).toBeCloseTo(42, 1);
    expect(geometry[0].mask.y + geometry[0].mask.height / 2).toBeCloseTo(33, 1);
    expect(geometry[1].mask.x + geometry[1].mask.width / 2).toBeCloseTo(58, 1);
    expect(geometry[1].mask.y + geometry[1].mask.height / 2).toBeCloseTo(33, 1);
    expect(geometry[0].lid.d).toContain("Q42");
    expect(geometry[1].lid.d).toContain("Q58");
  });

  it("never lets the two closed-eye marks cross the nose midline", () => {
    const geometry = blinkBlinkEyeOverlayGeometry(anchorWithEyes(), "#D9A374");
    const midpoint = ((0.42 + 0.58) / 2) * 100; // 50

    const leftRightEdge = geometry[0].mask.x + geometry[0].mask.width;
    const rightLeftEdge = geometry[1].mask.x;
    expect(leftRightEdge).toBeLessThan(midpoint);
    expect(rightLeftEdge).toBeGreaterThan(midpoint);
  });

  it("never produces an on-screen bar even when eyes are far apart", () => {
    const geometry = blinkBlinkEyeOverlayGeometry(
      anchorWithEyes({
        eye_left: { x: 0.30, y: 0.33, width: 0.05, height: 0.018 },
        eye_right: { x: 0.70, y: 0.33, width: 0.05, height: 0.018 },
      }),
      "#D9A374",
    );

    for (const eye of geometry) {
      const onScreenAspect = (eye.mask.width / eye.mask.height) * BLINK_OVERLAY_ASPECT;
      expect(onScreenAspect).toBeLessThanOrEqual(2.6);
    }
  });

  it("keeps lid strokes thin and lids within the eye width", () => {
    const geometry = blinkBlinkEyeOverlayGeometry(anchorWithEyes(), "#D9A374");

    for (const eye of geometry) {
      expect(eye.lid.strokeWidth).toBeLessThanOrEqual(0.9);
    }
    // Lid endpoints (M{x} ... {x2}) span no more than ~the detected eye width.
    const match = geometry[0].lid.d.match(/^M([\d.]+) [\d.]+ Q[\d.]+ [\d.]+ ([\d.]+)/);
    expect(match).not.toBeNull();
    if (match) {
      const span = Number(match[2]) - Number(match[1]);
      expect(span).toBeLessThanOrEqual(0.045 * 100 * 1.05);
    }
  });

  it("keeps minimalist tiny eyes producing tiny local marks", () => {
    const geometry = blinkBlinkEyeOverlayGeometry(
      anchorWithEyes({
        eye_left: { x: 0.455, y: 0.2017, width: 0.012, height: 0.0125 },
        eye_right: { x: 0.546, y: 0.2019, width: 0.0135, height: 0.0125 },
      }),
      "#E4DECC",
    );

    expect(geometry[0].mask.width).toBeLessThan(2.5);
    expect(geometry[0].mask.height).toBeLessThan(3.5);
    expect(geometry[0].lid.strokeWidth).toBeLessThanOrEqual(0.7);
  });

  it("uses per-eye vertical skin gradients when sampled colors are available", () => {
    const geometry = blinkBlinkEyeOverlayGeometry(
      anchorWithEyes({
        eye_left: {
          x: 0.42,
          y: 0.33,
          width: 0.045,
          height: 0.02,
          fill_top: "#F5B97D",
          fill_bottom: "#C3784B",
        },
        eye_right: {
          x: 0.58,
          y: 0.33,
          width: 0.045,
          height: 0.02,
          fill_top: "#E4A46A",
          fill_bottom: "#B96E43",
        },
      }),
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
  });

  it("prefers horizontal per-eye skin gradients when side lighting dominates", () => {
    const geometry = blinkBlinkEyeOverlayGeometry(
      anchorWithEyes({
        eye_left: {
          x: 0.42,
          y: 0.33,
          width: 0.045,
          height: 0.02,
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
          fill_left: "#C3784B",
          fill_right: "#B96E43",
        },
      }),
      "#D9A374",
    );

    expect(geometry[0].mask.gradient).toEqual({
      id: "blink-blink-eye-0-gradient",
      top: "#F5B97D",
      bottom: "#C3784B",
      orientation: "horizontal",
    });
  });

  it("falls back to the flat skin fill when no gradient colors are present", () => {
    const geometry = blinkBlinkEyeOverlayGeometry(anchorWithEyes(), "#D9A374");

    expect(geometry[0].mask.fill).toBe("#D9A374");
    expect(geometry[0].mask.gradient).toBeUndefined();
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
