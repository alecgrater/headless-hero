import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SubtitleOverlay } from "@remotion-src/effects/typography/Subtitles";
import type { SceneInput, WordTimestamp } from "@remotion-src/types";

let currentFrame = 12;

vi.mock("@remotion/google-fonts/Inter", () => ({
  loadFont: () => ({ fontFamily: "Inter" }),
}));

vi.mock("remotion", () => ({
  // Piecewise-linear interpolate with clamping; handles 2- and 3-point ranges.
  interpolate: (input: number, inputRange: number[], outputRange: number[]) => {
    const clamped = Math.min(Math.max(input, inputRange[0]), inputRange[inputRange.length - 1]);
    for (let i = 0; i < inputRange.length - 1; i++) {
      if (clamped <= inputRange[i + 1]) {
        const span = inputRange[i + 1] - inputRange[i];
        const progress = span === 0 ? 1 : (clamped - inputRange[i]) / span;
        return outputRange[i] + (outputRange[i + 1] - outputRange[i]) * progress;
      }
    }
    return outputRange[outputRange.length - 1];
  },
  useCurrentFrame: () => currentFrame,
  useVideoConfig: () => ({ fps: 30 }),
}));

const evenWords = (count: number, spanMs: number): WordTimestamp[] => {
  const step = spanMs / count;
  return Array.from({ length: count }, (_, i) => ({
    word: `word${i}`,
    start_ms: Math.round(i * step),
    end_ms: Math.round((i + 1) * step),
  }));
};

/** 7 words -> over the kinetic word cap -> routes clean. */
const cleanScene = (overrides: Partial<SceneInput> = {}): SceneInput => ({
  id: "scene",
  narration: "The myth says Talent is the reason.",
  duration_seconds: 4,
  is_title_card: false,
  visual_mode: "full_frame",
  word_timestamps: [
    { word: "The", start_ms: 0, end_ms: 120 },
    { word: "myth", start_ms: 130, end_ms: 260 },
    { word: "says", start_ms: 270, end_ms: 380 },
    { word: "Talent", start_ms: 390, end_ms: 720 },
    { word: "is", start_ms: 730, end_ms: 850 },
    { word: "the", start_ms: 860, end_ms: 970 },
    { word: "reason.", start_ms: 980, end_ms: 1220 },
  ],
  ...overrides,
});

/** 3 words in 1.2s -> a punch beat -> routes kinetic. */
const kineticScene = (overrides: Partial<SceneInput> = {}): SceneInput => ({
  id: "punch",
  narration: "Her finding surprised.",
  duration_seconds: 2,
  is_title_card: false,
  visual_mode: "full_frame",
  word_timestamps: evenWords(3, 1200),
  ...overrides,
});

function renderedWordSpans(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll("span")) as HTMLElement[];
}

function wordGroup(container: HTMLElement): HTMLElement {
  const span = container.querySelector("span");
  if (!span?.parentElement) throw new Error("no rendered subtitle words");
  return span.parentElement;
}

describe("SubtitleOverlay", () => {
  it("routes a long scene to clean and keeps its plate", () => {
    currentFrame = 14;
    const { container } = render(<SubtitleOverlay scene={cleanScene()} highlightEnabled />);

    expect(getComputedStyle(wordGroup(container)).backgroundColor).toBe("rgba(0, 0, 0, 0.52)");
    // Active word is recoloured, not resized.
    expect(getComputedStyle(screen.getByText("Talent")).color).toBe("rgb(250, 204, 21)");
    expect(getComputedStyle(screen.getByText("myth")).color).toBe("rgb(255, 255, 255)");
  });

  it("routes a short punch beat to kinetic with no plate", () => {
    currentFrame = 14;
    const { container } = render(<SubtitleOverlay scene={kineticScene()} highlightEnabled />);

    const background = getComputedStyle(wordGroup(container)).backgroundColor;
    expect(background === "" || background === "rgba(0, 0, 0, 0)").toBe(true);
    // Kinetic runs larger than clean's base size.
    const size = parseFloat(getComputedStyle(renderedWordSpans(container)[0]).fontSize);
    expect(size).toBeGreaterThan(52);
  });

  it("never varies font size or weight within a phrase", () => {
    // This is the invariant that the deleted `burst` style violated: a per-word size
    // change reflows the line as the active word moves.
    for (const scene of [cleanScene(), kineticScene()]) {
      currentFrame = 14;
      const { container, unmount } = render(<SubtitleOverlay scene={scene} highlightEnabled />);
      const spans = renderedWordSpans(container);
      expect(spans.length).toBeGreaterThan(1);
      const sizes = new Set(spans.map((s) => getComputedStyle(s).fontSize));
      const weights = new Set(spans.map((s) => getComputedStyle(s).fontWeight));
      expect(sizes.size).toBe(1);
      expect(weights.size).toBe(1);
      unmount();
    }
  });

  it("renders both styles in the loaded Inter face", () => {
    for (const scene of [cleanScene(), kineticScene()]) {
      currentFrame = 14;
      const { container, unmount } = render(<SubtitleOverlay scene={scene} highlightEnabled />);
      for (const span of renderedWordSpans(container)) {
        expect(getComputedStyle(span).fontFamily).toContain("Inter");
      }
      unmount();
    }
  });

  it("renders nothing for suppressed scenes", () => {
    currentFrame = 14;
    const { container } = render(
      <SubtitleOverlay scene={cleanScene({ visual_mode: "stat_card" })} highlightEnabled />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("renders nothing without word timings", () => {
    currentFrame = 14;
    const { container } = render(
      <SubtitleOverlay scene={cleanScene({ word_timestamps: [] })} highlightEnabled />,
    );
    expect(container.firstChild).toBeNull();
  });
});
