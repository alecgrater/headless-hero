import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { MediaAssignment } from "../../api";
import type { Scene } from "../../types/script";
import MediaReviewPanel from "./MediaReviewPanel";

const baseScene: Scene = {
  id: "scene_001",
  narration: "A case board connects the names.",
  visual_prompt: "[CLOSE-UP] Abstract evidence on a desk with no readable text",
  duration_estimate_seconds: 6,
  is_title_card: false,
  audio_duration_seconds: 6,
  visual_mode: "dossier",
};

describe("MediaReviewPanel", () => {
  it("offers every visual mode as a scene override", () => {
    const assignments: MediaAssignment[] = [
      {
        scene_id: "scene_001",
        visual_mode: "dossier",
        game_name: null,
        search_query: null,
        reasoning: "Preserved script mode.",
      },
    ];

    render(
      <MediaReviewPanel
        scriptId="script-1"
        assignments={assignments}
        scenes={{ scene_001: baseScene }}
        onApproved={vi.fn()}
      />,
    );

    expect(screen.getByText((_, element) => element?.textContent === "1 scenes: 1 Dossier")).toBeInTheDocument();
    expect(screen.getAllByText("Dossier").length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /re-analyze/i })).not.toBeInTheDocument();
    const select = screen.getByRole("combobox");
    const expectedModes = [
      "Full frame",
      "Multi-frame",
      "Continuous",
      "Video",
      "Popup sequence",
      "Flipflop",
      "Comparison board",
      "Captions",
      "Stat card",
      "Dossier",
    ];
    expect(within(select).getAllByRole("option").map((option) => option.textContent)).toEqual(expectedModes);
  });

  it("applies an arbitrary visual mode override", () => {
    const assignments: MediaAssignment[] = [
      {
        scene_id: "scene_001",
        visual_mode: "full_frame",
        game_name: null,
        search_query: null,
        reasoning: "Normal scene.",
      },
    ];

    render(
      <MediaReviewPanel
        scriptId="script-1"
        assignments={assignments}
        scenes={{ scene_001: { ...baseScene, visual_mode: "full_frame" } }}
        onApproved={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "dossier" } });

    expect(screen.getByRole("combobox")).toHaveValue("dossier");
    expect(screen.getAllByText("Dossier").length).toBeGreaterThan(0);
  });
});
