import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { VideoFormat } from "../../../types/format";
import ScriptTypesSection from "./ScriptTypesSection";

const ALL_MODES = [
  "full_frame",
  "continuous",
  "multi_frame",
  "video",
  "popup_sequence",
  "comparison_board",
  "captions",
  "stat_card",
];

const FORMATS: VideoFormat[] = [
  {
    id: "youtube-listicle",
    display_name: "Educational Listicle",
    short_description: "8 things…",
    level_count_min: 8,
    level_count_max: 8,
    level_label: "segment",
    supports_cold_open: true,
    supports_hook_scoring: true,
    supports_segmented_generation: true,
    title_card_strategy_kind: "composite-grid",
    supported_visual_modes: ALL_MODES,
    allowed_visual_beats: ["continuous", "multi_frame", "static"],
    max_consecutive_same_beat: 3,
    target_distribution: {},
    reference_notes: [{ category: "Narration", text: "Segments stand alone." }],
  },
  {
    id: "life-as-a",
    display_name: "Your Life As A...",
    short_description: "A walk through stages…",
    level_count_min: 4,
    level_count_max: 7,
    level_label: "level",
    supports_cold_open: true,
    supports_hook_scoring: false,
    supports_segmented_generation: true,
    title_card_strategy_kind: "cinematic-chapters",
    supported_visual_modes: ALL_MODES,
    allowed_visual_beats: ["continuous", "multi_frame", "static"],
    max_consecutive_same_beat: 3,
    target_distribution: {},
    reference_notes: [{ category: "Visuals", text: "All modes route by scene fit." }],
  },
];

vi.mock("../../../api", () => ({
  getFormats: vi.fn(async () => FORMATS),
}));

describe("ScriptTypesSection", () => {
  it("renders wrapping format cards and details for the selected format", async () => {
    render(<ScriptTypesSection />);
    await waitFor(() => expect(screen.getAllByText("Educational Listicle").length).toBeGreaterThan(0));
    expect(screen.getAllByText("Your Life As A...").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: /Your Life As A/i }));

    expect(screen.getByText("All modes route by scene fit.")).toBeInTheDocument();
    expect(screen.getByTestId("mode-life-as-a-captions")).toBeInTheDocument();
    expect(screen.queryByTestId("disabled-mode-life-as-a-captions")).not.toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("navigates to Visual Modes when a detailed mode chip is clicked", async () => {
    const onOpen = vi.fn();
    render(<ScriptTypesSection onOpenVisualModes={onOpen} />);
    await waitFor(() => expect(screen.getByTestId("mode-youtube-listicle-full_frame")).toBeInTheDocument());
    const chip = screen.getByTestId("mode-youtube-listicle-full_frame");
    expect(chip.tagName).toBe("BUTTON");
    fireEvent.click(chip);
    expect(onOpen).toHaveBeenCalledTimes(1);
  });

  it("shows an error message when formats fail to load", async () => {
    const { getFormats } = await import("../../../api");
    vi.mocked(getFormats).mockRejectedValueOnce(new Error("boom"));
    render(<ScriptTypesSection />);
    await waitFor(() => expect(screen.getByText("Could not load script formats.")).toBeInTheDocument());
  });
});
