import type { ReactNode } from "react";

type StylePresetToggleProps = {
  /** Current value of the project's eli_enabled flag (or global default). */
  eliEnabled: boolean;
  /** Current value of the style_preset_enabled flag. */
  enabled: boolean;
  /** Called when user flips the toggle. Ignored when Eli is enabled. */
  onChange: (enabled: boolean) => void;
  /** Name of the active global preset, or null if none is selected. */
  activePresetName: string | null;
};

/**
 * Project-level toggle for "use the active global style preset for this video."
 *
 * - When Eli is enabled, this toggle is forced off and visually greyed out.
 * - When the toggle is on but no preset is active, a warning state is shown.
 * - Inline descriptive text always renders so users see the resulting behavior
 *   *before* flipping the switch.
 */
export function StylePresetToggle({
  eliEnabled,
  enabled,
  onChange,
  activePresetName,
}: StylePresetToggleProps) {
  const greyed = eliEnabled;
  const effectivelyOn = !greyed && enabled;
  const noActivePreset = effectivelyOn && !activePresetName;

  let descriptor: ReactNode;
  if (greyed) {
    descriptor = (
      <span className="text-neutral-500">
        Style presets only apply when Eli is disabled for this video.
      </span>
    );
  } else if (noActivePreset) {
    descriptor = (
      <span className="text-amber-400">
        ⚠ No active preset. Pick one in Settings → Style Presets, or generate a new one.
      </span>
    );
  } else if (effectivelyOn) {
    descriptor = (
      <span className="text-neutral-400">
        Applies the preset across all scenes, frames, thumbnails, and chapter cards.
      </span>
    );
  } else {
    descriptor = (
      <span className="text-neutral-400">No style preset will be used.</span>
    );
  }

  const checkboxState = greyed ? false : enabled;

  return (
    <div
      className={`flex flex-col gap-1 rounded-md border border-neutral-800 bg-neutral-900 p-3 ${
        greyed ? "opacity-60" : ""
      }`}
    >
      <label className="flex items-center gap-2 text-sm font-medium text-neutral-100">
        <input
          type="checkbox"
          checked={checkboxState}
          disabled={greyed}
          onChange={(e) => onChange(e.target.checked)}
          className="h-4 w-4 rounded border-neutral-700 bg-neutral-800 text-violet-500 focus:ring-violet-500"
        />
        <span>Style preset</span>
        {effectivelyOn && activePresetName && (
          <span className="text-xs font-normal text-neutral-400">
            Active: <span className="text-neutral-200">"{activePresetName}"</span>
          </span>
        )}
        {greyed && (
          <span className="text-xs font-normal text-neutral-500">(Eli is on)</span>
        )}
      </label>
      <div className="pl-6 text-xs leading-relaxed">{descriptor}</div>
    </div>
  );
}
