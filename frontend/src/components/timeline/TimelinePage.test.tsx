import { describe, expect, it } from "vitest";

import { isBlinkReviewRequiredError } from "./TimelinePage";

describe("isBlinkReviewRequiredError", () => {
  it("detects backend blink review blocking errors", () => {
    expect(isBlinkReviewRequiredError(new Error("Blink Review must be completed before rendering/exporting"))).toBe(true);
    expect(isBlinkReviewRequiredError(new Error("Render failed"))).toBe(false);
  });
});
