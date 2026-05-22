import { SHORTCUT_GROUPS } from "./keyboardShortcuts";

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
                {group.shortcuts.map((shortcut) => (
                  <div key={shortcut.key} className="flex items-center justify-between py-1">
                    <span className="text-sm text-neutral-300">{shortcut.label}</span>
                    <kbd className="text-xs px-2 py-0.5 bg-neutral-800 border border-neutral-700 rounded text-neutral-400 font-mono">
                      {shortcut.shortcutDisplay}
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
