import { ImageIcon, Loader2, Plus, Scissors, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { assetUrl, generatePopupCropPreview } from "../../api";
import type { PopupCropPreviewResult } from "../../types/testLab";

const DEFAULT_PROMPT = [
  "A stressed office worker stands centered as the anchor subject.",
  "Create popup cutouts for: a crossed-out chart, a wall clock, and a barred window.",
  "Flat 2D Headless Hero cartoon style, clean silhouettes, no text.",
].join("\n");

const DEFAULT_ITEMS = ["crossed-out chart", "wall clock", "barred window"];
const MAX_ITEMS = 5;

export default function PopupCropLab() {
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [items, setItems] = useState(DEFAULT_ITEMS);
  const [result, setResult] = useState<PopupCropPreviewResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const cleanedItems = useMemo(() => items.map((item) => item.trim()).filter(Boolean), [items]);
  const canGenerate = prompt.trim().length > 0 && cleanedItems.length > 0 && !busy;

  async function handleGenerate() {
    if (!canGenerate) return;
    setBusy(true);
    setError("");
    try {
      const next = await generatePopupCropPreview(prompt.trim(), cleanedItems);
      if (!next) {
        setError("The crop preview could not be generated.");
        return;
      }
      setResult(next);
    } finally {
      setBusy(false);
    }
  }

  function updateItem(index: number, value: string) {
    setItems((current) => current.map((item, i) => (i === index ? value : item)));
  }

  function addItem() {
    setItems((current) => (current.length >= MAX_ITEMS ? current : [...current, ""]));
  }

  function removeItem(index: number) {
    setItems((current) => current.filter((_, i) => i !== index));
  }

  return (
    <div className="grid h-full min-h-0 grid-cols-1 gap-4 xl:grid-cols-[420px_minmax(480px,1fr)]">
      <section className="min-h-0 overflow-y-auto rounded-lg border border-neutral-800 bg-neutral-900/60 p-4">
        <header>
          <p className="text-xs font-semibold uppercase text-neutral-500">Popup Crop Lab</p>
          <h2 className="mt-2 text-sm font-semibold text-neutral-100">Contact sheet prompt</h2>
          <p className="mt-1 text-xs leading-5 text-neutral-500">
            Generate one sheet, crop the anchor and each named item, then inspect the pieces before wiring this into rendering.
          </p>
        </header>

        <label className="mt-4 block">
          <span className="text-xs font-medium text-neutral-300">Prompt</span>
          <textarea
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            rows={8}
            className="mt-2 w-full resize-y rounded-md border border-neutral-800 bg-neutral-950/80 px-3 py-2 text-sm leading-6 text-neutral-100 outline-none transition-colors placeholder:text-neutral-600 hover:border-neutral-700 focus:border-violet-500"
            placeholder="Describe the anchored character and the popup cutout subjects."
          />
        </label>

        <div className="mt-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-medium text-neutral-300">Items to crop</p>
              <p className="mt-1 text-xs text-neutral-500">The anchor crop is automatic. Add the popup item subjects here.</p>
            </div>
            <button
              onClick={addItem}
              disabled={items.length >= MAX_ITEMS}
              className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-neutral-800 bg-neutral-950/70 text-neutral-300 transition-colors hover:border-neutral-700 hover:text-neutral-100 disabled:cursor-not-allowed disabled:text-neutral-600"
              title="Add item"
            >
              <Plus className="h-4 w-4" />
            </button>
          </div>
          <div className="mt-3 space-y-2">
            {items.map((item, index) => (
              <div key={index} className="flex items-center gap-2">
                <input
                  value={item}
                  onChange={(event) => updateItem(index, event.target.value)}
                  className="min-w-0 flex-1 rounded-md border border-neutral-800 bg-neutral-950/80 px-3 py-2 text-sm text-neutral-100 outline-none transition-colors placeholder:text-neutral-600 hover:border-neutral-700 focus:border-violet-500"
                  placeholder={`Item ${index + 1}`}
                />
                <button
                  onClick={() => removeItem(index)}
                  disabled={items.length <= 1}
                  className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-neutral-800 bg-neutral-950/70 text-neutral-400 transition-colors hover:border-red-500/70 hover:text-red-300 disabled:cursor-not-allowed disabled:text-neutral-700"
                  title="Remove item"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        </div>

        {error && (
          <div className="mt-4 rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs leading-5 text-red-200">
            {error}
          </div>
        )}

        <button
          onClick={handleGenerate}
          disabled={!canGenerate}
          className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-md bg-violet-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-violet-500 disabled:cursor-not-allowed disabled:bg-neutral-800 disabled:text-neutral-500"
        >
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Scissors className="h-4 w-4" />}
          Generate Sheet & Crops
        </button>
      </section>

      <section className="min-h-0 overflow-y-auto rounded-lg border border-neutral-800 bg-neutral-900/60 p-4">
        {result ? (
          <div className="space-y-4">
            <div>
              <div className="flex items-center gap-2">
                <ImageIcon className="h-4 w-4 text-sky-300" />
                <h2 className="text-sm font-semibold text-neutral-100">Generated sheet</h2>
              </div>
              <div className="mt-3 overflow-hidden rounded-md border border-neutral-800 bg-neutral-950">
                <img src={assetUrl(result.sheet_url)} alt="Generated contact sheet" className="w-full object-contain" />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-sm font-semibold text-neutral-100">Cropped output</h3>
                <span className="text-xs text-neutral-500">{result.crops.length} crops</span>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-3">
                {result.crops.map((crop) => (
                  <div key={`${crop.role}-${crop.label}`} className="rounded-md border border-neutral-800 bg-neutral-950/70 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <p className="truncate text-xs font-medium text-neutral-200">{crop.label}</p>
                      <span className="shrink-0 rounded border border-neutral-800 px-1.5 py-0.5 text-[10px] uppercase text-neutral-500">
                        {crop.role}
                      </span>
                    </div>
                    <div className="mt-2 flex aspect-video items-center justify-center overflow-hidden rounded border border-neutral-800 bg-neutral-900">
                      <img src={assetUrl(crop.url)} alt={crop.label} className="h-full w-full object-contain" />
                    </div>
                    <p className="mt-2 font-mono text-[10px] text-neutral-600">[{crop.box.join(", ")}]</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <div className="flex min-h-[420px] items-center justify-center rounded-md border border-dashed border-neutral-800 bg-neutral-950/40">
            <div className="max-w-xs text-center">
              <Scissors className="mx-auto h-8 w-8 text-neutral-600" />
              <p className="mt-3 text-sm font-medium text-neutral-300">No crop preview yet</p>
              <p className="mt-1 text-xs leading-5 text-neutral-500">
                Generate a contact sheet to inspect the anchor crop and each popup item crop.
              </p>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}
