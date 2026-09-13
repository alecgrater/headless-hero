import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const fetchGenerationEstimate = vi.fn();

vi.mock("../../api", () => ({
  default: { get: vi.fn().mockResolvedValue({ ok: false, data: {} }), post: vi.fn() },
  fetchGenerationEstimate: (...args: unknown[]) => fetchGenerationEstimate(...args),
  refineHook: vi.fn(),
}));

import useScriptGeneration from "./useScriptGeneration";

const idea = {
  title: "Five Accidental Inventions",
  description: "Origin stories.",
  format_id: "youtube-listicle",
  segments_est: 8,
  keywords: ["history"],
};

describe("useScriptGeneration — pre-run estimate", () => {
  it("has an estimate before a run starts, which is when the notice needs it", async () => {
    // The Local Mode notice only renders while `generationStarted` is false, so
    // an estimate fetched at kickoff would never reach it.
    fetchGenerationEstimate.mockResolvedValue({
      average_seconds: 5700,
      sample_count: 0,
      source: "baseline",
    });

    const { result } = renderHook(() =>
      useScriptGeneration({ brandId: "brand-1", idea }),
    );

    await waitFor(() => expect(result.current.estimatedSeconds).toBe(5700));
    expect(result.current.estimateSource).toBe("baseline");
    expect(result.current.generationStarted).toBe(false);
    expect(fetchGenerationEstimate).toHaveBeenCalledWith("script_generation_youtube");
  });
});
