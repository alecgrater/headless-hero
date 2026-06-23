import { describe, expect, it } from "vitest";

import { resolveBlinkOverlayAnchor } from "@remotion-src/scenes/BlinkOverlay";

const safeAnchor = (overrides: Record<string, unknown> = {}) => ({
  detected: true,
  skin_fill: "#D9A374",
  eye_left: { x: 0.42, y: 0.33, width: 0.045, height: 0.02 },
  eye_right: { x: 0.58, y: 0.33, width: 0.045, height: 0.02 },
  mouth: { x: 0.5, y: 0.48 },
  brow_left: { x: 0.42, y: 0.26 },
  brow_right: { x: 0.58, y: 0.26 },
  ...overrides,
});

describe("resolveBlinkOverlayAnchor", () => {
  it("resolves a safe, symmetric, eye-sized anchor", () => {
    const anchor = resolveBlinkOverlayAnchor(safeAnchor());
    expect(anchor).not.toBeNull();
    expect(anchor?.eye_left).toMatchObject({ x: 0.42, y: 0.33 });
  });

  it("rejects anchors that are not flagged detected", () => {
    expect(resolveBlinkOverlayAnchor(safeAnchor({ detected: false }))).toBeNull();
  });

  it("rejects anchors missing detected eye width/height", () => {
    expect(resolveBlinkOverlayAnchor(safeAnchor({ eye_left: { x: 0.42, y: 0.33 } }))).toBeNull();
  });

  it("rejects anchors whose eyes are far too large to be a real eye", () => {
    expect(
      resolveBlinkOverlayAnchor(
        safeAnchor({
          eye_left: { x: 0.42, y: 0.33, width: 0.4, height: 0.3 },
          eye_right: { x: 0.58, y: 0.33, width: 0.4, height: 0.3 },
        }),
      ),
    ).toBeNull();
  });

  it("rejects vertically misaligned eye pairs", () => {
    expect(
      resolveBlinkOverlayAnchor(
        safeAnchor({ eye_right: { x: 0.58, y: 0.41, width: 0.045, height: 0.02 } }),
      ),
    ).toBeNull();
  });

  it("rejects asymmetric eye pairs", () => {
    expect(
      resolveBlinkOverlayAnchor(
        safeAnchor({ eye_right: { x: 0.58, y: 0.33, width: 0.012, height: 0.02 } }),
      ),
    ).toBeNull();
  });

  it("rejects eyes that are too close together or too far apart to be a face", () => {
    expect(
      resolveBlinkOverlayAnchor(
        safeAnchor({
          eye_left: { x: 0.49, y: 0.33, width: 0.045, height: 0.02 },
          eye_right: { x: 0.505, y: 0.33, width: 0.045, height: 0.02 },
        }),
      ),
    ).toBeNull();
    expect(
      resolveBlinkOverlayAnchor(
        safeAnchor({
          eye_left: { x: 0.05, y: 0.33, width: 0.045, height: 0.02 },
          eye_right: { x: 0.95, y: 0.33, width: 0.045, height: 0.02 },
        }),
      ),
    ).toBeNull();
  });

  it("rejects anchors whose eyes are swapped in x order", () => {
    expect(
      resolveBlinkOverlayAnchor(
        safeAnchor({
          eye_left: { x: 0.58, y: 0.33, width: 0.045, height: 0.02 },
          eye_right: { x: 0.42, y: 0.33, width: 0.045, height: 0.02 },
        }),
      ),
    ).toBeNull();
  });
});
