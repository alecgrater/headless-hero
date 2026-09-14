import { describe, expect, it } from "vitest";

import { resolveSubtitleStyle, spokenSpanSeconds } from "@remotion-src/effects/typography/subtitleRouting";
import type { SceneInput, WordTimestamp } from "@remotion-src/types";

/** Evenly spaced words spanning exactly `spanMs`. */
const words = (count: number, spanMs: number): WordTimestamp[] => {
  const step = spanMs / count;
  return Array.from({ length: count }, (_, i) => ({
    word: `w${i}`,
    start_ms: Math.round(i * step),
    end_ms: Math.round((i + 1) * step),
  }));
};

/** Default scene is a normal explanatory beat: 12 words over 5s -> clean. */
const scene = (overrides: Partial<SceneInput>): SceneInput => ({
  id: "scene",
  narration: "This is a normal explanatory sentence that runs on for a while.",
  duration_seconds: 6,
  is_title_card: false,
  visual_mode: "full_frame",
  word_timestamps: words(12, 5000),
  ...overrides,
});

describe("resolveSubtitleStyle", () => {
  it("honors explicit subtitle style overrides", () => {
    expect(resolveSubtitleStyle(scene({ subtitle_style: "kinetic" }), "horizontal")).toBe("kinetic");
    expect(resolveSubtitleStyle(scene({ subtitle_style: "clean" }), "horizontal")).toBe("clean");
    expect(resolveSubtitleStyle(scene({ subtitle_style: "none" }), "horizontal")).toBe("none");
  });

  it("suppresses captions visual mode and title cards", () => {
    expect(resolveSubtitleStyle(scene({ visual_mode: "captions" }), "horizontal")).toBe("none");
    expect(resolveSubtitleStyle(scene({ is_title_card: true }), "horizontal")).toBe("none");
  });

  it("suppresses stat_card visual mode", () => {
    expect(resolveSubtitleStyle(scene({ visual_mode: "stat_card" }), "horizontal")).toBe("none");
  });

  it("routes a short punch beat to kinetic", () => {
    expect(resolveSubtitleStyle(scene({ word_timestamps: words(2, 1000) }), "horizontal")).toBe("kinetic");
  });

  it("treats both threshold boundaries as inclusive", () => {
    // Exactly 6 words, exactly 3.0s -> still a punch beat.
    expect(resolveSubtitleStyle(scene({ word_timestamps: words(6, 3000) }), "horizontal")).toBe("kinetic");
  });

  it("rejects a punch beat that is one word too long", () => {
    expect(resolveSubtitleStyle(scene({ word_timestamps: words(7, 1500) }), "horizontal")).toBe("clean");
  });

  it("rejects a short scene that is drawn out past the span cap", () => {
    // 4 words but spread over 7.2s — short, but not a punch beat.
    expect(resolveSubtitleStyle(scene({ word_timestamps: words(4, 7200) }), "horizontal")).toBe("clean");
  });

  it("does not route on narration content", () => {
    // The deleted burst router fired on substrings like "but" / "then" / "turns out".
    expect(resolveSubtitleStyle(
      scene({ narration: "But then the real reason turns out to be simple." }),
      "horizontal",
    )).toBe("clean");
  });

  it("does not route on per-word pace", () => {
    // Fast delivery of many words is still clean — pace is not a term.
    expect(resolveSubtitleStyle(scene({ word_timestamps: words(20, 2400) }), "horizontal")).toBe("clean");
  });

  it("routes identically in both orientations", () => {
    const punchy = scene({ word_timestamps: words(3, 1200) });
    expect(resolveSubtitleStyle(punchy, "vertical")).toBe(resolveSubtitleStyle(punchy, "horizontal"));
  });

  it("falls back to clean for a scene with no word timings", () => {
    expect(resolveSubtitleStyle(scene({ word_timestamps: [] }), "horizontal")).toBe("clean");
  });

  it("falls back to clean when kinetic is disabled", () => {
    expect(resolveSubtitleStyle(
      scene({ word_timestamps: words(2, 1000) }),
      "horizontal",
      { enabledStyles: ["clean"] },
    )).toBe("clean");
    expect(resolveSubtitleStyle(
      scene({ subtitle_style: "kinetic" }),
      "horizontal",
      { enabledStyles: ["clean"] },
    )).toBe("clean");
  });

  it("suppresses subtitles when no styles are enabled", () => {
    expect(resolveSubtitleStyle(scene({}), "horizontal", { enabledStyles: [] })).toBe("none");
  });

  it("prefers backend-supplied thresholds over the built-in defaults", () => {
    const eightWords = scene({ word_timestamps: words(8, 2000) });
    expect(resolveSubtitleStyle(eightWords, "horizontal")).toBe("clean");
    expect(resolveSubtitleStyle(eightWords, "horizontal", {
      enabled_styles: ["clean", "kinetic"],
      kinetic_max_words: 8,
      kinetic_max_span_seconds: 3,
    })).toBe("kinetic");

    const punchy = scene({ word_timestamps: words(2, 1000) });
    expect(resolveSubtitleStyle(punchy, "horizontal", {
      enabled_styles: ["clean", "kinetic"],
      kinetic_max_words: 1,
      kinetic_max_span_seconds: 3,
    })).toBe("clean");
  });
});

describe("spokenSpanSeconds", () => {
  it("measures first word start to last word end", () => {
    expect(spokenSpanSeconds(words(4, 2500))).toBeCloseTo(2.5, 5);
  });

  it("is zero without timings", () => {
    expect(spokenSpanSeconds([])).toBe(0);
  });
});
