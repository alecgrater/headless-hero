import { describe, expect, it } from "vitest";

import {
  chooseCaptionEmphasis,
  findCaptionWordTimestamps,
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

  it("aligns hyphen-collapsed caption words to multiple spoken timestamp words", () => {
    const result = findCaptionWordTimestamps(
      [
        { word: "You", start_ms: 0, end_ms: 200 },
        { word: "were", start_ms: 250, end_ms: 450 },
        { word: "never", start_ms: 500, end_ms: 720 },
        { word: "behind", start_ms: 740, end_ms: 980 },
        { word: "until", start_ms: 1040, end_ms: 1240 },
        { word: "now", start_ms: 1280, end_ms: 1460 },
      ],
      "never-behind until now",
      3,
    );

    expect(result.map((word) => [word.word, word.start_ms])).toEqual([
      ["never", 500],
      ["until", 1040],
      ["now", 1280],
    ]);
  });

  it("prefers the final spoken caption phrase when words repeat", () => {
    const result = findCaptionWordTimestamps(
      [
        { word: "real", start_ms: 0, end_ms: 180 },
        { word: "cost", start_ms: 200, end_ms: 380 },
        { word: "was", start_ms: 420, end_ms: 560 },
        { word: "hidden", start_ms: 600, end_ms: 780 },
        { word: "until", start_ms: 820, end_ms: 980 },
        { word: "the", start_ms: 1020, end_ms: 1120 },
        { word: "real", start_ms: 1160, end_ms: 1340 },
        { word: "cost", start_ms: 1380, end_ms: 1560 },
      ],
      "real cost",
      2,
    );

    expect(result.map((word) => [word.word, word.start_ms])).toEqual([
      ["real", 1160],
      ["cost", 1380],
    ]);
  });
});
