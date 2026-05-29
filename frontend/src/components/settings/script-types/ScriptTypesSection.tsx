import { useEffect, useState } from "react";
import { getFormats } from "../../../api";
import type { VideoFormat } from "../../../types/format";
import { allVisualModes, modeChipsForFormat, type ModeChip } from "./modes";

interface MatrixRow {
  label: string;
  render: (f: VideoFormat) => string;
}

const ROWS: MatrixRow[] = [
  { label: "Summary", render: (f) => f.short_description },
  {
    label: "Structure",
    render: (f) =>
      f.level_count_min === f.level_count_max
        ? `${f.level_count_min} ${f.level_label}s`
        : `${f.level_count_min}–${f.level_count_max} ${f.level_label}s`,
  },
  {
    label: "Title cards",
    render: (f) => (f.title_card_strategy_kind === "composite-grid" ? "Composite grid" : "Cinematic chapters"),
  },
  { label: "Cold open", render: (f) => (f.supports_cold_open ? "Yes" : "No") },
  { label: "Hook scoring", render: (f) => (f.supports_hook_scoring ? "Yes" : "No") },
  { label: "Segmented generation", render: (f) => (f.supports_segmented_generation ? "Yes" : "No") },
  {
    label: "Visual rhythm",
    render: (f) => `${f.allowed_visual_beats.join(", ")} · max ${f.max_consecutive_same_beat} in a row`,
  },
  {
    label: "Visual modes",
    render: (f) => `${f.supported_visual_modes.length} supported`,
  },
];

function Chip({ chip, disabled, formatId }: { chip: ModeChip; disabled?: boolean; formatId: string }) {
  return (
    <span
      data-testid={disabled ? `disabled-mode-${formatId}-${chip.id}` : `mode-${formatId}-${chip.id}`}
      className={`inline-block rounded-md px-2 py-0.5 text-[11px] font-medium transition-colors ${
        disabled
          ? "bg-neutral-900 text-neutral-600 line-through"
          : "bg-neutral-800 text-neutral-200"
      }`}
      title={chip.hasDetail ? "See the Visual Modes reference for details" : undefined}
    >
      {chip.label}
    </span>
  );
}

export default function ScriptTypesSection() {
  const [formats, setFormats] = useState<VideoFormat[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getFormats()
      .then(setFormats)
      .catch(() => setError("Could not load script formats."));
  }, []);

  if (error) return <div className="px-6 py-5 text-sm text-rose-400">{error}</div>;
  if (!formats) return <div className="px-6 py-5 text-sm text-neutral-500">Loading…</div>;

  const universe = allVisualModes(formats);

  return (
    <div className="px-6 py-5 space-y-6">
      <div>
        <h2 className="text-base font-semibold text-neutral-100">Script Types</h2>
        <p className="text-[11px] text-neutral-500">
          Read-only reference — how each script format differs in structure, narration, and visual-mode
          compatibility. Mode chips link conceptually to the Visual Modes reference page.
        </p>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr>
              <th className="w-44 border-b border-neutral-800 px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                Dimension
              </th>
              {formats.map((f) => (
                <th key={f.id} className="border-b border-neutral-800 px-3 py-2 text-left font-semibold text-neutral-100">
                  {f.display_name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => (
              <tr key={row.label}>
                <td className="border-b border-neutral-900 px-3 py-2 align-top text-[11px] font-medium uppercase tracking-wide text-neutral-500">
                  {row.label}
                </td>
                {formats.map((f) => (
                  <td key={f.id} className="border-b border-neutral-900 px-3 py-2 align-top text-neutral-300">
                    {row.render(f)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {formats.map((f) => {
          const { supported, disabled } = modeChipsForFormat(f, universe);
          return (
            <div key={f.id} className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-4 space-y-3">
              <div className="space-y-1.5">
                <div className="text-[10px] font-semibold uppercase tracking-wider text-neutral-500">Supported modes</div>
                <div className="flex flex-wrap gap-1.5">
                  {supported.map((c) => (
                    <Chip key={c.id} chip={c} formatId={f.id} />
                  ))}
                </div>
                {disabled.length > 0 && (
                  <>
                    <div className="pt-1 text-[10px] font-semibold uppercase tracking-wider text-neutral-600">Disabled here</div>
                    <div className="flex flex-wrap gap-1.5">
                      {disabled.map((c) => (
                        <Chip key={c.id} chip={c} disabled formatId={f.id} />
                      ))}
                    </div>
                  </>
                )}
              </div>

              <div className="space-y-2">
                {f.reference_notes.map((note, i) => (
                  <div key={i} className="text-xs">
                    <span className="font-semibold text-neutral-400">{note.category}: </span>
                    <span className="text-neutral-400">{note.text}</span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
