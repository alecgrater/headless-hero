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
    <div className="max-w-6xl px-8 py-8 space-y-6 pb-24">
      <div className="space-y-1.5">
        <h2 className="text-lg font-semibold text-neutral-100">Visual Modes</h2>
        <p className="text-sm text-neutral-400">
          Read-only reference for the visual modes the script generator and post-voiceover analyzer
          can route scenes into. Click any mode to see required fields, compatibility, distribution
          rules, and renderer behavior.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
        {VISUAL_MODE_CATALOG.map((entry) => (
          <VisualModeCard
            key={entry.id}
            entry={entry}
            selected={entry.id === selectedId}
            onSelect={() => setSelectedId(entry.id)}
          />
        ))}
      </div>

      <VisualModeDetail entry={selected} />
    </div>
  );
}
