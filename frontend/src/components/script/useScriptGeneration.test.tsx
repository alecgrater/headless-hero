import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import useScriptGeneration from "./useScriptGeneration";
import api, { refineHook } from "../../api";
import type { ColdOpenResult, ColdOpenVariant, RefinedHookResult } from "../../types/script";

const pollConfigs: Array<{
  onStatus: (status: unknown) => void;
}> = [];

vi.mock("../../api", () => ({
  default: {
    get: vi.fn().mockResolvedValue({
      ok: true,
      data: { SCRIPT_MODEL: { masked: "gpt-5-mini" } },
    }),
    post: vi.fn(),
  },
  fetchGenerationEstimate: vi.fn().mockResolvedValue({ average_seconds: 10 }),
  recordDuration: vi.fn().mockResolvedValue({}),
  refineHook: vi.fn(),
}));

vi.mock("../../hooks/useOperationProgress", () => ({
  useOperationProgress: () => ({
    estimatedSeconds: null,
    active: false,
    start: vi.fn(),
    end: vi.fn(),
  }),
}));

vi.mock("../../hooks/usePollJob", () => ({
  usePollJob: (config: { onStatus: (status: unknown) => void }) => {
    pollConfigs.push(config);
    return {
      startPolling: vi.fn(),
      stopPolling: vi.fn(),
    };
  },
}));

const coldOpenVariant: ColdOpenVariant = {
  id: "variant-1",
  style: "direct",
  intro_hook: "You think this job is simple.",
  opening_narration: "Then the rush starts.",
  scores: {
    tension: 8,
    specificity: 8,
    drop_rate_risk: 2,
    overall: 8,
    reasoning: "Specific and tense.",
  },
};

const coldOpenResult: ColdOpenResult = {
  variants: [coldOpenVariant],
  winner_id: "variant-1",
};

const refineResult: RefinedHookResult = {
  hook_score: {
    promise: { score: 8, reasoning: "Clear." },
    tension: { score: 8, reasoning: "Strong." },
    payoff_hint: { score: 8, reasoning: "Specific." },
    overall: 8,
    suggestions: [],
  },
  refined_hook: {
    intro_hook: "You think this job is simple.",
    opening_narration: "Then the rush starts.",
  },
  original_hook: {
    intro_hook: "You think this job is simple.",
    opening_narration: "Then the rush starts.",
  },
};

describe("useScriptGeneration", () => {
  beforeEach(() => {
    pollConfigs.length = 0;
    vi.clearAllMocks();
    vi.mocked(api.post).mockResolvedValue({ ok: true, status: 200, data: { job_id: "job-1" } });
    vi.mocked(refineHook).mockResolvedValue({ job_id: "refine-job-1" });
  });

  it("preserves creator guidance after cold open refinement", async () => {
    const { result } = renderHook(() =>
      useScriptGeneration({
        brandId: "brand-1",
        supportsColdOpen: true,
        idea: {
          title: "8 Things About Fast Food",
          description: "A workplace story.",
          creator_guidance: "Every section should include realistic pay at that stage.",
          format_id: "youtube-listicle",
          segments_est: 8,
          keywords: ["work"],
        },
      }),
    );

    await act(async () => {
      await result.current.handleGenerate();
    });

    act(() => {
      pollConfigs[1].onStatus({
        status: "completed",
        error: null,
        cold_open_result: coldOpenResult,
      });
    });

    await act(async () => {
      result.current.handleColdOpenSelect(coldOpenVariant);
    });

    act(() => {
      pollConfigs[2].onStatus({
        status: "completed",
        current_step: "Complete",
        error: null,
        refine_result: refineResult,
      });
    });

    await waitFor(() => {
      expect(api.post).toHaveBeenCalledWith(
        "/api/scripts/generate",
        expect.objectContaining({
          creator_guidance: "Every section should include realistic pay at that stage.",
        }),
      );
    });
  });
});
