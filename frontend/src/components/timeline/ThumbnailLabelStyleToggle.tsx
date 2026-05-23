import type { ThumbnailLabelStyle } from "../../types/render";

interface Props {
  value: ThumbnailLabelStyle;
  onChange: (value: ThumbnailLabelStyle) => void;
  disabled?: boolean;
}

const OPTIONS: { value: ThumbnailLabelStyle; label: string }[] = [
  { value: "time_periods", label: "Time Periods" },
  { value: "levels", label: "Levels" },
];

export default function ThumbnailLabelStyleToggle({ value, onChange, disabled }: Props) {
  return (
    <div className="inline-flex rounded-lg border border-neutral-800 bg-neutral-900 p-0.5">
      {OPTIONS.map((opt) => {
        const isActive = value === opt.value;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            disabled={disabled}
            className={`px-3 py-1 text-xs font-medium rounded-md transition-colors disabled:opacity-40 disabled:cursor-not-allowed ${
              isActive
                ? "bg-violet-600 text-white"
                : "text-neutral-400 hover:text-neutral-100"
            }`}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
