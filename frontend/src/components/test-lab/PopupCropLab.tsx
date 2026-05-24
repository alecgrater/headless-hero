import { ImageIcon, Loader2, Plus, Scissors, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { assetUrl, generatePopupCropPreview } from "../../api";
import type { PopupCropPreviewResult } from "../../types/testLab";

const DEFAULT_ANCHOR_PROMPT = [
  "A stressed recurring office worker character, full body, hands on head, centered and large.",
  "Use the same detailed character style as normal scene protagonists.",
  "No text.",
].join("\n");

const DEFAULT_ITEM_PROMPT = [
  "Flat 2D Headless Hero cartoon icon style, clean silhouettes.",
  "The popup items should read clearly as separate symbolic cutouts.",
  "No text.",
].join("\n");

const DEFAULT_ITEMS = ["crossed-out chart", "wall clock", "barred window"];
const MAX_ITEMS = 5;

export default function PopupCropLab() {
  const [anchorPrompt, setAnchorPrompt] = useState(DEFAULT_ANCHOR_PROMPT);
  const [itemPrompt, setItemPrompt] = useState(DEFAULT_ITEM_PROMPT);
  const [items, setItems] = useState(DEFAULT_ITEMS);
  const [result, setResult] = useState<PopupCropPreviewResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const cleanedItems = useMemo(() => items.map((item) => item.trim()).filter(Boolean), [items]);
  const canGenerate = anchorPrompt.trim().length > 0 && itemPrompt.trim().length > 0 && cleanedItems.length > 0 && !busy;

  async function handleGenerate() {
    if (!canGenerate) return;
    setBusy(true);
    setError("");
    try {
      const next = await generatePopupCropPreview(anchorPrompt.trim(), itemPrompt.trim(), cleanedItems);
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
          <h2 className="mt-2 text-sm font-semibold text-neutral-100">Anchor and item prompts</h2>
          <p className="mt-1 text-xs leading-5 text-neutral-500">
            Generate the scene character separately, then generate ordered popup items on one sheet and inspect the keyed crops.
          </p>
        </header>

        <label className="mt-4 block">
          <span className="text-xs font-medium text-neutral-300">Anchor character prompt</span>
          <textarea
            value={anchorPrompt}
            onChange={(event) => setAnchorPrompt(event.target.value)}
            rows={5}
            className="mt-2 w-full resize-y rounded-md border border-neutral-800 bg-neutral-950/80 px-3 py-2 text-sm leading-6 text-neutral-100 outline-none transition-colors placeholder:text-neutral-600 hover:border-neutral-700 focus:border-violet-500"
            placeholder="Describe the recurring character pose for this scene."
          />
        </label>

        <label className="mt-4 block">
          <span className="text-xs font-medium text-neutral-300">Popup item sheet prompt</span>
          <textarea
            value={itemPrompt}
            onChange={(event) => setItemPrompt(event.target.value)}
            rows={5}
            className="mt-2 w-full resize-y rounded-md border border-neutral-800 bg-neutral-950/80 px-3 py-2 text-sm leading-6 text-neutral-100 outline-none transition-colors placeholder:text-neutral-600 hover:border-neutral-700 focus:border-violet-500"
            placeholder="Describe the visual style for the popup item cutouts."
          />
        </label>

        <div className="mt-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-medium text-neutral-300">Items to crop</p>
              <p className="mt-1 text-xs text-neutral-500">Items are cropped left to right in this exact order.</p>
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
          Generate Anchor, Sheet & Crops
        </button>
      </section>

      <section className="min-h-0 overflow-y-auto rounded-lg border border-neutral-800 bg-neutral-900/60 p-4">
        {result ? (
          <div className="space-y-4">
            <div>
              <div className="flex items-center gap-2">
                <ImageIcon className="h-4 w-4 text-sky-300" />
                <h2 className="text-sm font-semibold text-neutral-100">Generated sources</h2>
              </div>
              <div className="mt-3 grid gap-3 lg:grid-cols-2">
                <SourcePreview title="Anchor source" src={result.anchor_source_url} />
                <SourcePreview title="Item sheet" src={result.sheet_url} />
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
                    <div className="mt-2 grid gap-2">
                      <CropPreview title="Raw slot" src={crop.raw_url} alt={`${crop.label} raw crop`} />
                      <CropPreview title="Keyed trim" src={crop.url} alt={crop.label} checkerboard />
                    </div>
                    <p className="mt-2 font-mono text-[10px] text-neutral-600">[{crop.box.join(", ")}]</p>
                    <p className="mt-1 font-mono text-[10px] text-neutral-600">trim [{crop.trim_box.join(", ")}]</p>
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
                Generate an anchor and item sheet to inspect the raw slots and keyed cutouts.
              </p>
            </div>
          </div>
        )}
      </section>
    </div>
  );
}

function SourcePreview({ title, src }: { title: string; src: string }) {
  return (
    <div className="overflow-hidden rounded-md border border-neutral-800 bg-neutral-950">
      <div className="border-b border-neutral-800 px-3 py-2 text-xs font-medium text-neutral-300">{title}</div>
      <img src={assetUrl(src)} alt={title} className="w-full object-contain" />
    </div>
  );
}

function CropPreview({
  title,
  src,
  alt,
  checkerboard = false,
}: {
  title: string;
  src: string;
  alt: string;
  checkerboard?: boolean;
}) {
  return (
    <div className="overflow-hidden rounded border border-neutral-800 bg-neutral-900">
      <div className="border-b border-neutral-800 px-2 py-1 text-[10px] font-medium uppercase text-neutral-500">{title}</div>
      <div
        className="flex aspect-video items-center justify-center"
        style={checkerboard ? {
          backgroundColor: "#171717",
          backgroundImage:
            "linear-gradient(45deg, #262626 25%, transparent 25%), linear-gradient(-45deg, #262626 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #262626 75%), linear-gradient(-45deg, transparent 75%, #262626 75%)",
          backgroundPosition: "0 0, 0 8px, 8px -8px, -8px 0",
          backgroundSize: "16px 16px",
        } : undefined}
      >
        <img src={assetUrl(src)} alt={alt} className="h-full w-full object-contain" />
      </div>
    </div>
  );
}
