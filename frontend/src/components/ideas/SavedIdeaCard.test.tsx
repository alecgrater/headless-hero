import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import SavedIdeaCard from "./SavedIdeaCard";
import type { Idea } from "../../types/idea";

const baseIdea: Idea = {
  id: "idea-1",
  text: "8 Internet mysteries nobody has fully explained",
  description: "A compact mystery roundup for a faceless video.",
  category: "Mystery",
  rank: 80,
  status: "idea",
  source: "manual",
  cold_open_status: "pending",
  cold_open_variants_json: "",
  selected_hook_json: "",
  hook_score: 80,
  hook_score_json: "",
  created_at: "2026-06-07T00:00:00Z",
};

describe("SavedIdeaCard", () => {
  it("presents an idea without redundant idea, hook score, or priority controls", () => {
    render(
      <SavedIdeaCard
        idea={baseIdea}
        onUpdate={vi.fn()}
        onDelete={vi.fn()}
        onGenerateIdeas={vi.fn()}
      />,
    );

    expect(screen.getByText(baseIdea.text)).toBeInTheDocument();
    expect(screen.queryByText("Idea")).not.toBeInTheDocument();
    expect(screen.queryByText("hook")).not.toBeInTheDocument();
    expect(screen.queryByText("80")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Increase priority")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Decrease priority")).not.toBeInTheDocument();
  });

  it("keeps script generation as the primary row action", async () => {
    const onGenerateIdeas = vi.fn();
    const user = userEvent.setup();

    render(
      <SavedIdeaCard
        idea={baseIdea}
        onUpdate={vi.fn()}
        onDelete={vi.fn()}
        onGenerateIdeas={onGenerateIdeas}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Generate script ideas" }));

    expect(onGenerateIdeas).toHaveBeenCalledWith(baseIdea.text);
  });
});
