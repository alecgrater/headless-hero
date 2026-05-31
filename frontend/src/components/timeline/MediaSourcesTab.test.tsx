import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { MediaAssignment, VisualTreatmentAssignment } from "../../api";
import type { Scene, ScriptContent } from "../../types/script";
import MediaSourcesTab from "./MediaSourcesTab";

const scene: Scene = {
  id: "scene_001",
  narration: "A normal illustrated scene.",
  visual_prompt: "A normal illustration.",
  duration_estimate_seconds: 6,
  is_title_card: false,
  image_url: "",
  audio_url: "",
  audio_duration_seconds: 6,
  word_timestamps: [{ word: "A", start_ms: 0, end_ms: 100 }],
  visual_beat: "static",
  frame_directives: [],
  contains_person: false,
  frame_urls: [],
  visual_mode: "full_frame",
  visual_layers: [],
  caption_text: "",
  caption_emphasis: "",
};

const content: ScriptContent = {
  title: "Visual Mode Test",
  segments: [{ name: "Segment", scenes: [scene] }],
};

const assignments: VisualTreatmentAssignment[] = [
  {
    scene_id: "scene_001",
    visual_mode: "full_frame",
    reasoning: "Normal scene.",
    visual_layers: [],
  },
];

const mediaAssignments: MediaAssignment[] = [
  {
    scene_id: "scene_001",
    visual_mode: "full_frame",
    game_name: null,
    search_query: null,
    reasoning: "Normal scene.",
  },
];

function renderTab({
  onAnalyzeVisualTreatments = vi.fn(),
  onAnalyzeMedia = vi.fn(),
  visualAssignments = assignments,
  media = mediaAssignments,
}: {
  onAnalyzeVisualTreatments?: () => void;
  onAnalyzeMedia?: () => void;
  visualAssignments?: VisualTreatmentAssignment[] | null;
  media?: MediaAssignment[] | null;
} = {}) {
  render(
    <MediaSourcesTab
      scriptId="script-1"
      content={content}
      mediaAssignments={media}
      mediaAnalyzing={false}
      mediaReviewDismissed={false}
      visualTreatmentAssignments={visualAssignments}
      visualTreatmentAnalyzing={false}
      onAnalyzeVisualTreatments={onAnalyzeVisualTreatments}
      onApplyVisualTreatments={vi.fn()}
      onAnalyzeMedia={onAnalyzeMedia}
      onBeforeAssignmentsApply={vi.fn()}
      onAssignmentsSaved={vi.fn()}
      onApproved={vi.fn()}
    />,
  );
}

describe("MediaSourcesTab", () => {
  it("shows one visual-mode reassessment button when review assignments exist", () => {
    const onAnalyzeVisualTreatments = vi.fn();
    const onAnalyzeMedia = vi.fn();
    renderTab({ onAnalyzeVisualTreatments, onAnalyzeMedia });

    const buttons = screen.getAllByRole("button", { name: "Re-analyze Visual Modes" });

    expect(buttons).toHaveLength(1);
    fireEvent.click(buttons[0]);
    expect(onAnalyzeVisualTreatments).toHaveBeenCalledTimes(1);
    expect(onAnalyzeMedia).toHaveBeenCalledTimes(1);
  });

  it("shows one visual-mode analysis button before assignments exist", () => {
    const onAnalyzeVisualTreatments = vi.fn();
    const onAnalyzeMedia = vi.fn();
    renderTab({
      onAnalyzeVisualTreatments,
      onAnalyzeMedia,
      visualAssignments: null,
      media: null,
    });

    const buttons = screen.getAllByRole("button", { name: "Analyze Visual Modes" });

    expect(buttons).toHaveLength(1);
    fireEvent.click(buttons[0]);
    expect(onAnalyzeVisualTreatments).toHaveBeenCalledTimes(1);
    expect(onAnalyzeMedia).toHaveBeenCalledTimes(1);
  });

  it("shows visual-mode count boxes before assignments exist", () => {
    renderTab({
      visualAssignments: null,
      media: null,
    });

    expect(screen.getByLabelText("Full frame scenes")).toHaveTextContent("0");
    expect(screen.getByLabelText("Multi-frame scenes")).toHaveTextContent("0");
    expect(screen.getByLabelText("Video scenes")).toHaveTextContent("0");
  });
});
