import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import ThumbnailPhaseProgress, { type ThumbnailPhaseItem } from "./ThumbnailPhaseProgress";

const phases: ThumbnailPhaseItem[] = [
  { key: "title-cards", label: "Title cards", status: "done", detail: "8 of 8 chapters" },
  { key: "short-form", label: "Short-form thumbnails", status: "running", detail: "3 of 8 covers" },
  { key: "long-form", label: "Long-form thumbnail", status: "pending", detail: "Waiting for title cards" },
];

describe("ThumbnailPhaseProgress", () => {
  it("shows every thumbnail phase with status and detail while work is active", () => {
    render(<ThumbnailPhaseProgress phases={phases} />);

    expect(screen.getByText("Title cards")).toBeInTheDocument();
    expect(screen.getByText("Done")).toBeInTheDocument();
    expect(screen.getByText("8 of 8 chapters")).toBeInTheDocument();
    expect(screen.getByText("Short-form thumbnails")).toBeInTheDocument();
    expect(screen.getByText("Running")).toBeInTheDocument();
    expect(screen.getByText("3 of 8 covers")).toBeInTheDocument();
    expect(screen.getByText("Long-form thumbnail")).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument();
    expect(screen.getByText("Waiting for title cards")).toBeInTheDocument();
  });
});
