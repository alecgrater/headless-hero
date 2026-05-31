import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { VisualTreatmentAssignment } from "../../api";
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

function renderTab(onAnalyzeVisualTreatments = vi.fn()) {
  render(
    <MediaSourcesTab
      scriptId="script-1"
      content={content}
      mediaAssignments={null}
      mediaAnalyzing={false}
      mediaReviewDismissed={false}
      visualTreatmentAssignments={assignments}
      visualTreatmentAnalyzing={false}
      onAnalyzeVisualTreatments={onAnalyzeVisualTreatments}
      onApplyVisualTreatments={vi.fn()}
      onAnalyzeMedia={vi.fn()}
      onBeforeAssignmentsApply={vi.fn()}
      onAssignmentsSaved={vi.fn()}
      onApproved={vi.fn()}
    />,
  );
}

describe("MediaSourcesTab", () => {
  it("shows one visual-mode reassessment button when review assignments exist", () => {
    const onAnalyzeVisualTreatments = vi.fn();
    renderTab(onAnalyzeVisualTreatments);

    const buttons = screen.getAllByRole("button", { name: "Re-analyze Visual Mode Review" });

    expect(buttons).toHaveLength(1);
    fireEvent.click(buttons[0]);
    expect(onAnalyzeVisualTreatments).toHaveBeenCalledTimes(1);
  });
});
