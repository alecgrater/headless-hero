import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { VideoFormat } from "../../../types/format";
import ScriptTypesSection from "./ScriptTypesSection";

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
    supported_visual_modes: ["full_frame", "captions", "stat_card"],
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
    supported_visual_modes: ["full_frame"],
    allowed_visual_beats: ["continuous", "multi_frame", "static"],
    max_consecutive_same_beat: 2,
    target_distribution: { static: [0.45, 0.6] },
    reference_notes: [{ category: "Visuals", text: "captions and stat_card are disabled." }],
  },
];

vi.mock("../../../api", () => ({
  getFormats: vi.fn(async () => FORMATS),
}));

describe("ScriptTypesSection", () => {
  it("renders a column per format and the gotchas notes", async () => {
    render(<ScriptTypesSection />);
    await waitFor(() => expect(screen.getAllByText("Educational Listicle").length).toBeGreaterThan(0));
    expect(screen.getAllByText("Your Life As A...").length).toBeGreaterThan(0);
    expect(screen.getByText("captions and stat_card are disabled.")).toBeInTheDocument();
    const disabledChip = screen.getByTestId("disabled-mode-life-as-a-captions");
    expect(disabledChip).toBeInTheDocument();
  });
});
