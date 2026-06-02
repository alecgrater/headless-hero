import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { VideoFormat } from "../../types/format";
import DocsPage from "./DocsPage";

const ALL_MODES = [
  "full_frame",
  "continuous",
  "multi_frame",
  "video",
  "popup_sequence",
  "flipflop",
  "comparison_board",
  "captions",
  "stat_card",
];

const FORMATS: VideoFormat[] = [
  {
    id: "youtube-listicle",
    display_name: "Educational Listicle",
    short_description: "8 standalone segments.",
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
];

vi.mock("../../api", () => ({
  getFormats: vi.fn(async () => FORMATS),
}));

describe("DocsPage", () => {
  it("starts on workflow docs and opens moved reference pages from the docs sidebar", async () => {
    render(<DocsPage />);

    expect(screen.getByText("End-to-End Workflow")).toBeInTheDocument();
    expect(screen.getByText("Final Review Checklist")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Script Types" }));
    await waitFor(() => expect(screen.getByText("Format Comes First")).toBeInTheDocument());
    expect(screen.getAllByText("Educational Listicle").length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Visual Modes" }));
    expect(screen.getByText("Planned Before Voiceover")).toBeInTheDocument();
    expect(screen.getByText("Renderer Owns Text")).toBeInTheDocument();
  });
});
