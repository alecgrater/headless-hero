import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { YoloRunRecord, YoloStageRecord, YoloStageStatus } from "../../types/yolo";
import { YoloRunSummary } from "./YoloRunSummary";
import { effectiveEndMs, interruptedSummary } from "./yoloRun";

const T0 = "2026-09-14T00:00:00.000Z";

function stage(
  key: string,
  label: string,
  status: YoloStageStatus,
  started_at: string | null = null,
  ended_at: string | null = null,
): YoloStageRecord {
  return { key, label, status, started_at, ended_at, attempts: status === "pending" ? 0 : 1, error: null };
}

function run(overrides: Partial<YoloRunRecord> = {}): YoloRunRecord {
  return {
    run_id: "run-1",
    script_id: "script-1",
    started_at: T0,
    ended_at: null,
    status: "running",
    stages: [],
    ...overrides,
  };
}

afterEach(() => {
  vi.useRealTimers();
});

describe("effectiveEndMs", () => {
  it("uses ended_at when the run closed itself", () => {
    expect(effectiveEndMs(run({ status: "completed", ended_at: "2026-09-14T00:05:00.000Z" }))).toBe(
      Date.parse("2026-09-14T00:05:00.000Z"),
    );
  });

  it("falls through an unparseable ended_at to the newest recorded timestamp", () => {
    const record = run({
      ended_at: "not a date",
      stages: [stage("audio", "Generate Audio", "done", T0, "2026-09-14T00:02:00.000Z")],
    });
    expect(effectiveEndMs(record)).toBe(Date.parse("2026-09-14T00:02:00.000Z"));
  });

  it("measures an interrupted run to its last recorded timestamp, not to now", () => {
    // A run killed yesterday must not report the hours since as its duration.
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-15T12:00:00.000Z"));
    const record = run({
      stages: [
        stage("audio", "Generate Audio", "done", T0, "2026-09-14T00:02:00.000Z"),
        stage("images", "Generate Images", "running", "2026-09-14T00:02:00.000Z"),
      ],
    });
    expect(effectiveEndMs(record)).toBe(Date.parse("2026-09-14T00:02:00.000Z"));
  });

  it("falls back to started_at when no stage recorded anything", () => {
    expect(effectiveEndMs(run())).toBe(Date.parse(T0));
  });
});

describe("interruptedSummary", () => {
  it("names the stage the run died inside", () => {
    const record = run({
      stages: [stage("audio", "Generate Audio", "done", T0, T0), stage("images", "Generate Images", "running", T0)],
    });
    expect(interruptedSummary(record)).toBe("Stopped during: Generate Images");
  });

  it("names the last completed stage when the run died between stages", () => {
    // stage() evaluates an async skip() before marking the next stage running,
    // so no stage is "running" if the app was killed in that window.
    const record = run({
      stages: [
        stage("audio", "Generate Audio", "done", T0, T0),
        stage("images", "Generate Images", "done", T0, T0),
        stage("fx", "Generate FX", "pending"),
      ],
    });
    expect(interruptedSummary(record)).toBe("Stopped after: Generate Images");
  });

  it("says startup when nothing ever began", () => {
    expect(interruptedSummary(run({ stages: [stage("audio", "Generate Audio", "pending")] }))).toBe(
      "Stopped during startup",
    );
  });
});

describe("YoloRunSummary", () => {
  it("labels a stored running record as interrupted rather than in progress", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-09-15T12:00:00.000Z"));
    render(
      <YoloRunSummary
        run={run({
          stages: [
            stage("audio", "Generate Audio", "done", T0, "2026-09-14T00:02:00.000Z"),
            stage("images", "Generate Images", "running", "2026-09-14T00:02:00.000Z"),
          ],
        })}
        onDismiss={() => {}}
      />,
    );

    expect(screen.getByText(/Interrupted/)).toBeInTheDocument();
    expect(screen.getByText("Stopped during: Generate Images")).toBeInTheDocument();
    // 2 minutes of recorded work, not the 36 hours since it died.
    expect(screen.getByText("2:00")).toBeInTheDocument();
    expect(screen.queryByText("Every task completed.")).not.toBeInTheDocument();
  });

  it("does not invent a duration for the stage an interrupted run died inside", async () => {
    const user = userEvent.setup();
    render(
      <YoloRunSummary
        run={run({
          stages: [
            stage("audio", "Generate Audio", "done", T0, "2026-09-14T00:02:00.000Z"),
            stage("images", "Generate Images", "running", "2026-09-14T00:02:00.000Z"),
            stage("fx", "Generate FX", "pending"),
          ],
        })}
        onDismiss={() => {}}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Show timings" }));

    const rows = screen.getAllByRole("listitem");
    expect(rows[0]).toHaveTextContent("2:00");
    expect(rows[1]).toHaveTextContent("interrupted");
    expect(rows[1]).not.toHaveTextContent("0:00");
    expect(rows[2]).toHaveTextContent("not reached");
  });

  it("lists unresolved stages for a run that finished with failures", () => {
    render(
      <YoloRunSummary
        run={run({
          status: "completed_with_failures",
          ended_at: "2026-09-14T01:00:00.000Z",
          stages: [
            stage("audio", "Generate Audio", "done", T0, "2026-09-14T00:02:00.000Z"),
            stage("images", "Generate Images", "failed", "2026-09-14T00:02:00.000Z", "2026-09-14T00:09:00.000Z"),
          ],
        })}
        onDismiss={() => {}}
      />,
    );

    expect(screen.getByText("Unresolved: Generate Images")).toBeInTheDocument();
  });

  it("dismisses on request", async () => {
    const onDismiss = vi.fn();
    const user = userEvent.setup();
    render(
      <YoloRunSummary
        run={run({ status: "completed", ended_at: "2026-09-14T00:30:00.000Z" })}
        onDismiss={onDismiss}
      />,
    );

    await user.click(screen.getByTitle("Dismiss"));
    expect(onDismiss).toHaveBeenCalledOnce();
  });
});
