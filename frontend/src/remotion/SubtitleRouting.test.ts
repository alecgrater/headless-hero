import { describe, expect, it } from "vitest";

import { resolveSubtitleStyle } from "@remotion-src/effects/typography/subtitleRouting";
import type { SceneInput } from "@remotion-src/types";

const scene = (overrides: Partial<SceneInput>): SceneInput => ({
  id: "scene",
  narration: "This is a normal explanatory sentence.",
  duration_seconds: 6,
  is_title_card: false,
  visual_mode: "full_frame",
  word_timestamps: [
    { word: "This", start_ms: 0, end_ms: 500 },
    { word: "works", start_ms: 500, end_ms: 1000 },
  ],
  ...overrides,
});

describe("resolveSubtitleStyle", () => {
  it("honors explicit subtitle style overrides", () => {
    expect(resolveSubtitleStyle(scene({ subtitle_style: "kinetic" }), "horizontal")).toBe("kinetic");
  });

  it("suppresses captions visual mode and title cards", () => {
    expect(resolveSubtitleStyle(scene({ visual_mode: "captions" }), "horizontal")).toBe("none");
    expect(resolveSubtitleStyle(scene({ is_title_card: true }), "horizontal")).toBe("none");
  });

  it("routes fast dense word timing to kinetic", () => {
    expect(resolveSubtitleStyle(scene({
      narration: "One two three four five six seven eight.",
      word_timestamps: [
        { word: "One", start_ms: 0, end_ms: 120 },
        { word: "two", start_ms: 130, end_ms: 250 },
        { word: "three", start_ms: 260, end_ms: 380 },
        { word: "four", start_ms: 390, end_ms: 510 },
        { word: "five", start_ms: 520, end_ms: 640 },
        { word: "six", start_ms: 650, end_ms: 770 },
      ],
    }), "horizontal")).toBe("kinetic");
  });

  it("routes reveal language to burst", () => {
    expect(resolveSubtitleStyle(scene({ narration: "But then the real reason appears." }), "horizontal")).toBe("burst");
  });

  it("falls back to clean when uncertain", () => {
    expect(resolveSubtitleStyle(scene({}), "horizontal")).toBe("clean");
  });

  it("uses the only enabled subtitle style for automatic scenes", () => {
    expect(resolveSubtitleStyle(scene({}), "horizontal", { enabledStyles: ["kinetic"] })).toBe("kinetic");
  });

  it("prevents disabled subtitle styles from being selected", () => {
    expect(resolveSubtitleStyle(
      scene({ narration: "But then the real reason appears." }),
      "horizontal",
      { enabledStyles: ["clean", "kinetic"] },
    )).toBe("kinetic");
  });

  it("suppresses subtitles when no styles are enabled", () => {
    expect(resolveSubtitleStyle(scene({}), "horizontal", { enabledStyles: [] })).toBe("none");
  });
});
