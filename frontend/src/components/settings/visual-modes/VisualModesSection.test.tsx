import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import VisualModesSection from "./VisualModesSection";

describe("VisualModesSection duration workflow", () => {
  it("explains that visual modes plan duration before voiceover", () => {
    render(<VisualModesSection />);

    expect(screen.getByText(/planned before voiceover/i)).toBeInTheDocument();
    expect(screen.getByText(/outline phase first marks visual opportunities/i)).toBeInTheDocument();
    expect(screen.getByText(/captions, popup sequences, comparison boards, and stat cards/i)).toBeInTheDocument();
    expect(screen.getByText(/soft candidates instead of quotas/i)).toBeInTheDocument();
    expect(screen.getByText(/captions are normal-duration editorial punches/i)).toBeInTheDocument();
    expect(screen.getByText(/metadata-only audit/i)).toBeInTheDocument();
    expect(screen.getByText(/board and object modes get breathing room/i)).toBeInTheDocument();
    expect(screen.getByText(/post-voiceover validation/i)).toBeInTheDocument();
  });
});
