import { render, screen, within } from "@testing-library/react";
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
  it("displays preserved specialized modes intentionally", () => {
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
    expect(screen.getByText("Dossier")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /re-analyze/i })).not.toBeInTheDocument();
    const select = screen.getByRole("combobox");
    expect(within(select).getByRole("option", { name: "Dossier (preserved)" })).toBeInTheDocument();
  });
});
