import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SmokeTestLab from "./SmokeTestLab";

const runTestLabSmokeTest = vi.fn();

vi.mock("../../api", () => ({
  runTestLabSmokeTest: (...args: unknown[]) => runTestLabSmokeTest(...args),
}));

const report = {
  id: "smoke-1",
  started_at: "2026-06-20T12:00:00+00:00",
  completed_at: "2026-06-20T12:01:00+00:00",
  options: { render_heavy: true, external_api: false },
  summary: { pass: 1, warn: 1, fail: 1 },
  checks: [
    {
      id: "visual-mode-vocabulary",
      label: "Visual mode vocabulary",
      group: "Contracts",
      status: "pass",
      detail: "All expected visual modes are present.",
      evidence: "full_frame, captions",
      next_action: "",
      run_id: "",
      render_url: "",
    },
    {
      id: "blink-production-guardrail",
      label: "Blink production guardrail",
      group: "Visual Modes",
      status: "warn",
      detail: "Policy text still presents blink as a planning opportunity.",
      evidence: "Production actions: none",
      next_action: "Align visual opportunity guidance.",
      run_id: "",
      render_url: "",
    },
    {
      id: "render-probe-stat-card",
      label: "stat_card render probe",
      group: "Pipeline",
      status: "fail",
      detail: "The stat_card Test Lab probe failed.",
      evidence: "Remotion exited 1",
      next_action: "Open Test Lab run smoke-stat-card.",
      run_id: "smoke-stat-card",
      render_url: "",
    },
  ],
};

describe("SmokeTestLab", () => {
  beforeEach(() => {
    runTestLabSmokeTest.mockReset();
    runTestLabSmokeTest.mockResolvedValue(report);
  });

  it("runs the smoke test with render-heavy probes enabled and external APIs disabled by default", async () => {
    render(<SmokeTestLab />);

    fireEvent.click(screen.getByRole("button", { name: /run smoke test/i }));

    await waitFor(() => {
      expect(runTestLabSmokeTest).toHaveBeenCalledWith({
        render_heavy: true,
        external_api: false,
      });
    });
    expect(await screen.findByText("1 failed")).toBeInTheDocument();
    expect(screen.getByText("Blink production guardrail")).toBeInTheDocument();
    expect(screen.getByText("Align visual opportunity guidance.")).toBeInTheDocument();
    expect(screen.getByText("smoke-stat-card")).toBeInTheDocument();
  });

  it("can opt into external API probes", async () => {
    render(<SmokeTestLab />);

    fireEvent.click(screen.getByLabelText("External API asset generation"));
    fireEvent.click(screen.getByRole("button", { name: /run smoke test/i }));

    await waitFor(() => {
      expect(runTestLabSmokeTest).toHaveBeenCalledWith({
        render_heavy: true,
        external_api: true,
      });
    });
  });
});
