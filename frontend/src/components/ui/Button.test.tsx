import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Button } from "./Button";

describe("Button", () => {
  it("disables itself while loading and keeps the label visible", () => {
    render(<Button loading>Generate</Button>);

    expect(screen.getByRole("button", { name: "Generate" })).toBeDisabled();
  });
});
