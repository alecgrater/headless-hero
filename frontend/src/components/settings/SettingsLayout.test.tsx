import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ApiKeysSection from "./ApiKeysSection";
import MiscSection from "./MiscSection";
import PublishingSection from "./PublishingSection";
import { normalizeSectionId, SECTIONS, SECTION_GROUPS } from "./SettingsPage";

vi.mock("../../api", () => ({
  default: {
    get: vi.fn(async (path: string) => {
      if (path === "/api/publish/oauth/status") {
        return {
          ok: true,
          status: 200,
          data: {
            youtube: { connected: false },
            tiktok: { connected: false },
            instagram: { connected: false },
          },
        };
      }
      return { ok: true, status: 200, data: {} };
    }),
    post: vi.fn(async () => ({ ok: true, status: 200, data: {} })),
    put: vi.fn(async () => ({ ok: true, status: 200, data: {} })),
    request: vi.fn(async () => ({ ok: true, status: 200, data: {} })),
  },
  openInBrowser: vi.fn(),
}));

describe("settings section layout", () => {
  it("uses a power-user settings taxonomy with General as the default landing section", () => {
    expect(SECTIONS[0]).toMatchObject({
      id: "general",
      label: "General",
      group: "Essentials",
    });
    expect(SECTION_GROUPS).toEqual([
      "Essentials",
      "AI & Generation",
      "Production",
    ]);
    expect(SECTIONS.map((section) => section.id)).toEqual([
      "general",
      "api-keys",
      "ai-models",
      "visuals",
      "subtitles",
      "voice",
      "brand-style",
      "asset-vault",
    ]);
    expect(normalizeSectionId(undefined)).toBe("general");
    expect(normalizeSectionId("storage")).toBe("general");
    expect(normalizeSectionId("audio")).toBe("voice");
    expect(normalizeSectionId("publishing")).toBe("general");
    expect(normalizeSectionId("advanced")).toBe("general");
    expect(normalizeSectionId("misc")).toBe("general");
    expect(SECTIONS.find((section) => section.id === "voice")).toMatchObject({
      label: "Narration",
      group: "Production",
    });
    expect(SECTIONS.find((section) => section.id === "brand-style")).toMatchObject({
      label: "Visual Identity",
      group: "Production",
    });
    expect(SECTIONS.find((section) => section.id === "asset-vault")).toMatchObject({
      label: "Assets",
      group: "Production",
    });
  });

  it("keeps API key group titles outside bordered control boxes", async () => {
    const { container } = render(<ApiKeysSection showHeader={false} />);

    const aiTextHeading = await screen.findByRole("heading", { name: "AI Text", level: 3 });
    expect(aiTextHeading).toHaveClass("text-xl", "font-semibold", "tracking-tight");
    expect(aiTextHeading).not.toHaveClass("text-sm");
    expect(aiTextHeading.parentElement).toHaveClass("-ml-4", "rounded-2xl", "border", "border-violet-500/40", "bg-violet-500/5", "px-4", "py-3");
    expect(screen.getByRole("heading", { name: "Anthropic", level: 3 })).toHaveClass("text-sm", "font-medium");
    expect(aiTextHeading.closest("section")).not.toHaveClass("bg-neutral-900", "border", "rounded-xl");
    expect(container.querySelector(".divide-y")).toBeNull();
  });

  it("keeps Advanced category titles outside bordered control boxes", async () => {
    const { container } = render(<MiscSection showHeader={false} />);

    const workflowHeading = await screen.findByRole("heading", { name: "Workflow", level: 3 });
    expect(workflowHeading).toHaveClass("text-xl", "font-semibold", "tracking-tight");
    expect(workflowHeading).not.toHaveClass("text-sm");
    expect(workflowHeading.parentElement).toHaveClass("-ml-4", "rounded-2xl", "border", "border-violet-500/40", "bg-violet-500/5", "px-4", "py-3");
    expect(screen.getByRole("heading", { name: "Hook Refinement", level: 3 })).toHaveClass("text-sm", "font-medium");
    expect(screen.getByRole("heading", { name: "Full-frame Blink Review", level: 3 })).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "Toggle full-frame Blink Review" })).toBeInTheDocument();
    expect(workflowHeading.closest("section")).not.toHaveClass("bg-neutral-900", "border", "rounded-xl");
    expect(container.querySelector(".divide-y")).toBeNull();
  });

  it("keeps Publishing platform titles outside their action boxes", async () => {
    render(<PublishingSection showHeader={false} />);

    const youtubeHeading = await screen.findByRole("heading", { name: "YouTube Shorts", level: 3 });
    expect(youtubeHeading).toHaveClass("text-xl", "font-semibold", "tracking-tight");
    expect(youtubeHeading).not.toHaveClass("text-sm");
    expect(youtubeHeading.parentElement).toHaveClass("-ml-4", "rounded-2xl", "border", "border-violet-500/40", "bg-violet-500/5", "px-4", "py-3");
    expect(youtubeHeading.closest("section")).not.toHaveClass("bg-neutral-900", "border", "rounded-xl");
    expect(screen.getByText("Uploads rendered shorts to your connected YouTube channel.")).toHaveClass("text-xs");
  });
});
