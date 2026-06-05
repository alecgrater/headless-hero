import { useEffect, useState } from "react";
import { getFormats } from "../../../api";
import type { VideoFormat } from "../../../types/format";
import SettingsSectionHeader from "../SettingsSectionHeader";
import { allVisualModes, modeChipsForFormat, type ModeChip } from "./modes";

interface DetailItem {
  label: string;
  value: string;
}

function projectShape(format: VideoFormat): string {
  return format.level_count_min === format.level_count_max
    ? `${format.level_count_min} ${format.level_label}s`
    : `${format.level_count_min}-${format.level_count_max} ${format.level_label}s`;
}

function titleCardStrategy(format: VideoFormat): string {
  return format.title_card_strategy_kind === "composite-grid" ? "Composite grid" : "Cinematic chapters";
}

function enabledLabel(value: boolean): string {
  return value ? "Enabled" : "Not used";
}

function detailItems(format: VideoFormat): DetailItem[] {
  return [
    { label: "Project shape", value: projectShape(format) },
    { label: "Chapter cards", value: titleCardStrategy(format) },
    { label: "Cold open", value: enabledLabel(format.supports_cold_open) },
    { label: "Hook scoring", value: enabledLabel(format.supports_hook_scoring) },
    { label: "Segmented writing", value: enabledLabel(format.supports_segmented_generation) },
    { label: "Visual rhythm", value: `${format.allowed_visual_beats.join(", ")}; max ${format.max_consecutive_same_beat} in a row` },
    { label: "Mode coverage", value: `${format.supported_visual_modes.length} visual modes supported` },
  ];
}

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
  const [selectedFormatId, setSelectedFormatId] = useState<string | null>(null);

  useEffect(() => {
    getFormats()
      .then((loadedFormats) => {
        setFormats(loadedFormats);
        setSelectedFormatId((current) =>
          current && loadedFormats.some((format) => format.id === current)
            ? current
            : loadedFormats[0]?.id ?? null,
        );
      })
      .catch(() => setError("Could not load script formats."));
  }, []);

  if (error) return <div className="px-6 py-5 text-sm text-rose-400">{error}</div>;
  if (!formats) return <div className="px-6 py-5 text-sm text-neutral-500">Loading…</div>;

  const universe = allVisualModes(formats);
  const selectedFormat =
    formats.find((format) => format.id === selectedFormatId) ?? formats[0];
  const { supported, disabled } = modeChipsForFormat(selectedFormat, universe);

  return (
    <div className="px-6 py-6 space-y-6">
      <SettingsSectionHeader
        level={2}
        title="Script Types"
        description="Script types define the story contract for a project: how many sections it has, how title cards behave, which narration rules matter, and how visual modes can be used. Choose the format that matches the viewer promise first, then let scene-by-scene routing choose the best visual mode for each beat."
        descriptionClassName="max-w-4xl"
      />

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

      <section className="space-y-2">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-neutral-100">Format Library</h3>
          <span className="text-[10px] text-neutral-600">{formats.length} formats</span>
        </div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-3">
          {formats.map((format) => {
            const selected = format.id === selectedFormat.id;
            return (
              <button
                key={format.id}
                type="button"
                onClick={() => setSelectedFormatId(format.id)}
                className={`flex min-h-40 flex-col rounded-lg border p-4 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 ${
                  selected
                    ? "border-violet-500/50 bg-violet-500/10"
                    : "border-neutral-800 bg-neutral-900/40 hover:border-neutral-700 hover:bg-neutral-900/70"
                }`}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-neutral-100">{format.display_name}</div>
                    <div className="mt-1 text-[10px] font-mono text-neutral-600">{format.id}</div>
                  </div>
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-medium ${
                    selected ? "bg-violet-500/20 text-violet-200" : "bg-neutral-800 text-neutral-500"
                  }`}>
                    {projectShape(format)}
                  </span>
                </div>
                <p className="mt-3 line-clamp-3 text-xs leading-5 text-neutral-400">
                  {format.short_description}
                </p>
                <div className="mt-auto flex flex-wrap gap-1.5 pt-3">
                  <span className="rounded bg-neutral-950/60 px-1.5 py-0.5 text-[10px] text-neutral-500">
                    {titleCardStrategy(format)}
                  </span>
                  <span className="rounded bg-neutral-950/60 px-1.5 py-0.5 text-[10px] text-neutral-500">
                    {format.supported_visual_modes.length} modes
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </section>

      <section className="rounded-lg border border-neutral-800 bg-neutral-900/45 p-5">
        <div className="flex flex-col gap-5 xl:flex-row">
          <div className="min-w-0 flex-1 space-y-5">
            <div>
              <div className="text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
                Selected format
              </div>
              <h3 className="mt-1 text-lg font-semibold text-neutral-100">
                {selectedFormat.display_name}
              </h3>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-neutral-400">
                {selectedFormat.short_description}
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {detailItems(selectedFormat).map((item) => (
                <div key={item.label} className="rounded-md border border-neutral-800 bg-neutral-950/35 px-3 py-2">
                  <div className="text-[10px] font-semibold uppercase tracking-wider text-neutral-600">
                    {item.label}
                  </div>
                  <div className="mt-1 text-xs leading-5 text-neutral-300">{item.value}</div>
                </div>
              ))}
            </div>

            <div className="space-y-2">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
                Format notes
              </div>
              <div className="grid gap-2 lg:grid-cols-2">
                {selectedFormat.reference_notes.map((note, i) => (
                  <div key={`${note.category}-${i}`} className="rounded-md border border-neutral-800 bg-neutral-950/25 p-3 text-xs leading-5">
                    <span className="font-semibold text-neutral-300">{note.category}: </span>
                    <span className="text-neutral-400">{note.text}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <aside className="w-full shrink-0 space-y-4 xl:w-96">
            <div className="rounded-lg border border-neutral-800 bg-neutral-950/35 p-4">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
                Supported modes
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {supported.map((chip) => (
                  <Chip key={chip.id} chip={chip} formatId={selectedFormat.id} onOpen={onOpenVisualModes} />
                ))}
              </div>
              {disabled.length > 0 && (
                <>
                  <div className="mt-4 text-[10px] font-semibold uppercase tracking-wider text-neutral-600">
                    Disabled here
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {disabled.map((chip) => (
                      <Chip key={chip.id} chip={chip} disabled formatId={selectedFormat.id} onOpen={onOpenVisualModes} />
                    ))}
                  </div>
                </>
              )}
            </div>
          </aside>
        </div>
      </section>
    </div>
  );
}
