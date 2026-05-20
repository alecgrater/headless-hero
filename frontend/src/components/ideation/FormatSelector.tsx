import type { VideoFormat } from "../../types/format";

interface Props {
  formats: VideoFormat[];
  selectedId: string;
  onSelect: (id: string) => void;
}

export function FormatSelector({ formats, selectedId, onSelect }: Props) {
  return (
    <div className="grid grid-cols-2 gap-3 mb-6">
      {formats.map((fmt) => {
        const selected = fmt.id === selectedId;
        return (
          <button
            key={fmt.id}
            type="button"
            onClick={() => onSelect(fmt.id)}
            className={
              "text-left rounded-lg border p-4 transition-colors " +
              (selected
                ? "border-violet-500 bg-violet-500/10"
                : "border-neutral-800 bg-neutral-900 hover:border-neutral-700")
            }
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-sm font-semibold text-neutral-100">
                {fmt.display_name}
              </span>
              {selected && (
                <span className="text-xs text-violet-400">SELECTED</span>
              )}
            </div>
            <p className="text-xs text-neutral-400 mb-2 leading-relaxed">
              {fmt.short_description}
            </p>
            <p className="text-[11px] text-neutral-500 uppercase tracking-wide">
              {fmt.level_count_min === fmt.level_count_max
                ? `${fmt.level_count_min} ${fmt.level_label}s`
                : `${fmt.level_count_min}–${fmt.level_count_max} ${fmt.level_label}s`}
            </p>
          </button>
        );
      })}
    </div>
  );
}
