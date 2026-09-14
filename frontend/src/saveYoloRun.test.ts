import { beforeEach, describe, expect, it, vi } from "vitest";

import type { YoloRunRecord } from "./types/yolo";

type Requested = { method: string; path: string; body?: unknown };

const flush = () => new Promise((resolve) => setTimeout(resolve, 0));

function makeRun(status: YoloRunRecord["status"], scriptId = "script-1"): YoloRunRecord {
  return {
    run_id: "run-1",
    script_id: scriptId,
    started_at: "2026-09-14T00:00:00.000Z",
    ended_at: status === "running" ? null : "2026-09-14T00:10:00.000Z",
    status,
    stages: [],
  };
}

/**
 * Load a fresh `api` module bound to a stubbed Electron bridge.
 *
 * `api.ts` captures `window.api` at import time, so the bridge has to be in
 * place before the dynamic import — and the module registry has to be reset so
 * each test gets its own write queue.
 */
async function loadApiWith(request: (entry: Requested) => Promise<unknown>) {
  vi.resetModules();
  const calls: Requested[] = [];
  const stub = (method: string, path: string, body?: unknown) => {
    const entry = { method, path, body };
    calls.push(entry);
    return request(entry);
  };
  (window as unknown as { api: unknown }).api = {
    request: stub,
    get: (path: string) => stub("GET", path),
    post: (path: string, body?: unknown) => stub("POST", path, body),
    put: (path: string, body?: unknown) => stub("PUT", path, body),
    delete: (path: string) => stub("DELETE", path),
  };
  const mod = await import("./api");
  return { saveYoloRun: mod.saveYoloRun, calls };
}

describe("saveYoloRun", () => {
  beforeEach(() => {
    delete (window as unknown as { api?: unknown }).api;
  });

  it("serializes writes per project so a slow earlier PUT cannot land last", async () => {
    // The controller fires snapshots without awaiting. If the "running"
    // snapshot won the race, the stored run would stay in-progress forever and
    // the summary bar — the whole point of the log — would never show it.
    const resolvers: (() => void)[] = [];
    const { saveYoloRun, calls } = await loadApiWith(
      () =>
        new Promise((resolve) => {
          resolvers.push(() => resolve({ ok: true, status: 200, data: {} }));
        }),
    );

    const first = saveYoloRun("script-1", makeRun("running"), null);
    const second = saveYoloRun("script-1", makeRun("completed"), null);
    await flush();

    const statuses = () => calls.map((call) => (call.body as { run: YoloRunRecord }).run.status);
    // The second write must not be issued while the first is in flight.
    expect(statuses()).toEqual(["running"]);

    resolvers[0]();
    await first;
    await flush();
    expect(statuses()).toEqual(["running", "completed"]);

    resolvers[1]();
    await second;
    expect(statuses()).toEqual(["running", "completed"]);
  });

  it("keeps the chain alive when a write fails", async () => {
    let attempt = 0;
    const { saveYoloRun, calls } = await loadApiWith(() => {
      attempt += 1;
      if (attempt === 1) return Promise.reject(new Error("backend down"));
      return Promise.resolve({ ok: true, status: 200, data: {} });
    });

    await expect(saveYoloRun("script-1", makeRun("running"), null)).resolves.toBeUndefined();
    await expect(saveYoloRun("script-1", makeRun("completed"), null)).resolves.toBeUndefined();

    expect(calls).toHaveLength(2);
  });

  it("does not serialize across different projects", async () => {
    const resolvers: (() => void)[] = [];
    const { saveYoloRun, calls } = await loadApiWith(
      () =>
        new Promise((resolve) => {
          resolvers.push(() => resolve({ ok: true, status: 200, data: {} }));
        }),
    );

    const a = saveYoloRun("script-a", makeRun("running", "script-a"), null);
    const b = saveYoloRun("script-b", makeRun("running", "script-b"), null);
    await flush();

    expect(calls.map((call) => call.path)).toEqual([
      "/api/yolo/runs/script-a",
      "/api/yolo/runs/script-b",
    ]);

    resolvers.forEach((resolve) => resolve());
    await Promise.all([a, b]);
  });
});
