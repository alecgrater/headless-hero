import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { VisualTreatmentAssignment } from "../../api";
import type { Scene } from "../../types/script";
import VisualTreatmentReviewPanel, {
  EMPTY_VISUAL_MODE_COUNTS,
  VisualModeCatalog,
} from "./VisualTreatmentReviewPanel";

const assignments: VisualTreatmentAssignment[] = [
  {
    scene_id: "scene_001",
    visual_mode: "full_frame",
    reasoning: "Normal scene.",
    visual_layers: [],
  },
];

const mixedAssignments: VisualTreatmentAssignment[] = [
  ...assignments,
  {
    scene_id: "scene_002",
    visual_mode: "flipflop",
    reasoning: "Motion beat.",
    visual_layers: [
      { id: "scene_002_state_a", type: "image", asset_kind: "panel" },
      { id: "scene_002_state_b", type: "image", asset_kind: "panel" },
    ],
  },
  {
    scene_id: "scene_003",
    visual_mode: "flipflop",
    reasoning: "Motion beat.",
    visual_layers: [
      { id: "scene_003_state_a", type: "image", asset_kind: "panel" },
      { id: "scene_003_state_b", type: "image", asset_kind: "panel" },
    ],
  },
];

const scenes: Record<string, Scene> = {
  scene_001: {
    id: "scene_001",
    narration: "A normal illustrated scene.",
    visual_prompt: "A normal illustration.",
    duration_estimate_seconds: 6,
    is_title_card: false,
    image_url: "",
    audio_url: "",
    audio_duration_seconds: 6,
    visual_beat: "static",
    frame_directives: [],
    contains_person: false,
    frame_urls: [],
    visual_mode: "full_frame",
    visual_layers: [],
    caption_text: "",
    caption_emphasis: "",
  },
  scene_002: {
    id: "scene_002",
    narration: "Hands open and close.",
    visual_prompt: "Hands moving.",
    duration_estimate_seconds: 6,
    is_title_card: false,
    image_url: "",
    audio_url: "",
    audio_duration_seconds: 6,
    visual_beat: "flipflop",
    frame_directives: [],
    contains_person: false,
    frame_urls: [],
    visual_mode: "flipflop",
    visual_layers: [],
    caption_text: "",
    caption_emphasis: "",
  },
  scene_003: {
    id: "scene_003",
    narration: "The motion repeats.",
    visual_prompt: "Repeated motion.",
    duration_estimate_seconds: 6,
    is_title_card: false,
    image_url: "",
    audio_url: "",
    audio_duration_seconds: 6,
    visual_beat: "flipflop",
    frame_directives: [],
    contains_person: false,
    frame_urls: [],
    visual_mode: "flipflop",
    visual_layers: [],
    caption_text: "",
    caption_emphasis: "",
  },
};

describe("VisualTreatmentReviewPanel", () => {
  it("does not offer video as a manual layered visual-mode choice", () => {
    render(
      <VisualTreatmentReviewPanel
        assignments={assignments}
        scenes={scenes}
        onApply={vi.fn()}
      />,
    );

    const select = screen.getByRole("combobox");

    expect(within(select).queryByRole("option", { name: "Video" })).not.toBeInTheDocument();
    expect(within(select).getByRole("option", { name: "Full frame" })).toBeInTheDocument();
    expect(within(select).getByRole("option", { name: "Multi-frame" })).toBeInTheDocument();
    expect(within(select).getByRole("option", { name: "Continuous" })).toBeInTheDocument();
  });

  it("shows existing video assignments as read-only instead of a manual option", () => {
    render(
      <VisualTreatmentReviewPanel
        assignments={[
          {
            scene_id: "scene_001",
            visual_mode: "video",
            reasoning: "AI video candidate.",
            visual_layers: [],
          },
        ]}
        scenes={{
          scene_001: {
            ...scenes.scene_001,
            visual_mode: "video",
            video_url: "/static/projects/script-1/video/scene_001.mp4",
          },
        }}
        onApply={vi.fn()}
      />,
    );

    const select = screen.getByRole("combobox");

    expect(select).toBeDisabled();
    expect(within(select).getByRole("option", { name: "Video" })).toBeDisabled();
  });

  it("offers captions as a manual visual-mode choice", () => {
    render(
      <VisualTreatmentReviewPanel
        assignments={assignments}
        scenes={scenes}
        onApply={vi.fn()}
      />,
    );

    const select = screen.getByRole("combobox");

    expect(select).not.toBeDisabled();
    expect(within(select).getByRole("option", { name: "Captions" })).toBeInTheDocument();
  });

  it("does not render its own analyze button", () => {
    render(
      <VisualTreatmentReviewPanel
        assignments={assignments}
        scenes={scenes}
        onApply={vi.fn()}
      />,
    );

    expect(screen.queryByRole("button", { name: /analyze/i })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Apply" })).toBeInTheDocument();
  });

  it("shows count badges for every visual mode", () => {
    render(
      <VisualTreatmentReviewPanel
        assignments={mixedAssignments}
        scenes={scenes}
        onApply={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("Full frame scenes")).toHaveTextContent("1");
    expect(screen.getByLabelText("Full frame scenes")).toHaveClass("border-blue-300/70");
    expect(screen.getByLabelText("Full frame scenes")).toHaveClass("bg-blue-700");
    expect(screen.getByLabelText("Full frame scenes")).toHaveClass("text-yellow-300");
    expect(screen.getByLabelText("Flipflop scenes")).toHaveTextContent("2");
    expect(screen.getByLabelText("Captions scenes")).toHaveTextContent("0");
    expect(screen.getByLabelText("Video scenes")).toHaveTextContent("0");
  });

  it("shows duration profile labels in the visual mode catalog", () => {
    render(
      <VisualModeCatalog counts={{ ...EMPTY_VISUAL_MODE_COUNTS, comparison_board: 1 }} />,
    );

    expect(screen.getAllByText(/Extended target/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/Comparison board/i)).toBeInTheDocument();
  });
});
