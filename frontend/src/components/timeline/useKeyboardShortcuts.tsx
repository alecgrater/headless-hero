import { useCallback, useEffect, useState } from "react";

interface ShortcutActions {
  selectPrevScene: () => void;
  selectNextScene: () => void;
  undo: () => void;
  save: () => void;
  generateImage: () => void;
  generateAllImages: () => void;
  openExport: () => void;
  toggleAudioPreview: () => void;
  deleteScene: () => void;
  toggleProperties: () => void;
  // Micro-timeline actions
  splitAtPlayhead: () => void;
  placeMarker: () => void;
  nudgeBack: (large: boolean) => void;
  nudgeForward: (large: boolean) => void;
  selectLane: (lane: number) => void;
  deselectMicroTimeline: () => void;
  deleteMarker: () => void;
}

interface Shortcut {
  key: string;
  label: string;
  shortcutDisplay: string;
}

interface ShortcutGroup {
  label: string;
  shortcuts: Shortcut[];
}

export const SHORTCUT_GROUPS: ShortcutGroup[] = [
  {
    label: "Timeline Navigation",
    shortcuts: [
      { key: "ArrowUp", label: "Select previous scene", shortcutDisplay: "\u2191" },
      { key: "ArrowDown", label: "Select next scene", shortcutDisplay: "\u2193" },
      { key: "Space", label: "Play/pause audio", shortcutDisplay: "Space" },
      { key: "p", label: "Toggle properties panel", shortcutDisplay: "P" },
    ],
  },
  {
    label: "Scene Editing",
    shortcuts: [
      { key: "s", label: "Split scene at playhead", shortcutDisplay: "S" },
      { key: "Delete", label: "Delete scene or marker", shortcutDisplay: "Delete" },
      { key: "g", label: "Generate image for scene", shortcutDisplay: "\u2318G" },
      { key: "G", label: "Generate all images", shortcutDisplay: "\u2318\u21E7G" },
      { key: "z", label: "Undo", shortcutDisplay: "\u2318Z" },
      { key: "s_save", label: "Save", shortcutDisplay: "\u2318S" },
    ],
  },
  {
    label: "Micro-Timeline",
    shortcuts: [
      { key: "m", label: "Place marker at playhead", shortcutDisplay: "M" },
      { key: "[", label: "Nudge -1 frame", shortcutDisplay: "[" },
      { key: "]", label: "Nudge +1 frame", shortcutDisplay: "]" },
      { key: "shift_[", label: "Nudge -10 frames", shortcutDisplay: "\u21E7[" },
      { key: "shift_]", label: "Nudge +10 frames", shortcutDisplay: "\u21E7]" },
      { key: "1-4", label: "Select lane (Images/FX/Eli/In\u00B7Out)", shortcutDisplay: "1-4" },
      { key: "Escape", label: "Deselect marker/lane", shortcutDisplay: "Esc" },
    ],
  },
  {
    label: "Global",
    shortcuts: [
      { key: "e", label: "Open export panel", shortcutDisplay: "\u2318E" },
      { key: "?", label: "Toggle keyboard shortcuts", shortcutDisplay: "? / \u2318/" },
    ],
  },
];

// Flat list for backward compat
export const SHORTCUTS: Shortcut[] = SHORTCUT_GROUPS.flatMap((g) => g.shortcuts);

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

      // P for properties toggle
      if (e.key === "p" || e.key === "P") {
        e.preventDefault();
        actions.toggleProperties();
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

      // [ and ] for nudge
      if (e.key === "[") {
        e.preventDefault();
        actions.nudgeBack(e.shiftKey);
        return;
      }
      if (e.key === "]") {
        e.preventDefault();
        actions.nudgeForward(e.shiftKey);
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
          actions.openExport();
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

export function ShortcutHelpOverlay({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-8" onClick={onClose}>
      <div
        className="bg-neutral-900 border border-neutral-800 rounded-2xl w-full max-w-md p-6 max-h-[80vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold">Keyboard Shortcuts</h2>
          <button
            onClick={onClose}
            className="text-neutral-400 hover:text-white transition-colors text-xl leading-none"
          >
            &times;
          </button>
        </div>
        <div className="space-y-4">
          {SHORTCUT_GROUPS.map((group) => (
            <div key={group.label}>
              <h3 className="text-xs font-medium text-neutral-500 uppercase tracking-wider mb-1.5">
                {group.label}
              </h3>
              <div className="space-y-1">
                {group.shortcuts.map((s) => (
                  <div key={s.key} className="flex items-center justify-between py-1">
                    <span className="text-sm text-neutral-300">{s.label}</span>
                    <kbd className="text-xs px-2 py-0.5 bg-neutral-800 border border-neutral-700 rounded text-neutral-400 font-mono">
                      {s.shortcutDisplay}
                    </kbd>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
