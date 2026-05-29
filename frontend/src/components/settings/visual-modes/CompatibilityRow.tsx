import { Check, X } from "lucide-react";

interface Props {
  label: string;
  state: "supported" | "suppressed" | "yes" | "no";
  hint?: string;
}

export default function CompatibilityRow({ label, state, hint }: Props) {
  const positive = state === "supported" || state === "yes";
  const valueLabel = state === "supported"
    ? "Supported"
    : state === "suppressed"
      ? "Suppressed"
      : state === "yes"
        ? "Yes"
        : "No";

  return (
    <div className="flex items-center justify-between gap-3 px-3 py-2 rounded-lg bg-neutral-950/40 border border-neutral-800/60">
      <div className="flex flex-col">
        <span className="text-sm text-neutral-200">{label}</span>
        {hint && <span className="text-xs text-neutral-500">{hint}</span>}
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {positive ? (
          <Check className="w-4 h-4 text-emerald-400" />
        ) : (
          <X className="w-4 h-4 text-neutral-500" />
        )}
        <span className={`text-xs font-medium ${positive ? "text-emerald-400" : "text-neutral-500"}`}>
          {valueLabel}
        </span>
      </div>
    </div>
  );
}
