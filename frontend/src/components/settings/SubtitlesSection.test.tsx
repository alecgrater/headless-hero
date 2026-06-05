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
        SUBTITLE_STYLE_CLEAN_ENABLED: { masked: "false" },
        SUBTITLE_STYLE_KINETIC_ENABLED: { masked: "true" },
        SUBTITLE_STYLE_BURST_ENABLED: { masked: "false" },
      },
    })),
    put: vi.fn(async () => ({ ok: true, status: 200, data: {} })),
  },
}));

describe("SubtitlesSection settings", () => {
  it("maps settings rows into coverage and enabled styles", () => {
    expect(subtitleSettingsFromResponse({
      SUBTITLE_COVERAGE_MODE: { masked: "punchy" },
      SUBTITLE_STYLE_CLEAN_ENABLED: { masked: "false" },
      SUBTITLE_STYLE_KINETIC_ENABLED: { masked: "true" },
      SUBTITLE_STYLE_BURST_ENABLED: { masked: "0" },
    })).toEqual({
      coverage: "punchy",
      enabledStyles: ["kinetic"],
    });
  });

  it("builds a save payload for coverage and style gates", () => {
    expect(subtitleSettingsPayload({
      coverage: "all",
      enabledStyles: ["clean", "burst"],
    })).toEqual({
      SUBTITLE_COVERAGE_MODE: "all",
      SUBTITLE_STYLE_CLEAN_ENABLED: "true",
      SUBTITLE_STYLE_KINETIC_ENABLED: "false",
      SUBTITLE_STYLE_BURST_ENABLED: "true",
    });
  });

  it("renders visual style toggles and saves the selected behavior", async () => {
    render(createElement(SubtitlesSection));

    expect(await screen.findByText("Subtitle Coverage")).toBeTruthy();
    expect(screen.getByText("Punchiest 20% only")).toBeTruthy();
    expect(screen.getByText("Enabled Subtitle Styles")).toBeTruthy();
    expect(screen.getByText("Clean")).toBeTruthy();
    expect(screen.getByText("Kinetic Cards")).toBeTruthy();
    expect(screen.getByText("Burst")).toBeTruthy();
    expect(screen.getByText("changes")).toBeTruthy();
    expect(screen.getByText("why")).toBeTruthy();

    const coverageChoice = screen.getByRole("button", { name: /Punchiest 20% only/i });
    expect(coverageChoice).toHaveClass("border-l-2", "border-violet-400");
    expect(coverageChoice).not.toHaveClass("rounded-xl", "border", "bg-violet-500/10");

    const cleanStyle = screen.getByRole("button", { name: /Clean/i });
    expect(cleanStyle).toHaveClass("border-l-2");
    expect(cleanStyle).not.toHaveClass("rounded-xl", "border", "bg-sky-500/10");

    fireEvent.click(screen.getByRole("button", { name: /All non-caption scenes/i }));
    fireEvent.click(screen.getByRole("button", { name: /Clean/i }));
    fireEvent.click(screen.getByRole("button", { name: /Kinetic Cards/i }));
    fireEvent.click(screen.getByRole("button", { name: /Save Changes/i }));

    await waitFor(() => {
      expect(api.put).toHaveBeenCalledWith("/api/settings/keys", {
        SUBTITLE_COVERAGE_MODE: "all",
        SUBTITLE_STYLE_CLEAN_ENABLED: "true",
        SUBTITLE_STYLE_KINETIC_ENABLED: "false",
        SUBTITLE_STYLE_BURST_ENABLED: "false",
      });
    });
  });
});
