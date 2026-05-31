import { render, screen } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it, vi } from "vitest";

import GeneralSection from "./GeneralSection";

vi.mock("../../api", () => ({
  default: {
    get: vi.fn(async () => ({
      ok: true,
      status: 200,
      data: {
        IMAGE_PROVIDER: { masked: "google" },
        AI_VIDEO_ENABLED: { masked: "true" },
        AI_VIDEO_PROVIDER: { masked: "fal" },
        AI_VIDEO_SCENES_PER_SEGMENT: { masked: "2" },
        LIFE_AS_A_SCENE_CHUNKING_ENABLED: { masked: "true" },
        LIFE_AS_A_TARGET_SCENE_SECONDS: { masked: "8" },
        LIFE_AS_A_MAX_SCENE_SECONDS: { masked: "15" },
        LIFE_AS_A_SINGLE_VISUAL_MAX_SECONDS: { masked: "8" },
      },
    })),
    put: vi.fn(async () => ({ ok: true, status: 200, data: {} })),
  },
}));

describe("GeneralSection visuals layout", () => {
  it("renders visuals as separate settings sections with the subtitle heading scale", async () => {
    const { container } = render(createElement(GeneralSection, { panel: "visuals", showHeader: false }));

    const imageProviderHeading = await screen.findByRole("heading", { name: "Image Provider", level: 3 });
    const aiVideoHeading = screen.getByRole("heading", { name: "AI Video", level: 3 });
    const sceneStructureHeading = screen.getByRole("heading", { name: "Scene Structure", level: 3 });

    for (const heading of [imageProviderHeading, aiVideoHeading, sceneStructureHeading]) {
      expect(heading).toHaveClass("text-base", "font-semibold");
      expect(heading).not.toHaveClass("text-sm");
      expect(heading).not.toHaveClass("text-lg");
    }
    expect(container.querySelector(".divide-y")).toBeNull();
  });
});
