import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import TestLabRunPanel from "./TestLabRunPanel";
import type { TestLabRun, TestLabSettings } from "../../types/testLab";

const baseRun: TestLabRun = {
  run_id: "run-1",
  script_id: "script-1",
  preset_id: "coffee-brain",
  status: "completed",
  settings: {
    visual_mode: "popup_sequence",
  },
  assets: [],
  logs: [
    {
      stage: "audio",
      status: "completed",
      message: "Completed audio",
    },
  ],
  render_url: "",
  cost_breakdown: [],
  created_at: "2026-05-25T12:47:00Z",
};

describe("TestLabRunPanel", () => {
  it("hides stage logs and labels history rows by visual mode", () => {
    render(
      <TestLabRunPanel
        activeRun={baseRun}
        runs={[
          baseRun,
          {
            ...baseRun,
            run_id: "run-2",
            settings: {
              visual_mode: "full_frame",
            },
          },
        ]}
        running={false}
        currentStep="Idle"
        onSelectRun={vi.fn()}
      />,
    );

    expect(screen.queryByText("Stage logs")).not.toBeInTheDocument();
    expect(screen.queryByText("Completed audio")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Popup sequence/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Full frame/i })).toBeInTheDocument();
    expect(screen.queryByText("coffee-brain")).not.toBeInTheDocument();
  });

  it("labels legacy history rows from stored treatment settings", () => {
    render(
      <TestLabRunPanel
        activeRun={baseRun}
        runs={[
          {
            ...baseRun,
            run_id: "run-legacy-treatment",
            settings: {
              media_source: "ai",
              visual_treatment: "blink",
            } as Partial<TestLabSettings>,
          },
          {
            ...baseRun,
            run_id: "run-legacy-video",
            settings: {
              media_source: "ai_video",
              visual_treatment: "full_frame",
            } as Partial<TestLabSettings>,
          },
        ]}
        running={false}
        currentStep="Idle"
        onSelectRun={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: /Blink/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Video/i })).toBeInTheDocument();
    expect(screen.queryByText("coffee-brain")).not.toBeInTheDocument();
  });
});
