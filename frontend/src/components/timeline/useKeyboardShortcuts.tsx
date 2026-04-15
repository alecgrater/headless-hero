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
}

interface Shortcut {
  key: string;
  label: string;
  shortcutDisplay: string;
}

export const SHORTCUTS: Shortcut[] = [
  { key: "ArrowUp", label: "Select previous scene", shortcutDisplay: "\u2191" },
  { key: "ArrowDown", label: "Select next scene", shortcutDisplay: "\u2193" },
  { key: "z", label: "Undo", shortcutDisplay: "\u2318Z" },
  { key: "s", label: "Save", shortcutDisplay: "\u2318S" },
  { key: "g", label: "Generate image for selected scene", shortcutDisplay: "\u2318G" },
  { key: "G", label: "Generate all images", shortcutDisplay: "\u2318\u21E7G" },
  { key: "e", label: "Open export panel", shortcutDisplay: "\u2318E" },
  { key: "Space", label: "Play/pause audio preview", shortcutDisplay: "Space" },
  { key: "p", label: "Toggle properties panel", shortcutDisplay: "P" },
  { key: "Delete", label: "Delete selected scene", shortcutDisplay: "Delete" },
];

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

      // Escape closes help
      if (e.key === "Escape" && showHelp) {
        setShowHelp(false);
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

      // Delete/Backspace for scene deletion
      if (e.key === "Delete" || e.key === "Backspace") {
        e.preventDefault();
        actions.deleteScene();
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
        className="bg-neutral-900 border border-neutral-800 rounded-2xl w-full max-w-md p-6"
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
        <div className="space-y-2">
          {SHORTCUTS.map((s) => (
            <div key={s.key} className="flex items-center justify-between py-1.5">
              <span className="text-sm text-neutral-300">{s.label}</span>
              <kbd className="text-xs px-2 py-1 bg-neutral-800 border border-neutral-700 rounded text-neutral-400 font-mono">
                {s.shortcutDisplay}
              </kbd>
            </div>
          ))}
          <div className="flex items-center justify-between py-1.5 border-t border-neutral-800 mt-2 pt-3">
            <span className="text-sm text-neutral-300">Show this help</span>
            <kbd className="text-xs px-2 py-1 bg-neutral-800 border border-neutral-700 rounded text-neutral-400 font-mono">
              ? / {"\u2318"}/
            </kbd>
          </div>
        </div>
      </div>
    </div>
  );
}
