import { useState } from "react";
import type { VisualModeEntry } from "./catalog";
import CompatibilityRow from "./CompatibilityRow";

interface Props {
  entry: VisualModeEntry;
}

function FieldChips({ items, tone }: { items: string[]; tone: "required" | "optional" }) {
  if (items.length === 0) {
    return <span className="text-xs text-neutral-500 italic">None</span>;
  }
  const cls =
    tone === "required"
      ? "bg-violet-500/10 text-violet-300 border-violet-500/30"
      : "bg-neutral-800/80 text-neutral-300 border-neutral-700";
  return (
    <div className="flex flex-wrap gap-1.5">
      {items.map((field) => (
        <span
          key={field}
          className={`text-[11px] font-mono px-2 py-0.5 rounded border ${cls}`}
        >
          {field}
        </span>
      ))}
    </div>
  );
}

export default function VisualModeDetail({ entry }: Props) {
  const [videoFailed, setVideoFailed] = useState(false);

  return (
    <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 overflow-hidden">
      <div className="relative aspect-video bg-neutral-950 overflow-hidden border-b border-neutral-800">
        {videoFailed ? (
          <div className="absolute inset-0 flex items-center justify-center bg-neutral-900">
            <span className="text-xs uppercase tracking-wider text-neutral-500">
              {entry.label} preview unavailable
            </span>
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

      <div className="p-6 space-y-6">
        <div>
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-lg font-semibold text-neutral-100">{entry.label}</h3>
            <span className="text-xs font-mono px-2 py-0.5 rounded bg-neutral-800 text-neutral-400">
              {entry.id}
            </span>
          </div>
          <p className="mt-2 text-sm text-neutral-300 leading-relaxed">{entry.longDescription}</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
              Required fields
            </div>
            <FieldChips items={entry.requiredFields} tone="required" />
          </div>
          <div className="space-y-2">
            <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
              Optional fields
            </div>
            <FieldChips items={entry.optionalFields} tone="optional" />
          </div>
        </div>

        <div className="space-y-2">
          <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
            Compatibility
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            <CompatibilityRow
              label="Standard subtitles"
              state={entry.compatibility.standardSubtitles}
            />
            <CompatibilityRow
              label="Eli overlay"
              state={entry.compatibility.eliOverlay}
            />
            <CompatibilityRow
              label="Scene FX (zoom punch / drift)"
              state={entry.compatibility.sceneFx}
            />
            <CompatibilityRow
              label="Title card eligible"
              state={entry.compatibility.titleCardEligible ? "yes" : "no"}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
              Distribution
            </div>
            <div className="inline-block px-3 py-1.5 rounded-full text-xs font-medium bg-sky-500/10 text-sky-300 border border-sky-500/30">
              {entry.distribution}
            </div>
          </div>
          <div className="space-y-2">
            <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
              Routing
            </div>
            <p className="text-sm text-neutral-300 leading-relaxed">{entry.routing}</p>
          </div>
        </div>

        {entry.notCompatibleWith.length > 0 && (
          <div className="space-y-2">
            <div className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
              Not compatible with
            </div>
            <ul className="space-y-1">
              {entry.notCompatibleWith.map((note) => (
                <li
                  key={note}
                  className="text-sm text-neutral-400 leading-relaxed pl-4 relative before:content-['•'] before:absolute before:left-1 before:text-neutral-600"
                >
                  {note}
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="pt-2 border-t border-neutral-800/60">
          <div className="text-[11px] text-neutral-500">
            Renderer:{" "}
            <span className="font-mono text-neutral-400">{entry.rendererPath}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
