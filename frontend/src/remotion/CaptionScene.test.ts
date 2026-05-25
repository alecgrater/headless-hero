import { describe, expect, it } from "vitest";

import {
  chooseCaptionEmphasis,
  splitCaptionWords,
  captionWordsForDisplay,
} from "@remotion-src/utils/captionText";

describe("captionText utilities", () => {
  it("uses caption text before narration and strips subtitle hyphens for display", () => {
    const words = captionWordsForDisplay({
      captionText: "You were never-behind",
      narration: "Fallback narration",
    });

    expect(words).toEqual(["You", "were", "neverbehind"]);
  });

  it("falls back to narration when caption text is empty", () => {
    const words = captionWordsForDisplay({
      captionText: "",
      narration: "The real cost",
    });

    expect(words).toEqual(["The", "real", "cost"]);
  });

  it("chooses explicit emphasis when it matches the caption", () => {
    expect(chooseCaptionEmphasis("Spending big while falling behind", "falling behind")).toBe("falling behind");
  });

  it("falls back to the final content phrase when emphasis is missing", () => {
    expect(chooseCaptionEmphasis("This is the real cost", "")).toBe("real cost");
  });

  it("marks multi-word emphasis ranges", () => {
    const result = splitCaptionWords("Spending big while falling behind", "falling behind");

    expect(result.map((word) => [word.text, word.emphasized])).toEqual([
      ["Spending", false],
      ["big", false],
      ["while", false],
      ["falling", true],
      ["behind", true],
    ]);
  });
});
