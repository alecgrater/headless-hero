import { useId, type ReactNode } from "react";

type StylePresetToggleProps = {
  /** Current value of the project's eli_enabled flag (or global default). */
  eliEnabled: boolean;
  /** Current value of the style_preset_enabled flag. */
  enabled: boolean;
  /** Called when user changes whether the style preset applies. */
  onChange: (enabled: boolean) => void;
  /** Called when user changes whether Eli is the default visual identity. */
  onEliChange: (enabled: boolean) => void;
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
  onEliChange,
  activePresetName,
}: StylePresetToggleProps) {
  const radioGroupName = useId();
  const selectedMode = eliEnabled ? "eli" : enabled ? "style" : "unstyled";

  const options: Array<{
    id: "style" | "eli" | "unstyled";
    title: string;
    description: ReactNode;
  }> = [
    {
      id: "style",
      title: "Style preset and main character",
      description: activePresetName ? (
        <span>
          Uses <span className="text-neutral-200">"{activePresetName}"</span> across scenes, thumbnails, and chapter cards.
        </span>
      ) : (
        <span className="text-amber-300">
          No active preset selected. Pick one in Visual Identity before relying on this default.
        </span>
      ),
    },
    {
      id: "eli",
      title: "Eli host overlay",
      description: "New projects use Eli as the recurring on-screen host. Style presets are bypassed for this mode.",
    },
    {
      id: "unstyled",
      title: "No global style preset",
      description: "New projects use normal prompt-driven visuals without Eli or the active preset.",
    },
  ];

  const selectMode = (mode: "style" | "eli" | "unstyled") => {
    if (mode === "style") {
      onEliChange(false);
      onChange(true);
      return;
    }
    if (mode === "eli") {
      onEliChange(true);
      onChange(false);
      return;
    }
    onEliChange(false);
    onChange(false);
  };

  return (
    <div role="radiogroup" aria-label="Visual identity" className="grid gap-2 md:grid-cols-3">
      {options.map((option) => {
        const selected = selectedMode === option.id;
        return (
          <label
            key={option.id}
            className={`flex min-h-28 cursor-pointer flex-col rounded-lg border p-3 transition-colors ${
              selected
                ? "border-violet-500 bg-violet-500/10 text-neutral-100"
                : "border-neutral-800 bg-neutral-950/40 text-neutral-300 hover:border-neutral-700 hover:bg-neutral-900"
            }`}
          >
            <span className="flex items-start justify-between gap-3">
              <span className="text-sm font-medium">{option.title}</span>
              <input
                type="radio"
                name={radioGroupName}
                checked={selected}
                onChange={() => selectMode(option.id)}
                className="mt-0.5 h-4 w-4 shrink-0 border-neutral-700 bg-neutral-800 text-violet-500 focus:ring-violet-500"
              />
            </span>
            <span className="mt-2 text-xs leading-relaxed text-neutral-500">{option.description}</span>
          </label>
        )}
      )}
    </div>
  );
}
