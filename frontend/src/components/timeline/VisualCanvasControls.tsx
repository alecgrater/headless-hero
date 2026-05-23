import { useEffect, useMemo, useState } from "react";

interface Props {
  color: string;
  palette: string[];
  saving?: boolean;
  onSelect: (color: string) => void;
}

function normalizeHex(value: string): string | null {
  const text = value.trim().replace(/^#/, "");
  if (!/^[0-9a-fA-F]{6}$/.test(text)) return null;
  return `#${text.toUpperCase()}`;
}

export default function VisualCanvasControls({ color, palette, saving = false, onSelect }: Props) {
  const [draft, setDraft] = useState(color);
  const normalizedDraft = useMemo(() => normalizeHex(draft), [draft]);
  const showInvalid = draft.trim().length > 0 && !normalizedDraft;
  const swatchColor = normalizedDraft ?? color;

  useEffect(() => {
    setDraft(color);
  }, [color]);

  const handleSelect = () => {
    if (!normalizedDraft) return;
    onSelect(normalizedDraft);
  };

  return (
    <div className="rounded-lg border border-neutral-800 bg-neutral-900 p-4">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="space-y-1">
          <h3 className="text-sm font-semibold text-neutral-100">Canvas Color</h3>
          <p className="max-w-2xl text-xs leading-5 text-neutral-400">
            The canvas color sits behind every scene. Full-frame visuals cover it completely; popup and flipflop treatments let it show through.
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start">
          <div
            className="h-9 w-9 shrink-0 rounded-lg border border-neutral-700"
            style={{ backgroundColor: swatchColor }}
            title={swatchColor}
          />
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="#F6C54A"
                className="w-32 rounded-lg border border-neutral-700 bg-neutral-950 px-3 py-2 font-mono text-xs text-neutral-100 placeholder-neutral-600 outline-none transition-colors hover:border-neutral-600 focus:border-violet-500"
                aria-invalid={showInvalid}
              />
              <button
                type="button"
                onClick={handleSelect}
                disabled={saving || !normalizedDraft}
                className="rounded-lg bg-violet-600 px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-violet-600"
              >
                {saving ? "Saving..." : "Select"}
              </button>
            </div>
            {showInvalid && (
              <p className="mt-1 text-xs text-amber-300">Enter a valid 6-digit hex color.</p>
            )}
          </div>
        </div>
      </div>

      {palette.length > 0 && (
        <div className="mt-4 flex flex-wrap gap-2">
          {palette.map((paletteColor) => {
            const normalizedPaletteColor = normalizeHex(paletteColor) ?? paletteColor;
            const selected = normalizedPaletteColor.toUpperCase() === color.toUpperCase();
            return (
              <button
                key={paletteColor}
                type="button"
                onClick={() => {
                  setDraft(normalizedPaletteColor);
                  onSelect(normalizedPaletteColor);
                }}
                disabled={saving}
                className={`h-8 w-8 rounded-lg border transition-colors hover:border-neutral-300 disabled:cursor-wait disabled:opacity-60 ${
                  selected ? "border-violet-300 ring-2 ring-violet-500/40" : "border-neutral-700"
                }`}
                style={{ backgroundColor: normalizedPaletteColor }}
                title={normalizedPaletteColor}
                aria-label={`Select canvas color ${normalizedPaletteColor}`}
              />
            );
          })}
        </div>
      )}
    </div>
  );
}
