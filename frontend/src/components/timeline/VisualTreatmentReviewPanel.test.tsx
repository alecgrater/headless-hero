import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { VisualTreatmentAssignment } from "../../api";
import type { Scene } from "../../types/script";
import VisualTreatmentReviewPanel from "./VisualTreatmentReviewPanel";

const assignments: VisualTreatmentAssignment[] = [
  {
    scene_id: "scene_001",
    visual_mode: "full_frame",
    reasoning: "Normal scene.",
    visual_layers: [],
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
};

describe("VisualTreatmentReviewPanel", () => {
  it("does not offer video as a manual layered visual-mode choice", () => {
    render(
      <VisualTreatmentReviewPanel
        assignments={assignments}
        scenes={scenes}
        canAnalyze
        onApply={vi.fn()}
        onReanalyze={vi.fn()}
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
        canAnalyze
        onApply={vi.fn()}
        onReanalyze={vi.fn()}
      />,
    );

    const select = screen.getByRole("combobox");

    expect(select).toBeDisabled();
    expect(within(select).getByRole("option", { name: "Video" })).toBeDisabled();
  });
});
