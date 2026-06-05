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
  it("renders exports, publishing, and advanced controls on the General page", async () => {
    render(createElement(GeneralSection, { panel: "general", showHeader: false }));

    const exportsHeading = await screen.findByRole("heading", { name: "Exports", level: 3 });
    const publishingHeading = screen.getByRole("heading", { name: "Publishing", level: 3 });
    const advancedHeading = screen.getByRole("heading", { name: "Advanced", level: 3 });
    const youtubeHeading = screen.getByRole("heading", { name: "YouTube Shorts", level: 3 });
    const workflowHeading = await screen.findByRole("heading", { name: "Workflow", level: 3 });

    for (const sectionHeading of [exportsHeading, publishingHeading, advancedHeading]) {
      expect(sectionHeading).toHaveClass("text-xl", "font-semibold", "tracking-tight");
      expect(sectionHeading).not.toHaveClass("text-base");
      expect(sectionHeading.parentElement).toHaveClass("rounded-2xl", "border", "border-violet-500/40", "bg-violet-500/5", "px-4", "py-3");
    }
    for (const subsectionHeading of [youtubeHeading, workflowHeading]) {
      expect(subsectionHeading).toHaveClass("text-sm", "font-semibold");
      expect(subsectionHeading).not.toHaveClass("text-base");
      expect(subsectionHeading).not.toHaveClass("text-lg");
    }

    expect(screen.getByRole("heading", { name: "Rendering", level: 3 })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Image Generation Safety", level: 3 })).toBeInTheDocument();
  });

  it("renders visuals as separate settings sections with the parent heading treatment", async () => {
    const { container } = render(createElement(GeneralSection, { panel: "visuals", showHeader: false }));

    const imageProviderHeading = await screen.findByRole("heading", { name: "Image Provider", level: 3 });
    const aiVideoHeading = screen.getByRole("heading", { name: "AI Video", level: 3 });
    const sceneStructureHeading = screen.getByRole("heading", { name: "Scene Structure", level: 3 });

    for (const heading of [imageProviderHeading, aiVideoHeading, sceneStructureHeading]) {
      expect(heading).toHaveClass("text-xl", "font-semibold", "tracking-tight");
      expect(heading).not.toHaveClass("text-sm");
      expect(heading).not.toHaveClass("text-base");
      expect(heading.parentElement).toHaveClass("rounded-2xl", "border", "border-violet-500/40", "bg-violet-500/5", "px-4", "py-3");
    }
    expect(container.querySelector(".divide-y")).toBeNull();
  });
});
