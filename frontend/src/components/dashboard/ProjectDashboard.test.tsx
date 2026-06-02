import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import ProjectDashboard from "./ProjectDashboard";
import type { ScriptSummary } from "../../types/script";

const { ratedProject } = vi.hoisted(() => ({
  ratedProject: {
    id: "script-1",
    brand_id: "brand-1",
    topic_title: "Life as a Castle Guard",
    topic_description: "A day at the gate.",
    created_at: "2026-05-30T12:00:00Z",
    segment_count: 8,
    scene_count: 24,
    image_count: 0,
    audio_count: 0,
    has_renders: false,
    thumbnail_url: "",
    format_id: "life-as-a",
    status: "script",
    hook_score_overall: 78,
    script_rating_overall: 8.1,
    upload_tracking: {
      longform_youtube: false,
      shortform_youtube: false,
      shortform_instagram: false,
      shortform_tiktok: false,
    },
  } satisfies ScriptSummary,
}));

vi.mock("../../api", () => ({
  default: {
    get: vi.fn().mockResolvedValue({
      ok: true,
      data: [ratedProject],
    }),
  },
  assetUrl: (path: string) => path,
  setUploadTracking: vi.fn(),
}));

describe("ProjectDashboard", () => {
  it("shows script ratings clearly in both grid and row views", async () => {
    const user = userEvent.setup();

    render(
      <ProjectDashboard
        onNewVideo={vi.fn()}
        onOpenProject={vi.fn()}
      />,
    );

    await screen.findByText("Life as a Castle Guard");

    expect(screen.getByText("Rating")).toBeInTheDocument();
    const rowRating = screen.getByLabelText("Script rating 8.1 out of 10");
    expect(rowRating).toHaveTextContent("8.1");
    expect(rowRating).not.toHaveTextContent("Script");

    await user.click(screen.getByLabelText("Grid view"));

    const card = screen.getByRole("button", { name: /life as a castle guard/i });
    const cardRating = within(card).getByLabelText("Script rating 8.1 out of 10");
    expect(cardRating).toHaveTextContent("8.1");
    expect(cardRating).not.toHaveTextContent("Script");
  });
});
