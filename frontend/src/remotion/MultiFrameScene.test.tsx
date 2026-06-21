import { render, screen } from "@testing-library/react";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { SceneInput } from "@remotion-src/types";

vi.mock("remotion", () => ({
  Img: ({ src, style }: { src: string; style?: React.CSSProperties }) => <img src={src} style={style} alt="" />,
  interpolate: (input: number, range: number[], output: number[]) => {
    if (input <= range[0]) return output[0];
    if (input >= range[1]) return output[1];
    const progress = (input - range[0]) / (range[1] - range[0]);
    return output[0] + progress * (output[1] - output[0]);
  },
  useCurrentFrame: vi.fn(),
  useVideoConfig: vi.fn(),
}));

import { useCurrentFrame, useVideoConfig } from "remotion";
import { MultiFrameScene } from "@remotion-src/scenes/MultiFrameScene";

describe("MultiFrameScene", () => {
  beforeEach(() => {
    vi.mocked(useCurrentFrame).mockReturnValue(15);
    vi.mocked(useVideoConfig).mockReturnValue({ durationInFrames: 90, fps: 30 } as ReturnType<typeof useVideoConfig>);
  });

  it("draws the approved blink overlay over media-backed frame scenes", () => {
    const scene = {
      id: "scene_001",
      narration: "A worker waits.",
      duration_seconds: 3,
      is_title_card: false,
      visual_mode: "multi_frame",
      frame_paths: ["/tmp/frame-0.png", "/tmp/frame-1.png"],
      full_frame_blink: {
        enabled: true,
        action: "blink",
        anchor: {
          detected: true,
          skin_fill: "#F0D2B4",
          eye_left: { x: 0.4, y: 0.3, width: 0.01, height: 0.01 },
          eye_right: { x: 0.46, y: 0.3, width: 0.01, height: 0.01 },
          mouth: { x: 0.43, y: 0.38, width: 0.02, height: 0.01 },
          brow_left: { x: 0.4, y: 0.26, width: 0.02, height: 0.004 },
          brow_right: { x: 0.46, y: 0.26, width: 0.02, height: 0.004 },
        },
      },
    } satisfies SceneInput;

    render(<MultiFrameScene scene={scene} />);

    expect(screen.getByTestId("multi-frame-blink-overlay")).toBeInTheDocument();
  });
});
