import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ScriptRating } from "../../types/script";
import ScriptRatingCard from "./ScriptRatingCard";

function rating(problemCount: number, majors = 0): ScriptRating {
  return {
    overall: 7,
    scores: { flow: 7, clarity: 8, human_sounding: 5, continuity: 8, format_fit: 8 },
    problems: Array.from({ length: problemCount }, (_, i) => ({
      category: "ai_tells" as const,
      scene: `scene_${i + 1}`,
      quote: `quoted line ${i + 1}`,
      problem: `problem ${i + 1}`,
      severity: i < majors ? ("major" as const) : ("minor" as const),
    })),
    worst_problem: "Formula closers.",
  };
}

describe("ScriptRatingCard", () => {
  it("shows the scores, the biggest issue, and quoted problems", () => {
    render(<ScriptRatingCard rating={rating(2, 1)} />);
    expect(screen.getByText("7.0")).toBeInTheDocument();
    expect(screen.getByText("Sounds human")).toBeInTheDocument();
    expect(screen.getByText("Formula closers.")).toBeInTheDocument();
    expect(screen.getByText("2 problems · 1 major")).toBeInTheDocument();
    expect(screen.getByText("“quoted line 1”")).toBeInTheDocument();
  });

  it("collapses long problem lists behind Show all", () => {
    render(<ScriptRatingCard rating={rating(9)} />);
    expect(screen.queryByText("“quoted line 9”")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("Show all 9"));
    expect(screen.getByText("“quoted line 9”")).toBeInTheDocument();
  });

  it("says so when there is nothing to fix", () => {
    render(<ScriptRatingCard rating={rating(0)} />);
    expect(screen.getByText("No concrete problems found")).toBeInTheDocument();
  });
});
