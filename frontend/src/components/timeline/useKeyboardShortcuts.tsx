import { useCallback, useEffect, useState } from "react";
import type { ShortcutActions } from "./keyboardShortcuts";

export function useKeyboardShortcuts(actions: ShortcutActions) {
  const [showHelp, setShowHelp] = useState(false);

  const handler = useCallback(
    (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const isInput = target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.tagName === "SELECT" || target.isContentEditable;

      // Help overlay: ? key or Cmd+/
      if (e.key === "?" && !isInput) {
        e.preventDefault();
        setShowHelp((prev) => !prev);
        return;
      }
      if ((e.metaKey || e.ctrlKey) && e.key === "/") {
        e.preventDefault();
        setShowHelp((prev) => !prev);
        return;
      }

      // Escape closes help OR deselects micro-timeline
      if (e.key === "Escape") {
        if (showHelp) {
          setShowHelp(false);
          return;
        }
        e.preventDefault();
        actions.deselectMicroTimeline();
        return;
      }

      // Skip shortcuts when typing in inputs
      if (isInput) return;

      // Arrow keys for scene navigation
      if (e.key === "ArrowUp") {
        e.preventDefault();
        actions.selectPrevScene();
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        actions.selectNextScene();
        return;
      }

      // Space for audio play/pause
      if (e.key === " ") {
        e.preventDefault();
        actions.toggleAudioPreview();
        return;
      }

      // S for split at playhead (non-Cmd)
      if (e.key === "s" && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        actions.splitAtPlayhead();
        return;
      }

      // M for place marker
      if (e.key === "m" || e.key === "M") {
        e.preventDefault();
        actions.placeMarker();
        return;
      }

      // [ and ] for nudge (Shift+[ produces "{", Shift+] produces "}")
      if (e.key === "[" || e.key === "{") {
        e.preventDefault();
        actions.nudgeBack(e.shiftKey || e.key === "{");
        return;
      }
      if (e.key === "]" || e.key === "}") {
        e.preventDefault();
        actions.nudgeForward(e.shiftKey || e.key === "}");
        return;
      }

      // 1-4 for lane selection
      if (e.key >= "1" && e.key <= "4") {
        e.preventDefault();
        actions.selectLane(parseInt(e.key));
        return;
      }

      // Delete/Backspace — delegates to deleteMarker which falls through to deleteScene if no marker
      if (e.key === "Delete" || e.key === "Backspace") {
        e.preventDefault();
        actions.deleteMarker();
        return;
      }

      // Cmd/Ctrl combos
      if (e.metaKey || e.ctrlKey) {
        if (e.key === "g" && e.shiftKey) {
          e.preventDefault();
          actions.generateAllImages();
          return;
        }
        if (e.key === "g") {
          e.preventDefault();
          actions.generateImage();
          return;
        }
        if (e.key === "e") {
          e.preventDefault();
          actions.openUpload();
          return;
        }
        // Note: Cmd+Z and Cmd+S already handled in useTimelineState
      }
    },
    [actions, showHelp],
  );

  useEffect(() => {
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [handler]);

  return { showHelp, setShowHelp };
}
