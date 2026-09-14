import type {
  YoloRunLogLine,
  YoloRunRecord,
  YoloRunStatus,
  YoloStageRecord,
  YoloStageStatus,
} from "../../types/yolo";
import { YOLO_STAGES, type YoloStageKey } from "./timelineProduction";

export type { YoloRunLogLine, YoloRunRecord, YoloRunStatus, YoloStageRecord, YoloStageStatus };
export type YoloStageOutcome = "done" | "skipped" | "failed" | "cancelled";

/** Attempts per stage, including the first. */
export const YOLO_STAGE_ATTEMPTS = 3;
/**
 * Backoff before attempt 2, 3, ... — a transient provider blip clears fast, a
 * rate limit does not. The last entry is reused if `attempts` is ever raised
 * beyond this array's length.
 */
export const YOLO_RETRY_BACKOFF_MS = [5_000, 20_000];
/** Cancellation is checked this often while backing off, so Stop stays responsive. */
const CANCEL_CHECK_MS = 500;

export interface YoloStageSpec {
  /** Skip the stage entirely — it is already complete. Evaluated once, before the first attempt. */
  skip?: () => boolean | Promise<boolean>;
  /** The work. Called once per attempt; retries should generate only what is missing. */
  run: (attempt: number) => Promise<void>;
  /**
   * Re-check completion after `run` resolves. Returning false triggers a retry
   * — batch generation reports per-item failures rather than throwing, so a
   * resolved promise is not evidence the stage finished.
   */
  verify?: () => Promise<boolean>;
}

export interface YoloRunControllerOptions {
  scriptId: string;
  /** Called with an immutable snapshot on every state transition. */
  onChange: (run: YoloRunRecord) => void;
  /** Durable write of the snapshot. Must not throw; failures are the caller's to swallow. */
  persist?: (run: YoloRunRecord, log: YoloRunLogLine | null) => void;
  isCancelled: () => boolean;
  runId?: string;
  now?: () => number;
  sleep?: (ms: number) => Promise<void>;
  attempts?: number;
  backoffMs?: number[];
}

function newRunId(): string {
  const globalCrypto = typeof crypto !== "undefined" ? crypto : undefined;
  if (globalCrypto?.randomUUID) return globalCrypto.randomUUID();
  return `run-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function errorMessage(err: unknown): string {
  if (err instanceof Error && err.message) return err.message;
  if (typeof err === "string" && err) return err;
  return "Unknown error";
}

function defaultSleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Runs the YOLO pipeline's stages with retries and a durable per-stage record.
 *
 * Before this existed, every stage ended in a hard `throw` when its completion
 * check came up short, and a single try/catch around all twelve stages turned
 * one flaky image into an abandoned run. Clicking YOLO again was the retry.
 * Here a stage retries itself with backoff, and only a `required` stage can
 * stop the run — the rest record the failure and let the pipeline carry on.
 */
export class YoloRunController {
  private run: YoloRunRecord;
  private readonly options: YoloRunControllerOptions;
  private readonly attempts: number;
  private readonly backoffMs: number[];
  private haltedFlag = false;

  constructor(options: YoloRunControllerOptions) {
    this.options = options;
    this.attempts = Math.max(1, options.attempts ?? YOLO_STAGE_ATTEMPTS);
    this.backoffMs = options.backoffMs ?? YOLO_RETRY_BACKOFF_MS;
    this.run = {
      run_id: options.runId ?? newRunId(),
      script_id: options.scriptId,
      started_at: this.nowIso(),
      ended_at: null,
      status: "running",
      stages: YOLO_STAGES.map((stage) => ({
        key: stage.key,
        label: stage.label,
        status: "pending" as YoloStageStatus,
        started_at: null,
        ended_at: null,
        attempts: 0,
        error: null,
      })),
    };
  }

  get snapshot(): YoloRunRecord {
    return this.run;
  }

  get halted(): boolean {
    return this.haltedFlag;
  }

  /** True once the run can no longer make progress — stopped by the user or halted by a required stage. */
  get stopped(): boolean {
    return this.haltedFlag || this.options.isCancelled();
  }

  private now(): number {
    return (this.options.now ?? Date.now)();
  }

  private nowIso(): string {
    return new Date(this.now()).toISOString();
  }

  private commit(log: YoloRunLogLine | null = null) {
    const snapshot: YoloRunRecord = {
      ...this.run,
      stages: this.run.stages.map((stage) => ({ ...stage })),
    };
    this.run = snapshot;
    this.options.onChange(snapshot);
    this.options.persist?.(snapshot, log);
  }

  private patchStage(key: YoloStageKey, patch: Partial<YoloStageRecord>, log: YoloRunLogLine | null = null) {
    this.run = {
      ...this.run,
      stages: this.run.stages.map((stage) => (stage.key === key ? { ...stage, ...patch } : stage)),
    };
    this.commit(log);
  }

  private stageLabel(key: YoloStageKey): string {
    return YOLO_STAGES.find((stage) => stage.key === key)?.label ?? key;
  }

  private isRequired(key: YoloStageKey): boolean {
    return YOLO_STAGES.find((stage) => stage.key === key)?.required ?? false;
  }

  /** Sleep in short slices so a Stop press during a 60s backoff is honoured promptly. */
  private async backoff(ms: number): Promise<void> {
    const sleep = this.options.sleep ?? defaultSleep;
    let remaining = ms;
    while (remaining > 0) {
      if (this.options.isCancelled()) return;
      const slice = Math.min(CANCEL_CHECK_MS, remaining);
      await sleep(slice);
      remaining -= slice;
    }
  }

  async stage(key: YoloStageKey, spec: YoloStageSpec): Promise<YoloStageOutcome> {
    const label = this.stageLabel(key);

    if (this.stopped) {
      this.patchStage(key, { status: "cancelled", ended_at: this.nowIso() });
      return "cancelled";
    }

    if (spec.skip) {
      let shouldSkip = false;
      try {
        shouldSkip = await spec.skip();
      } catch {
        shouldSkip = false;
      }
      if (shouldSkip) {
        this.patchStage(key, { status: "skipped" }, { level: "info", message: `${label}: already complete, skipped` });
        return "skipped";
      }
    }

    const startedAt = this.nowIso();
    this.patchStage(
      key,
      { status: "running", started_at: startedAt, ended_at: null, attempts: 0, error: null },
      { level: "info", message: `${label}: started` },
    );

    let lastError: string | null = null;

    for (let attempt = 1; attempt <= this.attempts; attempt += 1) {
      if (this.options.isCancelled()) {
        this.patchStage(key, { status: "cancelled", ended_at: this.nowIso(), attempts: attempt - 1 });
        return "cancelled";
      }

      this.patchStage(key, { attempts: attempt });

      try {
        await spec.run(attempt);
        if (this.options.isCancelled()) {
          this.patchStage(key, { status: "cancelled", ended_at: this.nowIso() });
          return "cancelled";
        }
        const complete = spec.verify ? await spec.verify() : true;
        if (complete) {
          const endedAt = this.nowIso();
          this.patchStage(
            key,
            { status: "done", ended_at: endedAt, error: null },
            {
              level: "info",
              message: `${label}: completed in ${this.elapsedText(startedAt, endedAt)}${attempt > 1 ? ` after ${attempt} attempts` : ""}`,
            },
          );
          return "done";
        }
        lastError = `${label} did not complete for every scene`;
      } catch (err) {
        lastError = errorMessage(err);
      }

      if (this.options.isCancelled()) {
        this.patchStage(key, { status: "cancelled", ended_at: this.nowIso(), error: lastError });
        return "cancelled";
      }

      if (attempt < this.attempts) {
        const waitMs = this.backoffMs[Math.min(attempt - 1, this.backoffMs.length - 1)] ?? 0;
        this.patchStage(
          key,
          { error: lastError },
          {
            level: "warning",
            message: `${label}: attempt ${attempt} failed (${lastError}); retrying in ${Math.round(waitMs / 1000)}s`,
          },
        );
        await this.backoff(waitMs);
      }
    }

    const required = this.isRequired(key);
    if (required) this.haltedFlag = true;
    this.patchStage(
      key,
      { status: "failed", ended_at: this.nowIso(), error: lastError },
      {
        level: "error",
        message: required
          ? `${label}: failed after ${this.attempts} attempts (${lastError}) — halting the run, later stages depend on it`
          : `${label}: failed after ${this.attempts} attempts (${lastError}) — continuing without it`,
      },
    );
    return "failed";
  }

  private elapsedText(startedAt: string, endedAt: string): string {
    const seconds = Math.max(0, (Date.parse(endedAt) - Date.parse(startedAt)) / 1000);
    return `${Math.round(seconds)}s`;
  }

  /** Close the run, deriving its status from the stages unless overridden. */
  finish(status?: YoloRunStatus): YoloRunRecord {
    const derived: YoloRunStatus = status
      ?? (this.haltedFlag
        ? "halted"
        : this.options.isCancelled()
          ? "cancelled"
          : this.run.stages.some((stage) => stage.status === "failed")
            ? "completed_with_failures"
            : "completed");
    const endedAt = this.nowIso();
    this.run = {
      ...this.run,
      status: derived,
      ended_at: endedAt,
      // Any stage still open when the run ends never got to run.
      stages: this.run.stages.map((stage) =>
        stage.status === "running" ? { ...stage, status: "cancelled", ended_at: endedAt } : stage,
      ),
    };
    const failed = this.run.stages.filter((stage) => stage.status === "failed").map((stage) => stage.label);
    this.commit({
      level: derived === "completed" ? "info" : derived === "cancelled" ? "info" : "warning",
      message: `Run ${derived.replace(/_/g, " ")} in ${this.elapsedText(this.run.started_at, endedAt)}${failed.length ? ` — unresolved: ${failed.join(", ")}` : ""}`,
    });
    return this.run;
  }
}

/** Stages that ended in a state the operator should know about. */
export function unresolvedStages(run: YoloRunRecord | null): YoloStageRecord[] {
  if (!run) return [];
  return run.stages.filter((stage) => stage.status === "failed");
}

/** Seconds a stage took, counting an in-flight stage up to `nowMs`. */
export function stageElapsedSeconds(stage: YoloStageRecord, nowMs: number): number | null {
  if (!stage.started_at) return null;
  const started = Date.parse(stage.started_at);
  if (Number.isNaN(started)) return null;
  const ended = stage.ended_at ? Date.parse(stage.ended_at) : nowMs;
  if (Number.isNaN(ended)) return null;
  return Math.max(0, (ended - started) / 1000);
}

/** Seconds the whole run has taken, counting an in-flight run up to `nowMs`. */
export function runElapsedSeconds(run: YoloRunRecord | null, nowMs: number): number | null {
  if (!run) return null;
  const started = Date.parse(run.started_at);
  if (Number.isNaN(started)) return null;
  const ended = run.ended_at ? Date.parse(run.ended_at) : nowMs;
  if (Number.isNaN(ended)) return null;
  return Math.max(0, (ended - started) / 1000);
}
