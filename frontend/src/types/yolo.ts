/**
 * YOLO pipeline run records — the durable shape shared by the browser
 * controller (`components/timeline/yoloRun.ts`) and the backend's
 * `pipeline.yolo_runs`. Timestamps are UTC ISO 8601 strings.
 */

export type YoloStageStatus = "pending" | "running" | "done" | "skipped" | "failed" | "cancelled";
export type YoloRunStatus = "running" | "completed" | "completed_with_failures" | "halted" | "cancelled";

export interface YoloStageRecord {
  key: string;
  label: string;
  status: YoloStageStatus;
  started_at: string | null;
  ended_at: string | null;
  attempts: number;
  error: string | null;
}

export interface YoloRunRecord {
  run_id: string;
  script_id: string;
  started_at: string;
  ended_at: string | null;
  status: YoloRunStatus;
  stages: YoloStageRecord[];
}

export interface YoloRunLogLine {
  level: "info" | "warning" | "error";
  message: string;
}
