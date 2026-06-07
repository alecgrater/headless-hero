import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import IdeaPage from "./IdeaPage";

vi.mock("../../api", () => ({
  getIdeas: vi.fn(),
  createIdea: vi.fn(),
  updateIdea: vi.fn(),
  deleteIdea: vi.fn(),
  getIdeaCounts: vi.fn(),
  getIdeaCategories: vi.fn(),
}));

const api = await import("../../api");

describe("IdeaPage", () => {
  beforeEach(() => {
    vi.mocked(api.getIdeas).mockResolvedValue([]);
    vi.mocked(api.getIdeaCounts).mockResolvedValue({ idea: 0, in_progress: 0, scripted: 0, published: 0 });
    vi.mocked(api.getIdeaCategories).mockResolvedValue([]);
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("loads ideas as a newest-first queue without unused scoring or priority controls", async () => {
    render(<IdeaPage onGenerateIdeas={vi.fn()} />);

    await waitFor(() => {
      expect(api.getIdeas).toHaveBeenCalledWith("newest", undefined, undefined);
    });

    expect(screen.getByRole("heading", { name: "Ideas" })).toBeInTheDocument();
    expect(screen.queryByText(/hook score/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/priority/i)).not.toBeInTheDocument();
    expect(screen.queryByText("Idea (0)")).not.toBeInTheDocument();
    expect(screen.queryByText(/auto-scored/i)).not.toBeInTheDocument();
  });
});
