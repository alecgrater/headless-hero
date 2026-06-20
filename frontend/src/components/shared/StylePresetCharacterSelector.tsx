import { ChevronLeft, ChevronRight, Settings } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  assetUrl,
  getActiveStylePreset,
  listStylePresetCharacters,
  listStylePresets,
  selectStylePresetCharacter,
  setActiveStylePreset,
  type StylePreset,
  type StylePresetCharacter,
} from "../../api";
import { useStylePreset } from "../../contexts/StylePresetContext";

type StylePresetCharacterSelectorProps = {
  testId?: string;
  onManage?: () => void;
};

export function StylePresetCharacterSelector({
  testId,
  onManage,
}: StylePresetCharacterSelectorProps) {
  const [presets, setPresets] = useState<StylePreset[]>([]);
  const [activePresetId, setActivePresetId] = useState<string | null>(null);
  const [characters, setCharacters] = useState<StylePresetCharacter[]>([]);
  const [activeCharacterId, setActiveCharacterId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { refresh } = useStylePreset();

  const activePresetIndex = useMemo(() => {
    if (presets.length === 0) return -1;
    const index = presets.findIndex((preset) => preset.id === activePresetId);
    return index >= 0 ? index : 0;
  }, [activePresetId, presets]);

  const activePreset = activePresetIndex >= 0 ? presets[activePresetIndex] : null;

  const activeCharacterIndex = useMemo(() => {
    if (characters.length === 0) return -1;
    const index = characters.findIndex((character) => character.id === activeCharacterId);
    return index >= 0 ? index : 0;
  }, [activeCharacterId, characters]);

  const activeCharacter = activeCharacterIndex >= 0 ? characters[activeCharacterIndex] : null;

  useEffect(() => {
    let cancelled = false;
    Promise.all([listStylePresets(), getActiveStylePreset()])
      .then(([presetList, active]) => {
        if (cancelled) return;
        setPresets(presetList);
        setActivePresetId(active?.id ?? presetList[0]?.id ?? null);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    if (!activePresetId) {
      setCharacters([]);
      setActiveCharacterId(null);
      return;
    }
    listStylePresetCharacters(activePresetId)
      .then((list) => {
        if (cancelled) return;
        setCharacters(list);
        setActiveCharacterId(list.find((character) => character.active)?.id ?? list[0]?.id ?? null);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
          setCharacters([]);
          setActiveCharacterId(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [activePresetId]);

  const activatePreset = useCallback(async (presetId: string) => {
    try {
      setError(null);
      setActivePresetId(presetId);
      await setActiveStylePreset(presetId);
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [refresh]);

  const activateCharacter = useCallback(async (characterId: string) => {
    if (!activePresetId) return;
    try {
      setError(null);
      const selected = await selectStylePresetCharacter(activePresetId, characterId);
      setCharacters((current) => current.map((character) => ({
        ...character,
        active: character.id === selected.id,
      })));
      setActiveCharacterId(selected.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [activePresetId]);

  const cyclePreset = (direction: -1 | 1) => {
    if (presets.length === 0) return;
    const nextIndex = (activePresetIndex + direction + presets.length) % presets.length;
    void activatePreset(presets[nextIndex].id);
  };

  const cycleCharacter = (direction: -1 | 1) => {
    if (characters.length === 0) return;
    const nextIndex = (activeCharacterIndex + direction + characters.length) % characters.length;
    void activateCharacter(characters[nextIndex].id);
  };

  if (loading) {
    return (
      <div data-testid={testId} className="rounded-lg border border-neutral-800 bg-neutral-900/70 px-4 py-3 text-sm text-neutral-500">
        Loading visual references...
      </div>
    );
  }

  if (error) {
    return (
      <div data-testid={testId} className="rounded-lg border border-red-500/30 bg-red-500/10 px-4 py-3 text-sm text-red-300">
        {error}
      </div>
    );
  }

  return (
    <div data-testid={testId} className="grid gap-4 lg:grid-cols-2">
      <ReferencePanel
        title="Style Preset"
        description="Pick the global visual reference for this project."
        emptyTitle="No style presets yet."
        activeName={activePreset?.name ?? null}
        activeBadgeColor="violet"
        imageUrl={activePreset?.image_url ?? null}
        prompt={activePreset?.prompt ?? ""}
        items={presets.map((preset) => ({
          id: preset.id,
          name: preset.name || "Untitled style preset",
          imageUrl: preset.image_url,
          active: preset.id === activePresetId,
        }))}
        onPrevious={() => cyclePreset(-1)}
        onNext={() => cyclePreset(1)}
        onSelect={(id) => void activatePreset(id)}
      />

      <ReferencePanel
        title="Main Character"
        description="Pick the preset-scoped protagonist used when Eli is off."
        emptyTitle={activePreset ? "No characters for this preset yet." : "Select a style preset first."}
        activeName={activeCharacter?.name ?? null}
        activeBadgeColor="emerald"
        imageUrl={activeCharacter?.reference_image_url ?? null}
        cutoutImageUrl={activeCharacter?.cutout_image_url || null}
        prompt={activeCharacter?.appearance ?? ""}
        items={characters.map((character) => ({
          id: character.id,
          name: character.name,
          imageUrl: character.reference_image_url,
          active: character.id === activeCharacterId,
        }))}
        onPrevious={() => cycleCharacter(-1)}
        onNext={() => cycleCharacter(1)}
        onSelect={(id) => void activateCharacter(id)}
      />

      {onManage && (
        <button
          type="button"
          onClick={onManage}
          className="inline-flex w-fit items-center gap-2 rounded-md border border-neutral-800 px-3 py-2 text-xs font-medium text-neutral-300 hover:border-violet-500 hover:text-violet-300 transition-colors lg:col-span-2"
        >
          <Settings className="size-3.5" />
          Manage visual identity
        </button>
      )}
    </div>
  );
}

function ReferencePanel({
  title,
  description,
  emptyTitle,
  activeName,
  activeBadgeColor,
  imageUrl,
  cutoutImageUrl,
  prompt,
  items,
  onPrevious,
  onNext,
  onSelect,
}: {
  title: string;
  description: string;
  emptyTitle: string;
  activeName: string | null;
  activeBadgeColor: "violet" | "emerald";
  imageUrl: string | null;
  cutoutImageUrl?: string | null;
  prompt: string;
  items: Array<{ id: string; name: string; imageUrl: string; active: boolean }>;
  onPrevious: () => void;
  onNext: () => void;
  onSelect: (id: string) => void;
}) {
  const badgeClass = activeBadgeColor === "emerald"
    ? "bg-emerald-500/15 text-emerald-300"
    : "bg-violet-500/20 text-violet-300";
  const dotClass = activeBadgeColor === "emerald" ? "bg-emerald-400" : "bg-violet-400";

  return (
    <section className="rounded-lg border border-neutral-800 bg-neutral-900 p-3">
      <div className="mb-3 rounded-lg border border-violet-500/30 bg-violet-500/5 px-4 py-3">
        <h3 className="text-base font-semibold text-neutral-100">{title}</h3>
        <p className="mt-1 text-xs leading-relaxed text-neutral-500">{description}</p>
      </div>

      <div className="rounded-md border border-neutral-800 bg-neutral-950/50 p-3">
        {imageUrl && activeName ? (
          <div className="space-y-3">
            <div className={cutoutImageUrl ? "grid gap-3 xl:grid-cols-[minmax(0,1fr)_128px]" : ""}>
              <div className="grid grid-cols-[34px_minmax(0,1fr)_34px] items-center gap-2">
                <button
                  type="button"
                  onClick={onPrevious}
                  aria-label={`Previous ${title.toLowerCase()}`}
                  className="flex size-8 items-center justify-center rounded-full border border-neutral-700 bg-neutral-950 text-neutral-300 hover:border-violet-500 hover:text-violet-300 transition-colors"
                >
                  <ChevronLeft className="size-4" />
                </button>
                <img
                  src={assetUrl(imageUrl)}
                  alt={activeName}
                  className="aspect-video max-h-[180px] w-full rounded object-cover"
                />
                <button
                  type="button"
                  onClick={onNext}
                  aria-label={`Next ${title.toLowerCase()}`}
                  className="flex size-8 items-center justify-center rounded-full border border-neutral-700 bg-neutral-950 text-neutral-300 hover:border-violet-500 hover:text-violet-300 transition-colors"
                >
                  <ChevronRight className="size-4" />
                </button>
              </div>

              {cutoutImageUrl && (
                <div
                  className="rounded-md border border-neutral-800 p-2"
                  style={{
                    backgroundColor: "#171717",
                    backgroundImage:
                      "linear-gradient(45deg, #262626 25%, transparent 25%), linear-gradient(-45deg, #262626 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #262626 75%), linear-gradient(-45deg, transparent 75%, #262626 75%)",
                    backgroundPosition: "0 0, 0 8px, 8px -8px, -8px 0",
                    backgroundSize: "16px 16px",
                  }}
                >
                  <p className="mb-1 text-[10px] font-medium uppercase text-neutral-500">Cutout</p>
                  <img
                    src={assetUrl(cutoutImageUrl)}
                    alt={`${activeName} transparent cutout`}
                    className="h-[128px] w-full rounded object-contain"
                  />
                </div>
              )}
            </div>

            <div>
              <div className="flex flex-wrap items-center gap-2">
                <h4 className="text-sm font-semibold text-neutral-100">{activeName}</h4>
                <span className={`rounded px-2 py-0.5 text-xs font-medium ${badgeClass}`}>Active</span>
              </div>
              {prompt && (
                <p className="mt-2 overflow-hidden text-xs leading-relaxed text-neutral-500 [display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:2]">
                  {prompt}
                </p>
              )}
            </div>

            <div className="flex max-h-24 flex-wrap items-center gap-2 overflow-y-auto pr-1">
              {items.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => onSelect(item.id)}
                  aria-label={`View ${item.name}`}
                  className={`relative h-12 w-20 rounded border p-0.5 transition-colors ${
                    item.active
                      ? "border-violet-500 bg-violet-500/10"
                      : "border-neutral-700 bg-neutral-950 hover:border-violet-500/70"
                  }`}
                >
                  <img src={assetUrl(item.imageUrl)} alt="" className="h-full w-full rounded-sm object-cover" />
                  {item.active && (
                    <span className={`absolute bottom-1 right-1 size-2 rounded-full ${dotClass} shadow-[0_0_0_2px_rgba(10,10,10,0.85)]`} />
                  )}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex aspect-video items-center justify-center rounded-md border border-dashed border-neutral-700 px-4 text-center">
            <p className="text-sm text-neutral-500">{emptyTitle}</p>
          </div>
        )}
      </div>
    </section>
  );
}
