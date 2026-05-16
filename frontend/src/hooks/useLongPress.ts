import { useCallback, useRef } from "react";

interface Options {
  onClick: () => void;
  onLongPress: () => void;
  threshold?: number;
}

export default function useLongPress({ onClick, onLongPress, threshold = 350 }: Options) {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const didLongPressRef = useRef(false);

  const clear = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return;
    didLongPressRef.current = false;
    timerRef.current = setTimeout(() => {
      didLongPressRef.current = true;
      onLongPress();
    }, threshold);
  }, [onLongPress, threshold]);

  const onMouseUp = useCallback(() => {
    clear();
    if (!didLongPressRef.current) onClick();
  }, [clear, onClick]);

  const onMouseLeave = useCallback(() => {
    clear();
  }, [clear]);

  const onTouchStart = useCallback(() => {
    didLongPressRef.current = false;
    timerRef.current = setTimeout(() => {
      didLongPressRef.current = true;
      onLongPress();
    }, threshold);
  }, [onLongPress, threshold]);

  const onTouchEnd = useCallback((e: React.TouchEvent) => {
    clear();
    if (didLongPressRef.current) {
      e.preventDefault();
    } else {
      onClick();
    }
  }, [clear, onClick]);

  return { onMouseDown, onMouseUp, onMouseLeave, onTouchStart, onTouchEnd };
}
