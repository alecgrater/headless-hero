import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import {
  assetUrl,
  getGlobalMainCharacter,
  regenerateGlobalMainCharacterReference,
  selectGlobalMainCharacterReference,
  updateGlobalMainCharacter,
  type MainCharacter,
  type MainCharacterConfig,
} from "../../api";

type Props = {
  compact?: boolean;
  onContinue?: () => void;
};

export function MainCharacterSection({ compact = false, onContinue }: Props) {
  const [config, setConfig] = useState<MainCharacterConfig | null>(null);
  const [name, setName] = useState("");
  const [appearance, setAppearance] = useState("");
  const [vibe, setVibe] = useState("");
  const [viewedIdx, setViewedIdx] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [refTs, setRefTs] = useState(() => Date.now());

  const load = async () => {
    const res = await getGlobalMainCharacter();
    if (!res.ok) return;
    setConfig(res.data);
    setName(res.data.main_character?.name ?? "");
    setAppearance(res.data.main_character?.appearance ?? "");
    setVibe(res.data.main_character?.vibe ?? "");
  };

  useEffect(() => {
    load();
  }, []);

  const variants = config?.main_character_reference_variants ?? [];
  const viewedIndex = useMemo(() => {
    if (variants.length === 0) return -1;
    const index = variants.findIndex((variant) => variant.idx === viewedIdx);
    return index >= 0 ? index : 0;
  }, [variants, viewedIdx]);
  const viewedVariant = viewedIndex >= 0 ? variants[viewedIndex] : null;

  useEffect(() => {
    if (variants.length === 0) {
      setViewedIdx(null);
      return;
    }
    if (viewedIdx !== null && variants.some((variant) => variant.idx === viewedIdx)) return;
    setViewedIdx(variants.find((variant) => variant.active)?.idx ?? variants[0].idx);
  }, [variants, viewedIdx]);

  const initial = config?.main_character;
  const dirty =
    name !== (initial?.name ?? "") ||
    appearance !== (initial?.appearance ?? "") ||
    vibe !== (initial?.vibe ?? "");
  const hasCharacterDetails = Boolean(name.trim() && appearance.trim());

  const save = async () => {
    const character: MainCharacter = { name, appearance, vibe };
    setSaving(true);
    const res = await updateGlobalMainCharacter(character);
    setSaving(false);
    if (res.ok) {
      setConfig(res.data);
      setRefTs(Date.now());
    }
  };

  const generate = async () => {
    if (dirty) {
      await save();
    }
    setGenerating(true);
    const res = await regenerateGlobalMainCharacterReference();
    setGenerating(false);
    if (res.ok) {
      setConfig(res.data);
      setViewedIdx(res.data.main_character_reference_variants.find((variant) => variant.active)?.idx ?? null);
      setRefTs(Date.now());
    }
  };

  const selectVariant = async (idx: number) => {
    const res = await selectGlobalMainCharacterReference(idx);
    if (res.ok) {
      setConfig(res.data);
      setViewedIdx(idx);
      setRefTs(Date.now());
    }
  };

  const showPrevious = () => {
    if (variants.length === 0) return;
    setViewedIdx(variants[(viewedIndex - 1 + variants.length) % variants.length].idx);
  };

  const showNext = () => {
    if (variants.length === 0) return;
    setViewedIdx(variants[(viewedIndex + 1) % variants.length].idx);
  };

  return (
    <section className={compact ? "space-y-5" : "space-y-4"}>
      {!compact && (
        <header>
          <h2 className="text-lg font-semibold text-neutral-100">Main Character</h2>
          <p className="text-sm text-neutral-400">
            The global recurring character used when Eli is disabled. Projects sync from this character before generating images.
          </p>
        </header>
      )}

      {onContinue && config?.main_character_reference_url && (
        <div className="flex items-center justify-between gap-3 rounded-md border border-emerald-900/70 bg-emerald-950/20 px-4 py-3">
          <p className="text-sm text-emerald-200">
            This project will use the active global main character.
          </p>
          <button
            type="button"
            onClick={onContinue}
            className="rounded-md bg-emerald-500 px-3 py-2 text-sm font-medium text-neutral-950 hover:bg-emerald-400 transition-colors"
          >
            Continue
          </button>
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="rounded-md border border-neutral-800 bg-neutral-900/60 p-4">
          {viewedVariant ? (
            <div className="grid grid-cols-[44px_minmax(0,1fr)_44px] items-center gap-3">
              <button
                type="button"
                onClick={showPrevious}
                aria-label="Previous main character reference"
                className="flex size-11 items-center justify-center rounded-full border border-neutral-700 bg-neutral-950 text-neutral-300 hover:border-violet-500 hover:text-violet-300 transition-colors"
              >
                <ChevronLeft className="size-6" />
              </button>
              <button
                type="button"
                onClick={() => setViewedIdx(viewedVariant.idx)}
                className={`rounded-md border-2 bg-neutral-950 p-1 transition-colors ${
                  viewedVariant.active ? "border-emerald-400" : "border-neutral-700 hover:border-violet-500"
                }`}
              >
                <img
                  src={`${assetUrl(viewedVariant.image_url)}?t=${refTs}`}
                  alt={`Main character reference ${viewedVariant.idx}`}
                  className="aspect-video w-full rounded object-cover"
                />
              </button>
              <button
                type="button"
                onClick={showNext}
                aria-label="Next main character reference"
                className="flex size-11 items-center justify-center rounded-full border border-neutral-700 bg-neutral-950 text-neutral-300 hover:border-violet-500 hover:text-violet-300 transition-colors"
              >
                <ChevronRight className="size-6" />
              </button>
            </div>
          ) : (
            <div className="flex aspect-video items-center justify-center rounded-md border border-dashed border-neutral-700 text-sm text-neutral-500">
              Generate a reference image to activate the global character
            </div>
          )}

          {viewedVariant && (
            <div className="mt-3 flex items-center justify-between gap-3">
              <span className="text-sm text-neutral-400">
                {viewedVariant.active ? "Active reference" : `Reference ${viewedVariant.idx}`}
              </span>
              {!viewedVariant.active && (
                <button
                  type="button"
                  onClick={() => selectVariant(viewedVariant.idx)}
                  className="rounded-md bg-emerald-500 px-3 py-2 text-sm font-medium text-neutral-950 hover:bg-emerald-400 transition-colors"
                >
                  Set active
                </button>
              )}
            </div>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            {variants.map((variant) => (
              <button
                key={variant.idx}
                type="button"
                onClick={() => setViewedIdx(variant.idx)}
                aria-label={`View main character reference ${variant.idx}`}
                className={`relative h-12 w-20 rounded border p-0.5 transition-colors ${
                  variant.idx === viewedIdx
                    ? "border-violet-500 bg-violet-500/10"
                    : variant.active
                      ? "border-emerald-400 bg-emerald-500/10"
                      : "border-neutral-700 bg-neutral-950 hover:border-violet-500"
                }`}
              >
                <img
                  src={`${assetUrl(variant.image_url)}?t=${refTs}`}
                  alt=""
                  className="h-full w-full rounded-sm object-cover"
                />
                {variant.active && (
                  <span className="absolute bottom-1 right-1 size-2 rounded-full bg-emerald-400 shadow-[0_0_0_2px_rgba(10,10,10,0.85)]" />
                )}
              </button>
            ))}
            <button
              type="button"
              onClick={generate}
              disabled={generating || saving || !hasCharacterDetails}
              className="flex h-12 min-w-28 items-center justify-center gap-1 rounded border-2 border-dashed border-neutral-700 px-3 text-xs font-medium text-neutral-400 hover:border-violet-500 hover:text-violet-300 disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
            >
              <Plus className="size-4" />
              {generating ? "Generating" : "New reference"}
            </button>
          </div>
        </div>

        <div className="rounded-md border border-neutral-800 bg-neutral-900 p-4">
          <div className="space-y-4">
            <label className="block">
              <span className="text-xs font-medium uppercase text-neutral-400">Name</span>
              <input
                type="text"
                value={name}
                onChange={(event) => setName(event.target.value)}
                className="mt-1 w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-100 focus:border-violet-500 focus:outline-none"
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium uppercase text-neutral-400">Appearance</span>
              <textarea
                rows={compact ? 4 : 5}
                value={appearance}
                onChange={(event) => setAppearance(event.target.value)}
                className="mt-1 w-full resize-y rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-100 focus:border-violet-500 focus:outline-none"
              />
            </label>
            <label className="block">
              <span className="text-xs font-medium uppercase text-neutral-400">Vibe</span>
              <textarea
                rows={3}
                value={vibe}
                onChange={(event) => setVibe(event.target.value)}
                className="mt-1 w-full resize-y rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-100 focus:border-violet-500 focus:outline-none"
              />
            </label>
          </div>
          <div className="mt-5 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={save}
              disabled={!dirty || saving || !hasCharacterDetails}
              className="rounded-md bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
            >
              {saving ? "Saving..." : "Save character"}
            </button>
            <button
              type="button"
              onClick={generate}
              disabled={generating || saving || !hasCharacterDetails}
              className="rounded-md border border-neutral-700 px-4 py-2 text-sm font-medium text-neutral-200 hover:border-violet-500 hover:text-violet-300 disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
            >
              {generating ? "Generating..." : "Generate reference"}
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
