import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import VisualModesSection from "./VisualModesSection";

describe("VisualModesSection duration workflow", () => {
  it("explains that visual modes plan duration before voiceover", () => {
    render(<VisualModesSection />);

    expect(screen.getByText(/planned before voiceover/i)).toBeInTheDocument();
    expect(screen.getByText(/duration targets are tied to visual mode/i)).toBeInTheDocument();
    expect(screen.getByText(/post-voiceover validation/i)).toBeInTheDocument();
  });
});
