import { useEffect, useState } from "react";
import { getFormats } from "../../../api";
import type { VideoFormat } from "../../../types/format";
import { allVisualModes, modeChipsForFormat, type ModeChip } from "./modes";

interface MatrixRow {
  label: string;
  render: (f: VideoFormat) => string;
}

const ROWS: MatrixRow[] = [
  { label: "Best for", render: (f) => f.short_description },
  {
    label: "Project shape",
    render: (f) =>
      f.level_count_min === f.level_count_max
        ? `${f.level_count_min} ${f.level_label}s`
        : `${f.level_count_min}–${f.level_count_max} ${f.level_label}s`,
  },
  {
    label: "Chapter cards",
    render: (f) => (f.title_card_strategy_kind === "composite-grid" ? "Composite grid" : "Cinematic chapters"),
  },
  { label: "Cold open", render: (f) => (f.supports_cold_open ? "Yes" : "No") },
  { label: "Hook scoring", render: (f) => (f.supports_hook_scoring ? "Yes" : "No") },
  { label: "Segmented writing", render: (f) => (f.supports_segmented_generation ? "Yes" : "No") },
  {
    label: "Visual rhythm guardrail",
    render: (f) => `${f.allowed_visual_beats.join(", ")} · max ${f.max_consecutive_same_beat} in a row`,
  },
  {
    label: "Mode coverage",
    render: (f) => `${f.supported_visual_modes.length} visual modes supported`,
  },
];

function Chip({
  chip,
  disabled,
  formatId,
  onOpen,
}: {
  chip: ModeChip;
  disabled?: boolean;
  formatId: string;
  onOpen?: () => void;
}) {
  const testId = disabled ? `disabled-mode-${formatId}-${chip.id}` : `mode-${formatId}-${chip.id}`;
  const base = `inline-block rounded-md px-2 py-0.5 text-[11px] font-medium ${
    disabled ? "bg-neutral-900 text-neutral-600 line-through" : "bg-neutral-800 text-neutral-200"
  }`;
  if (chip.hasDetail && onOpen) {
    return (
      <button
        type="button"
        data-testid={testId}
        onClick={onOpen}
        title="Open this mode on the Visual Modes reference page"
        className={`${base} cursor-pointer transition-colors hover:text-violet-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500`}
      >
        {chip.label}
      </button>
    );
  }
  return (
    <span data-testid={testId} className={base}>
      {chip.label}
    </span>
  );
}

export default function ScriptTypesSection({ onOpenVisualModes }: { onOpenVisualModes?: () => void }) {
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
    <div className="px-6 py-6 space-y-6">
      <div className="space-y-2">
        <h2 className="text-base font-semibold text-neutral-100">Script Types</h2>
        <p className="max-w-4xl text-sm leading-6 text-neutral-400">
          Script types define the story contract for a project: how many sections it has, how title
          cards behave, which narration rules matter, and how visual modes can be used. Choose the
          format that matches the viewer promise first, then let scene-by-scene routing choose the
          best visual mode for each beat.
        </p>
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
          <div className="text-sm font-semibold text-neutral-100">Format Comes First</div>
          <p className="mt-2 text-xs leading-5 text-neutral-400">
            A script format should fit the topic, pacing, and finished video promise. It is not a
            quota system for forcing certain scene visuals.
          </p>
        </div>
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
          <div className="text-sm font-semibold text-neutral-100">Shorts Must Stand Alone</div>
          <p className="mt-2 text-xs leading-5 text-neutral-400">
            Segmented formats expect each section to resolve cleanly enough that any segment can
            become its own short-form upload.
          </p>
        </div>
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
          <div className="text-sm font-semibold text-neutral-100">Modes Are Per Scene</div>
          <p className="mt-2 text-xs leading-5 text-neutral-400">
            Click any visual-mode chip to jump to the visual reference. Supported means eligible,
            not required.
          </p>
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr>
              <th scope="col" className="w-44 border-b border-neutral-800 px-3 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                Dimension
              </th>
              {formats.map((f) => (
                <th key={f.id} scope="col" className="border-b border-neutral-800 px-3 py-2 text-left font-semibold text-neutral-100">
                  {f.display_name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {ROWS.map((row) => (
              <tr key={row.label}>
                <th scope="row" className="border-b border-neutral-900 px-3 py-2 text-left align-top text-[11px] font-medium uppercase tracking-wide text-neutral-500">
                  {row.label}
                </th>
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
            <div key={f.id} className="rounded-lg border border-neutral-800 bg-neutral-900/40 p-4 space-y-4">
              <div>
                <div className="text-sm font-semibold text-neutral-100">{f.display_name}</div>
                <p className="mt-1 text-xs leading-5 text-neutral-500">{f.short_description}</p>
              </div>
              <div className="space-y-1.5">
                <div className="text-[10px] font-semibold uppercase tracking-wider text-neutral-500">Supported modes</div>
                <div className="flex flex-wrap gap-1.5">
                  {supported.map((c) => (
                    <Chip key={c.id} chip={c} formatId={f.id} onOpen={onOpenVisualModes} />
                  ))}
                </div>
                {disabled.length > 0 && (
                  <>
                    <div className="pt-1 text-[10px] font-semibold uppercase tracking-wider text-neutral-600">Disabled here</div>
                    <div className="flex flex-wrap gap-1.5">
                      {disabled.map((c) => (
                        <Chip key={c.id} chip={c} disabled formatId={f.id} onOpen={onOpenVisualModes} />
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
