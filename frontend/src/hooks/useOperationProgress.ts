import { useCallback, useRef, useState } from "react";
import { fetchGenerationEstimate, recordDuration } from "../api";
import type { EstimateSource } from "../api";

interface UseOperationProgressReturn {
  estimatedSeconds: number | null;
  /** Anything but "measured" is an approximation the UI should caption. */
  estimateSource: EstimateSource;
  active: boolean;
  start: (sceneCount?: number) => void;
  end: (sceneCount?: number) => void;
}

export function useOperationProgress(operationType: string): UseOperationProgressReturn {
  const [estimatedSeconds, setEstimatedSeconds] = useState<number | null>(null);
  const [estimateSource, setEstimateSource] = useState<EstimateSource>("measured");
  const [active, setActive] = useState(false);
  const startTime = useRef<number>(0);

  const start = useCallback(
    (sceneCount?: number) => {
      setActive(true);
      startTime.current = Date.now();
      fetchGenerationEstimate(operationType, sceneCount)
        .then((est) => {
          setEstimatedSeconds(est.average_seconds);
          setEstimateSource(est.source ?? "measured");
        })
        .catch(() => {});
    },
    [operationType],
  );

  const end = useCallback(
    (sceneCount?: number) => {
      setActive(false);
      if (startTime.current > 0) {
        const elapsed = (Date.now() - startTime.current) / 1000;
        recordDuration(operationType, elapsed, sceneCount).catch(() => {});
        startTime.current = 0;
      }
    },
    [operationType],
  );

  return { estimatedSeconds, estimateSource, active, start, end };
}
