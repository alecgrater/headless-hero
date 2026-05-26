import { describe, expect, it } from "vitest";
import type React from "react";

import { layerChromeStyle, popupOrbitFrameStyle } from "@remotion-src/scenes/TreatmentRenderer";
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
