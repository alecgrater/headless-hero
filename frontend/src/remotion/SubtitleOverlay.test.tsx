import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SubtitleOverlay } from "@remotion-src/effects/typography/Subtitles";
import type { SceneInput } from "@remotion-src/types";

let currentFrame = 12;

vi.mock("remotion", () => ({
  interpolate: (
    input: number,
    inputRange: [number, number, number],
    outputRange: [number, number, number],
  ) => {
    const [inMin, inMid, inMax] = inputRange;
    const [outMin, outMid, outMax] = outputRange;
    if (input <= inMid) {
      const progress = (input - inMin) / Math.max(1, inMid - inMin);
      return outMin + (outMid - outMin) * Math.min(1, Math.max(0, progress));
    }
    const progress = (input - inMid) / Math.max(1, inMax - inMid);
    return outMid + (outMax - outMid) * Math.min(1, Math.max(0, progress));
  },
  useCurrentFrame: () => currentFrame,
  useVideoConfig: () => ({ fps: 30 }),
}));

const scene = (overrides: Partial<SceneInput> = {}): SceneInput => ({
  id: "scene",
  narration: "The myth says Talent is the reason.",
  duration_seconds: 4,
  is_title_card: false,
  subtitle_style: "burst",
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

describe("SubtitleOverlay", () => {
  it("keeps burst emphasis bigger without display-font uppercase styling", () => {
    currentFrame = 14;

    render(
      <SubtitleOverlay
        scene={scene()}
        highlightEnabled
        orientation="vertical"
      />,
    );

    const activeWord = screen.getByText("Talent");
    const inactiveWord = screen.getByText("myth");
    const activeStyle = getComputedStyle(activeWord);
    const inactiveStyle = getComputedStyle(inactiveWord);

    expect(activeStyle.textTransform).not.toBe("uppercase");
    expect(activeStyle.fontFamily).toContain("Inter");
    expect(parseFloat(activeStyle.fontSize)).toBeGreaterThan(parseFloat(inactiveStyle.fontSize));
    expect(parseFloat(activeStyle.fontSize)).toBeLessThanOrEqual(76);
    expect(inactiveStyle.color).toBe("rgb(244, 244, 245)");
  });
});
