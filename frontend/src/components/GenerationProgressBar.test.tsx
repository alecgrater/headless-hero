import { render, screen, act, cleanup } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import GenerationProgressBar from "./GenerationProgressBar";

/** Advance both the fake clock and React's timers together. */
function advance(seconds: number) {
  act(() => {
    vi.advanceTimersByTime(seconds * 1000);
  });
}

describe("GenerationProgressBar", () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: false });
    vi.setSystemTime(new Date("2026-01-01T00:00:00Z"));
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  function bar(props: Partial<Parameters<typeof GenerationProgressBar>[0]> = {}) {
    return render(
      createElement(GenerationProgressBar, {
        estimatedSeconds: 100,
        active: true,
        ...props,
      }),
    );
  }

  it("counts down while the estimate holds", () => {
    bar();
    advance(40);
    expect(screen.getByText(/~1m remaining/)).toBeTruthy();
  });

  it("says so past the estimate instead of going quiet at 95%", () => {
    // The failure this replaces: a local run sat at 95% for an hour with no
    // text, which is indistinguishable from a hang.
    bar();
    advance(150);
    expect(screen.getByText(/Taking longer than expected/)).toBeTruthy();
    expect(screen.getByText(/still running/)).toBeTruthy();
  });

  it("marks a baseline estimate as not measured on this machine", () => {
    bar({ estimateSource: "baseline" });
    advance(10);
    expect(screen.getByText(/not measured on this machine yet/)).toBeTruthy();
  });

  it("does not add that qualifier to a measured estimate", () => {
    bar({ estimateSource: "measured" });
    advance(10);
    expect(screen.queryByText(/not measured on this machine yet/)).toBeNull();
  });

  it("fills linearly rather than on a curve that reads as stalled", () => {
    // Half the estimate elapsed must look like half done. The quadratic ease-in
    // this replaces showed 25% at the midpoint of a ninety-minute wait.
    const { container } = bar();
    advance(50);
    const fill = container.querySelector("div[style]") as HTMLElement;
    expect(parseFloat(fill.style.width)).toBeGreaterThan(45);
    expect(parseFloat(fill.style.width)).toBeLessThan(55);
  });

  it("flashes to 100% when the run ends, then disappears", () => {
    const { rerender, container } = bar();
    advance(20);

    rerender(createElement(GenerationProgressBar, { estimatedSeconds: 100, active: false }));
    const fill = container.querySelector("div[style]") as HTMLElement;
    expect(fill.style.width).toBe("100%");

    advance(1);
    expect(container.querySelector("div")).toBeNull();
  });

  it("renders an indeterminate bar with no estimate and never ticks", () => {
    const { container } = bar({ estimatedSeconds: null });
    advance(600);
    expect(container.querySelector(".animate-pulse")).toBeTruthy();
    expect(screen.queryByText(/remaining/)).toBeNull();
  });
});
