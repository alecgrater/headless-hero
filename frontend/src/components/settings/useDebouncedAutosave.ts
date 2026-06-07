import { useEffect, useRef } from "react";

export function useDebouncedAutosave(
  enabled: boolean,
  save: () => boolean | void | Promise<boolean | void>,
  dependencies: unknown[],
  delayMs = 600,
) {
  const saveRef = useRef(save);
  const lastSavedKeyRef = useRef("");
  const inFlightKeyRef = useRef("");

  useEffect(() => {
    saveRef.current = save;
  }, [save]);

  useEffect(() => {
    if (!enabled) return;
    const attemptKey = JSON.stringify(dependencies);
    if (attemptKey === lastSavedKeyRef.current || attemptKey === inFlightKeyRef.current) return;
    const timeoutId = window.setTimeout(() => {
      inFlightKeyRef.current = attemptKey;
      void Promise.resolve(saveRef.current()).then((saved) => {
        if (saved !== false) {
          lastSavedKeyRef.current = attemptKey;
        }
      }).finally(() => {
        if (inFlightKeyRef.current === attemptKey) {
          inFlightKeyRef.current = "";
        }
      });
    }, delayMs);
    return () => window.clearTimeout(timeoutId);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- caller controls the watched values explicitly.
  }, [enabled, delayMs, ...dependencies]);
}
