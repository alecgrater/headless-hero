import { useCallback, useEffect, useState } from "react";

export interface Toast {
  id: string;
  message: string;
  type: "error" | "success" | "info";
}

let _addToast: ((toast: Toast) => void) | null = null;

/** Show a toast notification from anywhere (outside React tree). */
// eslint-disable-next-line react-refresh/only-export-components -- co-located with the only consumer of _addToast
export function showToast(message: string, type: Toast["type"] = "error") {
  const id = Date.now().toString(36) + Math.random().toString(36).slice(2, 6);
  _addToast?.({ id, message, type });
}

export default function ToastContainer() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const addToast = useCallback((toast: Toast) => {
    setToasts((prev) => [...prev, toast]);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  // Register global add function
  useEffect(() => {
    _addToast = addToast;
    return () => {
      _addToast = null;
    };
  }, [addToast]);

  // Auto-dismiss after 6 seconds
  useEffect(() => {
    if (toasts.length === 0) return;
    const oldest = toasts[0];
    const timer = setTimeout(() => removeToast(oldest.id), 6000);
    return () => clearTimeout(timer);
  }, [toasts, removeToast]);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed bottom-4 right-4 z-[100] flex flex-col gap-2 max-w-sm">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`flex items-start gap-3 rounded-lg border px-4 py-3 text-sm shadow-lg animate-[slideIn_0.2s_ease-out] ${
            toast.type === "error"
              ? "bg-red-500/10 border-red-500/30 text-red-300"
              : toast.type === "success"
                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                : "bg-sky-500/10 border-sky-500/30 text-sky-300"
          }`}
        >
          <span className="flex-1 break-words">{toast.message}</span>
          <button
            onClick={() => removeToast(toast.id)}
            className="text-neutral-500 hover:text-neutral-300 shrink-0 leading-none text-lg"
          >
            &times;
          </button>
        </div>
      ))}
    </div>
  );
}
