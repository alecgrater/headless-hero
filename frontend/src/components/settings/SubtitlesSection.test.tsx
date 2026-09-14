import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createElement } from "react";
import { describe, expect, it, vi } from "vitest";

import api from "../../api";
import SubtitlesSection, {
  subtitleSettingsFromResponse,
  subtitleSettingsPayload,
} from "./SubtitlesSection";

vi.mock("../../api", () => ({
  default: {
    get: vi.fn(async () => ({
      ok: true,
      status: 200,
      data: {
        SUBTITLE_COVERAGE_MODE: { masked: "punchy" },
        SUBTITLE_STYLE_KINETIC_ENABLED: { masked: "true" },
      },
    })),
    put: vi.fn(async () => ({ ok: true, status: 200, data: {} })),
  },
}));

describe("SubtitlesSection settings", () => {
  it("maps settings rows into coverage and enabled styles", () => {
    expect(subtitleSettingsFromResponse({
      SUBTITLE_COVERAGE_MODE: { masked: "punchy" },
      SUBTITLE_STYLE_KINETIC_ENABLED: { masked: "true" },
    })).toEqual({
      coverage: "punchy",
      enabledStyles: ["clean", "kinetic"],
    });
  });

  it("always keeps clean enabled, even with kinetic off", () => {
    expect(subtitleSettingsFromResponse({
      SUBTITLE_COVERAGE_MODE: { masked: "all" },
      SUBTITLE_STYLE_KINETIC_ENABLED: { masked: "0" },
    })).toEqual({
      coverage: "all",
      enabledStyles: ["clean"],
    });
  });

  it("ignores retired per-style keys", () => {
    expect(subtitleSettingsFromResponse({
      SUBTITLE_COVERAGE_MODE: { masked: "all" },
      SUBTITLE_STYLE_CLEAN_ENABLED: { masked: "false" },
      SUBTITLE_STYLE_BURST_ENABLED: { masked: "true" },
    })).toEqual({
      coverage: "all",
      enabledStyles: ["clean", "kinetic"],
    });
  });

  it("builds a save payload for coverage and the kinetic gate only", () => {
    expect(subtitleSettingsPayload({
      coverage: "all",
      enabledStyles: ["clean"],
    })).toEqual({
      SUBTITLE_COVERAGE_MODE: "all",
      SUBTITLE_STYLE_KINETIC_ENABLED: "false",
    });

    expect(subtitleSettingsPayload({
      coverage: "punchy",
      enabledStyles: ["clean", "kinetic"],
    })).toEqual({
      SUBTITLE_COVERAGE_MODE: "punchy",
      SUBTITLE_STYLE_KINETIC_ENABLED: "true",
    });
  });

  it("renders the two-style list and saves the selected behavior", async () => {
    render(createElement(SubtitlesSection));

    expect(await screen.findByText("Subtitle Coverage")).toBeTruthy();
    expect(screen.getByText("Punchiest 20% only")).toBeTruthy();
    expect(screen.getByText("Subtitle Styles")).toBeTruthy();
    expect(screen.getByText("Clean")).toBeTruthy();
    expect(screen.getByText("Kinetic accents")).toBeTruthy();
    expect(screen.getByText("Always on")).toBeTruthy();
    // Burst is gone from the catalogue entirely.
    expect(screen.queryByText("Burst")).toBeNull();

    const coverageSection = screen.getByTestId("subtitle-coverage-section");
    expect(coverageSection).toHaveClass("xl:grid-cols-[220px_minmax(0,1fr)]", "border-t", "border-neutral-800");

    const coverageChoice = screen.getByRole("button", { name: /Punchiest 20% only/i });
    expect(coverageChoice).toHaveClass("rounded-md", "bg-violet-500");
    expect(coverageChoice).not.toHaveClass("border-l-2", "rounded-xl");

    const styleSection = screen.getByTestId("subtitle-styles-section");
    expect(styleSection).toHaveClass("xl:grid-cols-[220px_minmax(0,1fr)]", "border-t", "border-neutral-800");

    // Clean is not a toggle — it has no button role.
    expect(screen.queryByRole("button", { name: /^Clean/i })).toBeNull();

    const kineticStyle = screen.getByRole("button", { name: /Kinetic accents/i });
    expect(kineticStyle).toHaveClass("bg-violet-500/10", "shadow-[0_18px_42px_rgba(139,92,246,0.18)]");
    expect(kineticStyle).toHaveClass("grid", "border-t");
    expect(kineticStyle).not.toHaveClass("rounded-xl", "border-l-2");

    expect(screen.getByTestId("kinetic-style-preview")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: /All non-caption scenes/i }));
    fireEvent.click(kineticStyle);

    expect(screen.queryByRole("button", { name: /Save Changes/i })).toBeNull();

    await waitFor(() => {
      expect(api.put).toHaveBeenCalledWith("/api/settings/keys", {
        SUBTITLE_COVERAGE_MODE: "all",
        SUBTITLE_STYLE_KINETIC_ENABLED: "false",
      });
    });
  });
});
