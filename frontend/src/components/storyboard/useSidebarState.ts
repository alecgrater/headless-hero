import { useCallback, useState } from "react";

interface SidebarState {
  leftCollapsed: boolean;
  rightCollapsed: boolean;
  rightPinned: boolean;
  toggleLeft: () => void;
  toggleRight: () => void;
  toggleRightPin: () => void;
  openRight: () => void;
  closeRight: () => void;
}

function loadBool(key: string, fallback: boolean): boolean {
  try {
    const v = localStorage.getItem(key);
    if (v === null) return fallback;
    return v === "true";
  } catch {
    return fallback;
  }
}

export function useSidebarState(scriptId: string): SidebarState {
  const leftKey = `hh-sidebar-left-${scriptId}`;
  const rightKey = `hh-sidebar-right-${scriptId}`;
  const pinKey = `hh-sidebar-pin-${scriptId}`;

  const [leftCollapsed, setLeftCollapsed] = useState(() => loadBool(leftKey, false));
  const [rightCollapsed, setRightCollapsed] = useState(() => loadBool(rightKey, false));
  const [rightPinned, setRightPinned] = useState(() => loadBool(pinKey, true));

  const toggleLeft = useCallback(() => {
    setLeftCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem(leftKey, String(next));
      return next;
    });
  }, [leftKey]);

  const toggleRight = useCallback(() => {
    setRightCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem(rightKey, String(next));
      return next;
    });
  }, [rightKey]);

  const toggleRightPin = useCallback(() => {
    setRightPinned((prev) => {
      const next = !prev;
      localStorage.setItem(pinKey, String(next));
      return next;
    });
  }, [pinKey]);

  const openRight = useCallback(() => {
    setRightCollapsed(false);
    localStorage.setItem(rightKey, "false");
  }, [rightKey]);

  const closeRight = useCallback(() => {
    setRightCollapsed(true);
    localStorage.setItem(rightKey, "true");
  }, [rightKey]);

  return {
    leftCollapsed,
    rightCollapsed,
    rightPinned,
    toggleLeft,
    toggleRight,
    toggleRightPin,
    openRight,
    closeRight,
  };
}
