import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import DiscoverPage from "./DiscoverPage";

vi.mock("./ForYouTab", () => ({
  default: () => <div>For You panel</div>,
}));

vi.mock("./TrendingTab", () => ({
  default: () => <div>Trending panel</div>,
}));

vi.mock("./WhitespaceTab", () => ({
  default: () => <div>Whitespace panel</div>,
}));

vi.mock("../ideas/IdeaPage", () => ({
  default: () => <div>Saved Ideas panel</div>,
}));

describe("DiscoverPage", () => {
  it("shows saved ideas as a nested discover tab", async () => {
    render(
      <DiscoverPage
        onGenerateIdeas={vi.fn()}
        onGenerateSavedIdeas={vi.fn()}
      />,
    );

    expect(screen.getByText("For You panel").parentElement).toHaveClass("block");
    expect(screen.getByText("Saved Ideas panel").parentElement).toHaveClass("hidden");

    await userEvent.click(screen.getByRole("button", { name: "Ideas" }));

    expect(screen.getByText("For You panel").parentElement).toHaveClass("hidden");
    expect(screen.getByText("Saved Ideas panel").parentElement).toHaveClass("block");
  });
});
