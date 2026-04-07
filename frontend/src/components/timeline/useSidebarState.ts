import { useCallback, useState } from "react";

interface SidebarState {
  leftCollapsed: boolean;
  rightCollapsed: boolean;
  toggleLeft: () => void;
  toggleRight: () => void;
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

  const [leftCollapsed, setLeftCollapsed] = useState(() => loadBool(leftKey, false));
  const [rightCollapsed, setRightCollapsed] = useState(() => loadBool(rightKey, false));

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

  return {
    leftCollapsed,
    rightCollapsed,
    toggleLeft,
    toggleRight,
  };
}
