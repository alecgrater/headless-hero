import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import SmokeTestLab from "./SmokeTestLab";

const runTestLabSmokeTest = vi.fn();
const getTestLabSmokeTests = vi.fn();
const exportTestLabSmokeTest = vi.fn();

vi.mock("../../api", () => ({
  exportTestLabSmokeTest: (...args: unknown[]) => exportTestLabSmokeTest(...args),
  getTestLabSmokeTests: () => getTestLabSmokeTests(),
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
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
    exportTestLabSmokeTest.mockReset();
    getTestLabSmokeTests.mockReset();
    runTestLabSmokeTest.mockReset();
    exportTestLabSmokeTest.mockResolvedValue({
      report_id: "smoke-1",
      markdown: "Please fix the Headless Hero Smoke Test issues below.\n\n# Smoke Test Report `smoke-1`",
    });
    getTestLabSmokeTests.mockResolvedValue([]);
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

  it("loads previous smoke tests and re-exports the selected report", async () => {
    getTestLabSmokeTests.mockResolvedValue([report]);
    render(<SmokeTestLab />);

    expect(await screen.findByRole("button", { name: /smoke-1/i })).toBeInTheDocument();
    expect(screen.getByText("Blink production guardrail")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /copy fix brief/i }));

    await waitFor(() => {
      expect(exportTestLabSmokeTest).toHaveBeenCalledWith("smoke-1");
      expect(navigator.clipboard.writeText).toHaveBeenCalledWith(
        expect.stringContaining("Please fix the Headless Hero Smoke Test issues below."),
      );
    });
    expect(await screen.findByText("Fix brief copied")).toBeInTheDocument();
  });
});
