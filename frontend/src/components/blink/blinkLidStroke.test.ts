import { describe, expect, it } from "vitest";

import { BLINK_DEFAULT_LID_STROKE, blinkLidStroke } from "./blinkLidStroke";

describe("blinkLidStroke", () => {
  it("uses the anchor's line color when it is a valid hex color", () => {
    expect(blinkLidStroke({ lid_stroke: "#1a1a1a" })).toBe("#1a1a1a");
  });

  it("falls back to the renderer's default otherwise", () => {
    expect(blinkLidStroke({ lid_stroke: "black" })).toBe(BLINK_DEFAULT_LID_STROKE);
    expect(blinkLidStroke({})).toBe(BLINK_DEFAULT_LID_STROKE);
    expect(blinkLidStroke(null)).toBe(BLINK_DEFAULT_LID_STROKE);
  });
});
