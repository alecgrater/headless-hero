import { useEffect, useRef } from "react";

export function useDebouncedAutosave(
  enabled: boolean,
  save: () => void | Promise<void>,
  dependencies: unknown[],
  delayMs = 600,
) {
  const saveRef = useRef(save);
  const lastAttemptKeyRef = useRef("");

  useEffect(() => {
    saveRef.current = save;
  }, [save]);

  useEffect(() => {
    if (!enabled) return;
    const attemptKey = JSON.stringify(dependencies);
    if (attemptKey === lastAttemptKeyRef.current) return;
    const timeoutId = window.setTimeout(() => {
      lastAttemptKeyRef.current = attemptKey;
      void saveRef.current();
    }, delayMs);
    return () => window.clearTimeout(timeoutId);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- caller controls the watched values explicitly.
  }, [enabled, delayMs, ...dependencies]);
}
