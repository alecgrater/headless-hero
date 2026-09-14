import { describe, expect, it, vi } from "vitest";

import { YOLO_STAGES } from "./timelineProduction";
import { YoloRunController, runElapsedSeconds, stageElapsedSeconds, unresolvedStages } from "./yoloRun";

function makeController(overrides: Partial<ConstructorParameters<typeof YoloRunController>[0]> = {}) {
  let clock = 1_000_000;
  const snapshots: ReturnType<YoloRunController["finish"]>[] = [];
  const persisted: { status: string; log: string | null }[] = [];
  const controller = new YoloRunController({
    scriptId: "script-1",
    runId: "run-1",
    onChange: (run) => snapshots.push(run),
    persist: (run, log) => persisted.push({ status: run.status, log: log?.message ?? null }),
    isCancelled: () => false,
    now: () => (clock += 1000),
    // Resolve backoffs instantly; the timing of the wait isn't under test.
    sleep: async () => {},
    backoffMs: [10, 10, 10],
    ...overrides,
  });
  return { controller, snapshots, persisted };
}

describe("YoloRunController", () => {
  it("seeds every pipeline stage as pending so the plan is visible up front", () => {
    const { controller } = makeController();
    expect(controller.snapshot.stages.map((stage) => stage.key)).toEqual(YOLO_STAGES.map((stage) => stage.key));
    expect(controller.snapshot.stages.every((stage) => stage.status === "pending")).toBe(true);
    expect(controller.snapshot.status).toBe("running");
  });

  it("marks a stage done and records its duration", async () => {
    const { controller } = makeController();
    const outcome = await controller.stage("fx", { run: async () => {} });

    expect(outcome).toBe("done");
    const stage = controller.snapshot.stages.find((item) => item.key === "fx")!;
    expect(stage.status).toBe("done");
    expect(stage.attempts).toBe(1);
    expect(stageElapsedSeconds(stage, 0)).toBeGreaterThan(0);
  });

  it("skips a stage whose work is already complete", async () => {
    const { controller } = makeController();
    const run = vi.fn(async () => {});
    const outcome = await controller.stage("audio", { skip: () => true, run });

    expect(outcome).toBe("skipped");
    expect(run).not.toHaveBeenCalled();
    expect(controller.snapshot.stages.find((item) => item.key === "audio")!.status).toBe("skipped");
  });

  it("retries a throwing stage and succeeds on a later attempt", async () => {
    const { controller } = makeController();
    const run = vi.fn(async (attempt: number) => {
      if (attempt < 3) throw new Error("gemini hiccup");
    });

    const outcome = await controller.stage("images", { run });

    expect(outcome).toBe("done");
    expect(run).toHaveBeenCalledTimes(3);
    const stage = controller.snapshot.stages.find((item) => item.key === "images")!;
    expect(stage.attempts).toBe(3);
    expect(stage.error).toBeNull();
  });

  it("retries when verify reports the stage incomplete even though run resolved", async () => {
    const { controller } = makeController();
    let generated = 0;
    const run = vi.fn(async () => {
      generated += 1;
    });

    const outcome = await controller.stage("images", { run, verify: async () => generated >= 2 });

    expect(outcome).toBe("done");
    expect(run).toHaveBeenCalledTimes(2);
  });

  it("keeps going after a skippable stage exhausts its retries", async () => {
    const { controller } = makeController();
    const outcome = await controller.stage("images", {
      run: async () => {
        throw new Error("provider down");
      },
    });

    expect(outcome).toBe("failed");
    expect(controller.halted).toBe(false);
    expect(controller.stopped).toBe(false);
    const stage = controller.snapshot.stages.find((item) => item.key === "images")!;
    expect(stage.status).toBe("failed");
    expect(stage.error).toBe("provider down");
  });

  it("halts the run when a required stage exhausts its retries", async () => {
    const { controller } = makeController();
    const outcome = await controller.stage("audio", {
      run: async () => {
        throw new Error("elevenlabs 500");
      },
    });

    expect(outcome).toBe("failed");
    expect(controller.halted).toBe(true);
    expect(controller.stopped).toBe(true);
  });

  it("does not start a stage once the run is halted", async () => {
    const { controller } = makeController();
    await controller.stage("audio", {
      run: async () => {
        throw new Error("elevenlabs 500");
      },
    });

    const run = vi.fn(async () => {});
    const outcome = await controller.stage("images", { run });

    expect(outcome).toBe("cancelled");
    expect(run).not.toHaveBeenCalled();
  });

  it("stops mid-retry when the user presses Stop", async () => {
    let cancelled = false;
    const { controller } = makeController({ isCancelled: () => cancelled });
    const run = vi.fn(async () => {
      cancelled = true;
      throw new Error("interrupted");
    });

    const outcome = await controller.stage("images", { run });

    expect(outcome).toBe("cancelled");
    expect(run).toHaveBeenCalledTimes(1);
    expect(controller.snapshot.stages.find((item) => item.key === "images")!.status).toBe("cancelled");
  });

  it("abandons a backoff wait as soon as Stop is pressed", async () => {
    let cancelled = false;
    const sleep = vi.fn(async () => {
      cancelled = true;
    });
    const { controller } = makeController({
      isCancelled: () => cancelled,
      sleep,
      backoffMs: [60_000],
    });

    const outcome = await controller.stage("images", {
      run: async () => {
        throw new Error("provider down");
      },
    });

    expect(outcome).toBe("cancelled");
    // One 500ms slice, then the cancel check short-circuits the remaining wait.
    expect(sleep).toHaveBeenCalledTimes(1);
  });

  it("treats a verify that throws as a failed attempt", async () => {
    const { controller } = makeController();
    const outcome = await controller.stage("fx", {
      run: async () => {},
      verify: async () => {
        throw new Error("refresh failed");
      },
    });

    expect(outcome).toBe("failed");
    expect(controller.snapshot.stages.find((item) => item.key === "fx")!.error).toBe("refresh failed");
  });

  it("derives a completed status when every stage succeeded", async () => {
    const { controller } = makeController();
    await controller.stage("fx", { run: async () => {} });
    const run = controller.finish();

    expect(run.status).toBe("completed");
    expect(run.ended_at).not.toBeNull();
    expect(runElapsedSeconds(run, 0)).toBeGreaterThan(0);
  });

  it("derives completed_with_failures and lists the unresolved stages", async () => {
    const { controller } = makeController();
    await controller.stage("images", {
      run: async () => {
        throw new Error("provider down");
      },
    });
    const run = controller.finish();

    expect(run.status).toBe("completed_with_failures");
    expect(unresolvedStages(run).map((stage) => stage.key)).toEqual(["images"]);
  });

  it("derives halted when a required stage failed", async () => {
    const { controller } = makeController();
    await controller.stage("audio", {
      run: async () => {
        throw new Error("elevenlabs 500");
      },
    });

    expect(controller.finish().status).toBe("halted");
  });

  it("derives cancelled when the user stopped the run", async () => {
    let cancelled = false;
    const { controller } = makeController({ isCancelled: () => cancelled });
    cancelled = true;

    expect(controller.finish().status).toBe("cancelled");
  });

  it("persists a durable snapshot on each transition", async () => {
    const { controller, persisted } = makeController();
    await controller.stage("fx", { run: async () => {} });
    controller.finish();

    expect(persisted.length).toBeGreaterThan(2);
    expect(persisted.at(-1)!.status).toBe("completed");
    expect(persisted.some((entry) => entry.log?.includes("Generate FX: started"))).toBe(true);
    expect(persisted.some((entry) => entry.log?.includes("Generate FX: completed"))).toBe(true);
  });

  it("hands onChange a fresh object each time so React re-renders", async () => {
    const { controller, snapshots } = makeController();
    await controller.stage("fx", { run: async () => {} });

    expect(snapshots.length).toBeGreaterThan(1);
    expect(new Set(snapshots).size).toBe(snapshots.length);
  });
});

describe("stageElapsedSeconds", () => {
  it("counts an in-flight stage up to now", () => {
    const stage = {
      key: "images",
      label: "Generate Images",
      status: "running" as const,
      started_at: new Date(1_000_000).toISOString(),
      ended_at: null,
      attempts: 1,
      error: null,
      detail: null,
    };
    expect(stageElapsedSeconds(stage, 1_030_000)).toBe(30);
  });

  it("returns null for a stage that never started", () => {
    const stage = {
      key: "images",
      label: "Generate Images",
      status: "pending" as const,
      started_at: null,
      ended_at: null,
      attempts: 0,
      error: null,
      detail: null,
    };
    expect(stageElapsedSeconds(stage, 1_030_000)).toBeNull();
  });
});
