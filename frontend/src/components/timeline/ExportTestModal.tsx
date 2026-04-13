import { useState } from "react";
import type { ExportTestOptions } from "../../api";

interface Props {
  onRun: (options: ExportTestOptions) => void;
  onClose: () => void;
}

const STEPS = [
  { key: "regen_title_cards" as const, label: "Title Cards", desc: "Regenerate composite title card images", cost: "Gemini" },
  { key: "regen_images" as const, label: "Images", desc: "Regenerate scene images", cost: "Gemini" },
  { key: "regen_audio" as const, label: "Audio", desc: "Regenerate voiceover", cost: "ElevenLabs" },
  { key: "regen_fx" as const, label: "FX", desc: "Regenerate zoom punch", cost: "Claude" },
  { key: "regen_eli" as const, label: "Eli Overlays", desc: "Regenerate character animation keyframes", cost: "Claude" },
];

export default function ExportTestModal({ onRun, onClose }: Props) {
  const [options, setOptions] = useState<ExportTestOptions>({
    regen_title_cards: false,
    regen_images: false,
    regen_audio: false,
    regen_fx: false,
    regen_eli: false,
  });

  const selectedCount = Object.values(options).filter(Boolean).length;
  const allSelected = selectedCount === STEPS.length;

  const toggleAll = () => {
    const next = !allSelected;
    setOptions({
      regen_title_cards: next,
      regen_images: next,
      regen_audio: next,
      regen_fx: next,
      regen_eli: next,
    });
  };

  const toggle = (key: keyof ExportTestOptions) => {
    setOptions((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-8" onClick={onClose}>
      <div
        className="bg-neutral-900 border border-neutral-800 rounded-2xl w-full max-w-md flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-800">
          <h2 className="text-lg font-semibold text-neutral-100">Export Test</h2>
          <button
            onClick={onClose}
            className="text-neutral-500 hover:text-neutral-300 transition-colors text-xl leading-none"
          >
            &times;
          </button>
        </div>

        {/* Body */}
        <div className="px-6 py-4 space-y-4">
          <p className="text-sm text-neutral-400">
            Select steps to regenerate. Unchecked steps keep existing data.
          </p>

          {/* Regenerate All toggle */}
          <label className="flex items-center gap-3 px-3 py-2 rounded-lg bg-neutral-800/60 border border-neutral-700/40 cursor-pointer hover:bg-neutral-800 transition-colors">
            <input
              type="checkbox"
              checked={allSelected}
              onChange={toggleAll}
              className="w-4 h-4 rounded accent-rose-500"
            />
            <span className="text-sm font-medium text-neutral-200">Regenerate All</span>
          </label>

          {/* Individual steps */}
          <div className="space-y-1">
            {STEPS.map((step) => (
              <label
                key={step.key}
                className="flex items-center gap-3 px-3 py-2.5 rounded-lg cursor-pointer hover:bg-neutral-800/40 transition-colors"
              >
                <input
                  type="checkbox"
                  checked={options[step.key]}
                  onChange={() => toggle(step.key)}
                  className="w-4 h-4 rounded accent-rose-500"
                />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-neutral-200">{step.label}</span>
                    <span className="text-[10px] text-neutral-500 bg-neutral-800 px-1.5 py-0.5 rounded">{step.cost}</span>
                  </div>
                  <p className="text-xs text-neutral-500 mt-0.5">{step.desc}</p>
                </div>
              </label>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-neutral-800 flex justify-end">
          <button
            onClick={() => onRun(options)}
            className="px-5 py-2 text-sm rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-semibold transition-colors"
          >
            {selectedCount > 0
              ? `Run Export Test (${selectedCount} step${selectedCount !== 1 ? "s" : ""} + render)`
              : "Run Export Test (render only)"}
          </button>
        </div>
      </div>
    </div>
  );
}
