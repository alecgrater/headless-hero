import { useState } from "react";
import type { VisualMode } from "./catalog";
import { VISUAL_MODE_CATALOG } from "./catalog";
import VisualModeCard from "./VisualModeCard";
import VisualModeDetail from "./VisualModeDetail";

export default function VisualModesSection() {
  const [selectedId, setSelectedId] = useState<VisualMode>("full_frame");
  const selected =
    VISUAL_MODE_CATALOG.find((entry) => entry.id === selectedId) ?? VISUAL_MODE_CATALOG[0];

  return (
    <div className="px-6 py-5 space-y-4">
      <div className="flex items-baseline justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold text-neutral-100">Visual Modes</h2>
          <p className="text-[11px] text-neutral-500">
            Read-only reference — every visual mode the script generator and analyzer can route scenes into.
          </p>
        </div>
        <div className="text-[10px] text-neutral-600">
          {VISUAL_MODE_CATALOG.length} modes
        </div>
      </div>

      <VisualModeDetail entry={selected} />

      <div className="space-y-1.5">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
          All modes
        </div>
        <div className="grid grid-cols-9 gap-2">
          {VISUAL_MODE_CATALOG.map((entry) => (
            <VisualModeCard
              key={entry.id}
              entry={entry}
              selected={entry.id === selectedId}
              onSelect={() => setSelectedId(entry.id)}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
