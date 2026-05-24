import { Check, Clipboard, Copy, ImageIcon, Loader2, Plus, Scissors, Sparkles, Trash2 } from "lucide-react";
import type { ReactNode } from "react";
import { useMemo, useState } from "react";
import {
  assetUrl,
  bumpAssetVersion,
  chromaPopupCropAnchor,
  chromaPopupCropItemSheet,
  generatePopupCropAnchor,
  generatePopupCropItemSheet,
} from "../../api";
import type { PopupCropPreviewCrop } from "../../types/testLab";

const DEFAULT_ANCHOR_PROMPT = [
  "A stressed recurring office worker character, full body, hands on head, centered and large.",
  "Use the same detailed character style as normal scene protagonists.",
  "No text.",
].join("\n");

const DEFAULT_ITEM_PROMPT = [
  "Item 1 — Overflowing inbox (overflowing_inbox):",
  "A paper tray stacked with teetering documents about to topple over.",
  "Flat 2D cartoon, bold outlines.",
  "Item 2 — Broken coffee mug (broken_coffee_mug):",
  "A coffee mug split in two with liquid spilling out.",
  "Flat 2D cartoon, bold outlines.",
  "Item 3 — Ringing phone (ringing_phone):",
  "A desk phone with curved motion lines on both sides indicating loud ringing.",
  "Flat 2D cartoon, bold outlines.",
].join("\n");

const DEFAULT_ITEMS = ["overflowing_inbox", "broken_coffee_mug", "ringing_phone"];
const MAX_ITEMS = 5;

const ITEM_IDEA_PROMPT = [
  "Generate exactly 3 popup item cutouts for an educational YouTube video scene.",
  "",
  "Pick 3 visually distinct, universally recognizable everyday objects of your choice.",
  "",
  "For each item provide:",
  "- A human-readable name (e.g. \"Overflowing inbox\")",
  "- A snake_case ID (e.g. `overflowing_inbox`)",
  "- A 1-2 sentence image generation description: simple, concrete, ",
  "  visual. End each with \"Flat 2D cartoon, bold outlines.\"",
  "",
  "Format each item exactly like this:",
  "",
  "Item 1 — Human readable name (`snake_case_id`):",
  "A description of the item.",
  "Flat 2D cartoon, bold outlines.",
  "",
  "Item 2 — Human readable name (`snake_case_id`):",
  "A description of the item.",
  "Flat 2D cartoon, bold outlines.",
  "",
  "Item 3 — Human readable name (`snake_case_id`):",
  "A description of the item.",
  "Flat 2D cartoon, bold outlines.",
  "",
  "Do not repeat any item label. Each item appears exactly once.",
  "Use backticks around the snake_case_id.",
  "Output only the 3 items. No preamble, no explanation, no extra text.",
].join("\n");

type BusyAction = "anchor-generate" | "anchor-chroma" | "items-generate" | "items-chroma" | null;

export default function PopupCropLab() {
  const [runId, setRunId] = useState<string | null>(null);
  const [anchorPrompt, setAnchorPrompt] = useState(DEFAULT_ANCHOR_PROMPT);
  const [itemPrompt, setItemPrompt] = useState(DEFAULT_ITEM_PROMPT);
  const [items, setItems] = useState(DEFAULT_ITEMS);
  const [anchorSourceUrl, setAnchorSourceUrl] = useState("");
  const [itemSheetUrl, setItemSheetUrl] = useState("");
  const [generatedItemLabels, setGeneratedItemLabels] = useState<string[]>([]);
  const [anchorCrop, setAnchorCrop] = useState<PopupCropPreviewCrop | null>(null);
  const [itemCrops, setItemCrops] = useState<PopupCropPreviewCrop[]>([]);
  const [busyAction, setBusyAction] = useState<BusyAction>(null);
  const [error, setError] = useState("");
  const [itemPromptHelpOpen, setItemPromptHelpOpen] = useState(false);
  const [itemPromptCopied, setItemPromptCopied] = useState(false);
  const [, setAssetRefreshTick] = useState(0);

  const cleanedItems = useMemo(() => items.map((item) => item.trim()).filter(Boolean), [items]);
  const itemSheetMatchesItems =
    itemSheetUrl &&
    generatedItemLabels.length === cleanedItems.length &&
    generatedItemLabels.every((label, index) => label === cleanedItems[index]);
  const busy = busyAction !== null;

  async function handleGenerateAnchor() {
    if (!anchorPrompt.trim() || busy) return;
    await runAction("anchor-generate", async () => {
      const next = await generatePopupCropAnchor(anchorPrompt.trim(), runId);
      if (!next) {
        setError("The character source could not be generated.");
        return;
      }
      setRunId(next.run_id);
      refreshAssets(next.anchor_source_url, next.anchor_cutout_url ?? "");
      setAnchorSourceUrl(next.anchor_source_url);
      setAnchorCrop(
        next.anchor_cutout_url
          ? {
              role: "anchor",
              label: "Anchor character",
              url: next.anchor_cutout_url,
              raw_url: next.anchor_source_url,
              box: [],
              trim_box: [],
              warnings: next.warnings ?? [],
            }
          : null,
      );
    });
  }

  async function handleChromaAnchor() {
    if (!runId || !anchorSourceUrl || busy) return;
    await runAction("anchor-chroma", async () => {
      const next = await chromaPopupCropAnchor(runId);
      if (!next) {
        setError("The character chroma pass could not be generated.");
        return;
      }
      refreshAssets(...next.crops.flatMap((crop) => [crop.raw_url, crop.url]));
      setAnchorCrop(next.crops[0] ?? null);
    });
  }

  async function handleGenerateItems() {
    if (!itemPrompt.trim() || cleanedItems.length === 0 || busy) return;
    await runAction("items-generate", async () => {
      const next = await generatePopupCropItemSheet(itemPrompt.trim(), cleanedItems, runId);
      if (!next) {
        setError("The item sheet could not be generated.");
        return;
      }
      setRunId(next.run_id);
      refreshAssets(next.sheet_url);
      setItemSheetUrl(next.sheet_url);
      setGeneratedItemLabels(cleanedItems);
      setItemCrops([]);
    });
  }

  async function handleChromaItems() {
    if (!runId || !itemSheetUrl || generatedItemLabels.length === 0 || !itemSheetMatchesItems || busy) return;
    await runAction("items-chroma", async () => {
      const next = await chromaPopupCropItemSheet(runId, generatedItemLabels);
      if (!next) {
        setError("The item chroma pass could not be generated.");
        return;
      }
      refreshAssets(...next.crops.flatMap((crop) => [crop.raw_url, crop.url]));
      setItemCrops(next.crops);
    });
  }

  function refreshAssets(...paths: string[]) {
    bumpAssetVersion(...paths);
    setAssetRefreshTick((current) => current + 1);
  }

  async function runAction(action: BusyAction, fn: () => Promise<void>) {
    setBusyAction(action);
    setError("");
    try {
      await fn();
    } finally {
      setBusyAction(null);
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

  async function handleCopyItemIdeaPrompt() {
    try {
      await navigator.clipboard.writeText(ITEM_IDEA_PROMPT);
      setItemPromptCopied(true);
      window.setTimeout(() => setItemPromptCopied(false), 1600);
    } catch {
      setError("The prompt could not be copied to the clipboard.");
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-4 overflow-y-auto">
      <section className="shrink-0 rounded-lg border border-neutral-800 bg-neutral-900/60 p-4">
        <header>
          <p className="text-xs font-semibold uppercase text-neutral-500">Popup Crop Lab</p>
          <h2 className="mt-2 text-sm font-semibold text-neutral-100">Character and item sheet</h2>
          <p className="mt-1 text-xs leading-5 text-neutral-500">
            Generate each source first, then run chroma when you want to inspect the cleaned transparent cutouts.
          </p>
        </header>
        {error && (
          <div className="mt-4 rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs leading-5 text-red-200">
            {error}
          </div>
        )}
      </section>

      <LabPanel
        title="Character"
        description="Generate and chroma-key the anchored scene character separately from the popup items."
        controls={
          <>
          <label className="block">
            <span className="text-xs font-medium text-neutral-300">Character prompt</span>
            <textarea
              value={anchorPrompt}
              onChange={(event) => setAnchorPrompt(event.target.value)}
              rows={5}
              className="mt-2 w-full resize-y rounded-md border border-neutral-800 bg-neutral-950/80 px-3 py-2 text-sm leading-6 text-neutral-100 outline-none transition-colors placeholder:text-neutral-600 hover:border-neutral-700 focus:border-violet-500"
              placeholder="Describe the recurring character pose for this scene."
            />
          </label>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <ActionButton
              label="Generate Character"
              icon={<Sparkles className="h-4 w-4" />}
              busy={busyAction === "anchor-generate"}
              disabled={!anchorPrompt.trim() || busy}
              onClick={handleGenerateAnchor}
            />
            <ActionButton
              label="Chroma Character"
              icon={<Scissors className="h-4 w-4" />}
              busy={busyAction === "anchor-chroma"}
              disabled={!runId || !anchorSourceUrl || busy}
              onClick={handleChromaAnchor}
            />
          </div>
          </>
        }
        preview={
          <OutputGrid>
            {anchorSourceUrl ? <SourcePreview title="Character source" src={anchorSourceUrl} /> : <EmptyPreview label="No character source yet" />}
            {anchorCrop ? <CropCard crop={anchorCrop} /> : <EmptyPreview label="No character chroma yet" />}
          </OutputGrid>
        }
      />

      <LabPanel
        title="Item"
        titleAction={
          <ItemPromptHelper
            open={itemPromptHelpOpen}
            copied={itemPromptCopied}
            onToggle={() => setItemPromptHelpOpen((current) => !current)}
            onCopy={handleCopyItemIdeaPrompt}
          />
        }
        description="Generate the items in UI order, then chroma-key the sheet into individual cutouts."
        controls={
          <>
          <label className="block">
            <span className="text-xs font-medium text-neutral-300">Item sheet prompt</span>
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

          <div className="mt-3 grid grid-cols-2 gap-2">
            <ActionButton
              label="Generate Sheet"
              icon={<ImageIcon className="h-4 w-4" />}
              busy={busyAction === "items-generate"}
              disabled={!itemPrompt.trim() || cleanedItems.length === 0 || busy}
              onClick={handleGenerateItems}
            />
            <ActionButton
              label="Chroma Items"
              icon={<Scissors className="h-4 w-4" />}
              busy={busyAction === "items-chroma"}
              disabled={!runId || !itemSheetUrl || !itemSheetMatchesItems || busy}
              onClick={handleChromaItems}
            />
          </div>
          {itemSheetUrl && !itemSheetMatchesItems && (
            <p className="mt-2 text-xs leading-5 text-amber-300">
              Regenerate the item sheet after changing the item list so crops stay mapped left to right.
            </p>
          )}
          </>
        }
        preview={
          <OutputGrid>
            {itemSheetUrl ? <SourcePreview title="Item sheet" src={itemSheetUrl} /> : <EmptyPreview label="No item sheet yet" />}
            {itemCrops.length > 0 ? (
              itemCrops.map((crop) => <CropCard key={`${crop.role}-${crop.label}`} crop={crop} />)
            ) : (
              <EmptyPreview label="No item chroma yet" />
            )}
          </OutputGrid>
        }
      />
    </div>
  );
}

function LabPanel({
  title,
  titleAction,
  description,
  controls,
  preview,
}: {
  title: string;
  titleAction?: ReactNode;
  description: string;
  controls: ReactNode;
  preview: ReactNode;
}) {
  return (
    <section className="grid min-h-[420px] shrink-0 grid-cols-1 overflow-hidden rounded-lg border border-neutral-800 bg-neutral-900/60 xl:grid-cols-[440px_minmax(520px,1fr)]">
      <div className="border-b border-neutral-800 p-4 xl:border-b-0 xl:border-r">
        <div className="mb-4">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-neutral-100">{title}</h3>
            {titleAction}
          </div>
          <p className="mt-1 text-xs leading-5 text-neutral-500">{description}</p>
        </div>
        {controls}
      </div>
      <div className="min-h-0 p-4">{preview}</div>
    </section>
  );
}

function ItemPromptHelper({
  open,
  copied,
  onToggle,
  onCopy,
}: {
  open: boolean;
  copied: boolean;
  onToggle: () => void;
  onCopy: () => void;
}) {
  return (
    <div className="relative">
      <button
        type="button"
        onClick={onToggle}
        className={`inline-flex h-7 w-7 items-center justify-center rounded-md border border-neutral-800 bg-neutral-950/80 text-neutral-400 transition-colors hover:border-violet-500/70 hover:text-violet-200 ${
          open ? "border-violet-500/70 bg-violet-500/15 text-violet-200" : ""
        }`}
        title="Show item prompt helper"
      >
        <Clipboard className={`h-3.5 w-3.5 transition-transform duration-300 ${open ? "-rotate-6 scale-110" : ""}`} />
      </button>
      <div
        className={`absolute left-0 top-9 z-20 w-[min(22rem,calc(100vw-3rem))] rounded-lg border border-violet-500/30 bg-neutral-950/95 p-3 shadow-2xl shadow-violet-950/30 backdrop-blur transition-all duration-300 ${
          open
            ? "pointer-events-auto translate-y-0 scale-100 opacity-100"
            : "pointer-events-none -translate-y-2 scale-95 opacity-0"
        }`}
      >
        <div className="flex items-center justify-between gap-3">
          <h4 className="text-xs font-semibold text-neutral-100">Prompt:</h4>
          <button
            type="button"
            onClick={onCopy}
            className="inline-flex h-8 items-center justify-center gap-1.5 rounded-md border border-neutral-800 bg-neutral-900 px-2 text-xs font-medium text-neutral-200 transition-colors hover:border-violet-500/70 hover:text-violet-100"
          >
            {copied ? <Check className="h-3.5 w-3.5 text-emerald-300" /> : <Copy className="h-3.5 w-3.5" />}
            <span>{copied ? "Copied" : "Copy"}</span>
          </button>
        </div>
        <pre className="mt-3 max-h-80 overflow-y-auto whitespace-pre-wrap rounded-md border border-neutral-800 bg-neutral-900/80 p-3 text-[11px] leading-5 text-neutral-300">
          {ITEM_IDEA_PROMPT}
        </pre>
      </div>
    </div>
  );
}

function ActionButton({
  label,
  icon,
  busy,
  disabled,
  onClick,
}: {
  label: string;
  icon: ReactNode;
  busy: boolean;
  disabled: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-violet-600 px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-violet-500 disabled:cursor-not-allowed disabled:bg-neutral-800 disabled:text-neutral-500"
    >
      {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : icon}
      <span>{label}</span>
    </button>
  );
}

function OutputGrid({ children }: { children: ReactNode }) {
  return (
    <div className="grid h-full content-start gap-3 md:grid-cols-2 2xl:grid-cols-3">{children}</div>
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

function CropCard({ crop }: { crop: PopupCropPreviewCrop }) {
  return (
    <div className="rounded-md border border-neutral-800 bg-neutral-950/70 p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="truncate text-xs font-medium text-neutral-200">{crop.label}</p>
        <span className="shrink-0 rounded border border-neutral-800 px-1.5 py-0.5 text-[10px] uppercase text-neutral-500">
          {crop.role}
        </span>
      </div>
      <div className="mt-2 grid gap-2">
        <CropPreview title="Raw fixed crop" src={crop.raw_url} alt={`${crop.label} raw crop`} />
        <CropPreview title="Chroma + auto-trim" src={crop.url} alt={crop.label} checkerboard />
      </div>
      {crop.box.length > 0 && (
        <p className="mt-2 font-mono text-[10px] text-neutral-600">[{crop.box.join(", ")}]</p>
      )}
      {crop.trim_box.length > 0 && (
        <p className="mt-1 font-mono text-[10px] text-neutral-600">trim [{crop.trim_box.join(", ")}]</p>
      )}
      {crop.warnings && crop.warnings.length > 0 && (
        <div className="mt-2 rounded border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-[11px] text-amber-200">
          {crop.warnings.join(", ")}
        </div>
      )}
    </div>
  );
}

function EmptyPreview({ label }: { label: string }) {
  return (
    <div className="flex min-h-32 items-center justify-center rounded-md border border-dashed border-neutral-800 bg-neutral-950/40 text-xs text-neutral-600">
      {label}
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
