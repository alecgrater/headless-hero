/**
 * PropertiesPopup — right-side slide-over panel wrapping PropertiesPanel.
 * Opens via the Properties button in PreviewPanel or the P keyboard shortcut.
 */
import type { ReactNode } from "react";
import { X } from "lucide-react";

interface Props {
  onClose: () => void;
  children: ReactNode;
}

export default function PropertiesPopup({ onClose, children }: Props) {
  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/40"
        onClick={onClose}
      />

      {/* Slide-over panel */}
      <div className="fixed top-0 right-0 z-50 h-full w-[500px] max-w-[90vw] bg-neutral-950 border-l border-neutral-800 shadow-2xl flex flex-col animate-slide-in-right">
        {/* Close button */}
        <div className="flex items-center justify-between px-4 py-2 border-b border-neutral-800/60 shrink-0">
          <span className="text-xs text-neutral-500 uppercase tracking-widest font-medium">
            Scene Properties
          </span>
          <button
            onClick={onClose}
            className="p-1 text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800 rounded transition-colors"
            title="Close (P)"
          >
            <X size={16} />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 min-h-0 overflow-y-auto">
          {children}
        </div>
      </div>
    </>
  );
}
