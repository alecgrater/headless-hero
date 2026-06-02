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
            Read-only reference — every visual mode the script generator and validator can route scenes into.
          </p>
        </div>
        <div className="text-[10px] text-neutral-600">
          {VISUAL_MODE_CATALOG.length} modes
        </div>
      </div>

      <div className="space-y-2">
        <div>
          <h3 className="text-sm font-semibold text-neutral-100">Workflow</h3>
          <p className="text-xs leading-5 text-neutral-500">
            Visual rhythm is planned before voiceover during script generation. Duration targets are tied to visual mode,
            so normal image beats stay short while captions, comparison boards, popup sequences, stat cards, and planned
            video scenes get the breathing room their renderer needs.
          </p>
        </div>
        <p className="text-xs leading-5 text-neutral-500">
          Post-voiceover validation uses real audio and word timing to prepare layers, video eligibility, and asset timing.
          It can downgrade unsafe modes, but it should not be the main place where new specialized modes are discovered.
        </p>
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
