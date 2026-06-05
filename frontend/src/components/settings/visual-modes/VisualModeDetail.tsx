import { useEffect, useState } from "react";
import { Check, X } from "lucide-react";
import type { VisualModeEntry } from "./catalog";

interface Props {
  entry: VisualModeEntry;
}

function FieldChips({ items, tone }: { items: string[]; tone: "required" | "optional" }) {
  if (items.length === 0) {
    return <span className="text-[11px] text-neutral-600 italic">None</span>;
  }
  const cls =
    tone === "required"
      ? "bg-violet-500/10 text-violet-300 border-violet-500/30"
      : "bg-neutral-800/80 text-neutral-300 border-neutral-700";
  return (
    <div className="flex flex-wrap gap-1">
      {items.map((field) => (
        <span
          key={field}
          className={`text-[10px] font-mono px-1.5 py-0.5 rounded border ${cls}`}
        >
          {field}
        </span>
      ))}
    </div>
  );
}

function CompatBadge({
  label,
  positive,
  valueLabel,
}: {
  label: string;
  positive: boolean;
  valueLabel: string;
}) {
  return (
    <div className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-neutral-950/60 border border-neutral-800/70">
      {positive ? (
        <Check className="w-3 h-3 text-emerald-400 shrink-0" />
      ) : (
        <X className="w-3 h-3 text-neutral-500 shrink-0" />
      )}
      <span className="text-[10px] text-neutral-400 leading-tight">{label}</span>
      <span
        className={`text-[10px] font-medium ml-auto ${positive ? "text-emerald-400" : "text-neutral-500"}`}
      >
        {valueLabel}
      </span>
    </div>
  );
}

export default function VisualModeDetail({ entry }: Props) {
  const [videoFailed, setVideoFailed] = useState(false);

  useEffect(() => {
    setVideoFailed(false);
  }, [entry.id]);

  const compat = entry.compatibility;

  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 overflow-hidden">
      <div className="grid grid-cols-1 lg:grid-cols-[minmax(0,420px)_1fr] gap-0">
        {/* Left: video preview */}
        <div className="relative aspect-video lg:aspect-auto lg:h-full bg-neutral-950 overflow-hidden border-b lg:border-b-0 lg:border-r border-neutral-800">
          {videoFailed ? (
            <div className="absolute inset-0 flex flex-col items-center justify-center gap-1">
              <span className="text-[10px] uppercase tracking-wider text-neutral-600">
                {entry.label}
              </span>
              <span className="text-[10px] text-neutral-700">preview unavailable</span>
            </div>
          ) : (
            <video
              key={entry.id}
              src={entry.previewSrc}
              autoPlay
              loop
              muted
              playsInline
              onError={() => setVideoFailed(true)}
              className="w-full h-full object-cover"
            />
          )}
        </div>

        {/* Right: info */}
        <div className="p-5 space-y-4 min-w-0">
          {/* Header */}
          <div className="space-y-1.5">
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-lg font-semibold tracking-tight text-neutral-100">{entry.label}</h3>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-neutral-800 text-neutral-400">
                {entry.id}
              </span>
              <span className="ml-auto text-[10px] px-2 py-0.5 rounded-full bg-sky-500/10 text-sky-300 border border-sky-500/30">
                {entry.distribution}
              </span>
            </div>
            <p className="text-[12px] text-neutral-300 leading-snug">{entry.longDescription}</p>
          </div>

          <div className="space-y-1 border-t border-neutral-800/60 pt-3">
            <div className="text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
              Duration profile
            </div>
            <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
              <p className="text-xs font-semibold text-sky-300">{entry.durationLabel}</p>
              <span className="w-fit rounded bg-neutral-800 px-1.5 py-0.5 text-[10px] font-mono text-neutral-400">
                {entry.durationProfile}
              </span>
            </div>
            <p className="text-[11px] leading-snug text-neutral-500">{entry.durationDescription}</p>
          </div>

          {/* Fields + Compatibility */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-3">
            <div className="space-y-1">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
                Required
              </div>
              <FieldChips items={entry.requiredFields} tone="required" />
            </div>
            <div className="space-y-1">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
                Optional
              </div>
              <FieldChips items={entry.optionalFields} tone="optional" />
            </div>
            <div className="md:col-span-2 space-y-1">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
                Compatibility
              </div>
              <div className="grid grid-cols-2 gap-1.5">
                <CompatBadge
                  label="Subtitles"
                  positive={compat.standardSubtitles === "supported"}
                  valueLabel={compat.standardSubtitles === "supported" ? "On" : "Off"}
                />
                <CompatBadge
                  label="Eli overlay"
                  positive={compat.eliOverlay === "supported"}
                  valueLabel={compat.eliOverlay === "supported" ? "On" : "Off"}
                />
                <CompatBadge
                  label="Scene FX"
                  positive={compat.sceneFx === "supported"}
                  valueLabel={compat.sceneFx === "supported" ? "On" : "Off"}
                />
                <CompatBadge
                  label="Title card"
                  positive={compat.titleCardEligible}
                  valueLabel={compat.titleCardEligible ? "Yes" : "No"}
                />
              </div>
            </div>
          </div>

          {/* Routing + Not compatible */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-x-4 gap-y-3">
            <div className="space-y-1">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
                Routing
              </div>
              <p className="text-[11px] text-neutral-400 leading-snug">{entry.routing}</p>
            </div>
            {entry.notCompatibleWith.length > 0 ? (
              <div className="space-y-1">
                <div className="text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
                  Avoid for
                </div>
                <ul className="space-y-0.5">
                  {entry.notCompatibleWith.map((note) => (
                    <li
                      key={note}
                      className="text-[11px] text-neutral-400 leading-snug pl-3 relative before:content-['•'] before:absolute before:left-0 before:text-neutral-600"
                    >
                      {note}
                    </li>
                  ))}
                </ul>
              </div>
            ) : (
              <div className="space-y-1">
                <div className="text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
                  Avoid for
                </div>
                <p className="text-[11px] text-neutral-600 italic leading-snug">
                  No conflicts — works alongside other modes.
                </p>
              </div>
            )}
          </div>

          {/* Renderer path */}
          <div className="pt-2 border-t border-neutral-800/60">
            <div className="text-[10px] text-neutral-500">
              Renderer:{" "}
              <span className="font-mono text-neutral-400">{entry.rendererPath}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
