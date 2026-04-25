import { useCallback, useRef, useState } from "react";
import { fetchGenerationEstimate, recordDuration } from "../api";

interface UseOperationProgressReturn {
  estimatedSeconds: number | null;
  active: boolean;
  start: (sceneCount?: number) => void;
  end: (sceneCount?: number) => void;
}

export function useOperationProgress(operationType: string): UseOperationProgressReturn {
  const [estimatedSeconds, setEstimatedSeconds] = useState<number | null>(null);
  const [active, setActive] = useState(false);
  const startTime = useRef<number>(0);

  const start = useCallback(
    (sceneCount?: number) => {
      setActive(true);
      startTime.current = Date.now();
      fetchGenerationEstimate(operationType, sceneCount)
        .then((est) => setEstimatedSeconds(est.average_seconds))
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

  return { estimatedSeconds, active, start, end };
}
