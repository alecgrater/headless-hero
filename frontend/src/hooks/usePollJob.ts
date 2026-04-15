import { useCallback, useEffect, useRef } from "react";

const MAX_POLL_FAILURES = 5;

interface PollJobConfig<T> {
  /** Function that fetches the job status. Return null if the request fails. */
  pollFn: (jobId: string) => Promise<T | null>;
  /** Return true when the job has completed successfully. */
  isComplete: (status: T) => boolean;
  /** Return true when the job has failed. */
  isFailed: (status: T) => boolean;
  /** Called on each successful poll with the latest status. */
  onStatus: (status: T) => void;
  /** Called when polling detects a lost connection (too many consecutive failures). */
  onConnectionLost: () => void;
  /** Poll interval in milliseconds. Defaults to 1000. */
  intervalMs?: number;
}

/**
 * Shared hook for polling background job status with automatic failure detection.
 *
 * Tracks consecutive poll failures and calls `onConnectionLost` after
 * MAX_POLL_FAILURES (5) consecutive failures.
 */
export function usePollJob<T>(config: PollJobConfig<T>) {
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const configRef = useRef(config);
  configRef.current = config;

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const startPolling = useCallback(
    (jobId: string) => {
      stopPolling();

      let consecutiveFailures = 0;
      const interval = configRef.current.intervalMs ?? 1000;

      pollRef.current = setInterval(async () => {
        const cfg = configRef.current;
        try {
          const status = await cfg.pollFn(jobId);
          if (status === null) {
            consecutiveFailures++;
            if (consecutiveFailures >= MAX_POLL_FAILURES) {
              stopPolling();
              cfg.onConnectionLost();
            }
            return;
          }
          consecutiveFailures = 0;
          cfg.onStatus(status);

          if (cfg.isComplete(status) || cfg.isFailed(status)) {
            stopPolling();
          }
        } catch {
          consecutiveFailures++;
          if (consecutiveFailures >= MAX_POLL_FAILURES) {
            stopPolling();
            cfg.onConnectionLost();
          }
        }
      }, interval);
    },
    [stopPolling],
  );

  return { startPolling, stopPolling };
}
