import { useState } from "react";
import type { VisualMode } from "./catalog";
import SettingsSectionHeader from "../SettingsSectionHeader";
import { VISUAL_MODE_CATALOG } from "./catalog";
import VisualModeCard from "./VisualModeCard";
import VisualModeDetail from "./VisualModeDetail";

export default function VisualModesSection() {
  const [selectedId, setSelectedId] = useState<VisualMode>("full_frame");
  const selected =
    VISUAL_MODE_CATALOG.find((entry) => entry.id === selectedId) ?? VISUAL_MODE_CATALOG[0];

  return (
    <div className="px-6 py-6 space-y-6">
      <div className="flex items-baseline justify-between gap-4">
        <SettingsSectionHeader
          level={2}
          title="Visual Modes"
          description="Visual modes are the scene-level render plans that decide what kind of media gets made: a single image, a frame sequence, a layered board, editorial text, a statistic card, or an AI video clip. They are chosen for scene intent, not for an even distribution."
          descriptionClassName="max-w-4xl"
        />
        <div className="text-[10px] text-neutral-600">
          {VISUAL_MODE_CATALOG.length} modes
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
          <h3 className="text-sm font-semibold text-neutral-100">Planned Before Voiceover</h3>
          <p className="mt-2 text-xs leading-5 text-neutral-400">
            The outline phase first marks visual opportunities per segment, then scene writing shapes
            narration and duration around the chosen modes. Normal image beats stay short while
            renderer-owned modes get breathing room.
          </p>
        </div>
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
          <h3 className="text-sm font-semibold text-neutral-100">Validated After Timing</h3>
          <p className="mt-2 text-xs leading-5 text-neutral-400">
            Post-voiceover validation uses real audio and word timing to prepare layers, video
            eligibility, and asset timing. It may downgrade unsafe modes.
          </p>
        </div>
        <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4">
          <h3 className="text-sm font-semibold text-neutral-100">Renderer Owns Text</h3>
          <p className="mt-2 text-xs leading-5 text-neutral-400">
            Captions, stat cards, title cards, and comparison labels render readable text in
            Remotion. Generated images should not bake in labels or subtitles.
          </p>
        </div>
      </div>

      <VisualModeDetail entry={selected} />

      <div className="space-y-1.5">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-neutral-500">
          Select a mode
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
