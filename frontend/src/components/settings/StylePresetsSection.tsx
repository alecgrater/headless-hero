import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp, Plus } from "lucide-react";
import { useCallback, useEffect, useId, useMemo, useState } from "react";
import api, {
  assetUrl,
  createStylePresetCharacter,
  deleteStylePreset,
  getActiveStylePreset,
  listStylePresetCharacters,
  listStylePresets,
  selectStylePresetCharacter,
  setActiveStylePreset,
  type StylePreset,
  type StylePresetCharacter,
} from "../../api";
import { useStylePreset } from "../../contexts/StylePresetContext";
import { showToast } from "../ToastContainer";
import { StylePresetToggle } from "../shared/StylePresetToggle";
import SettingsSectionHeader from "./SettingsSectionHeader";
import { StylePresetCreateModal } from "./StylePresetCreateModal";
import { useDebouncedAutosave } from "./useDebouncedAutosave";

const DISABLED_SETTING_VALUES = new Set(["", "0", "false", "no", "off"]);

function settingEnabled(val: string): boolean {
  return !DISABLED_SETTING_VALUES.has(val.trim().toLowerCase());
}

type Props = {
  compact?: boolean;
  showDefaults?: boolean;
  showHeader?: boolean;
  onContinue?: () => void;
};

function ExpandablePrompt({ text }: { text: string }) {
  const [expanded, setExpanded] = useState(false);
  const promptId = useId();
  const trimmedText = text.trim();

  if (!trimmedText) {
    return <p className="mt-1 text-sm text-neutral-500">No prompt saved.</p>;
  }

  return (
    <div className="mt-1 max-w-2xl">
      <p
        id={promptId}
        title={trimmedText}
        className={`text-sm leading-5 text-neutral-400 ${
          expanded
            ? "whitespace-pre-wrap break-words"
            : "overflow-hidden [display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:2]"
        }`}
      >
        {trimmedText}
      </p>
      <button
        type="button"
        aria-controls={promptId}
        aria-expanded={expanded}
        onClick={() => setExpanded((current) => !current)}
        className="mt-2 inline-flex items-center gap-1 rounded-md px-0 py-1 text-xs font-medium text-violet-300 hover:text-violet-200 transition-colors"
      >
        {expanded ? (
          <>
            <ChevronUp className="size-3.5" />
            Collapse prompt
          </>
        ) : (
          <>
            <ChevronDown className="size-3.5" />
            Show full prompt
          </>
        )}
      </button>
    </div>
  );
}

function StylePresetCharacterCreateModal({
  preset,
  onClose,
  onCreated,
}: {
  preset: StylePreset;
  onClose: () => void;
  onCreated: (character: StylePresetCharacter) => void;
}) {
  const [name, setName] = useState("");
  const [appearance, setAppearance] = useState("");
  const [vibe, setVibe] = useState("");
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const hasCharacterDetails = Boolean(name.trim() && appearance.trim());

  const handleGenerate = async () => {
    if (!hasCharacterDetails) {
      setError("Name and appearance are required.");
      return;
    }
    setError(null);
    setGenerating(true);
    try {
      const created = await createStylePresetCharacter(preset.id, {
        name: name.trim(),
        appearance: appearance.trim(),
        vibe: vibe.trim(),
      });
      onCreated(created);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="w-full max-w-2xl rounded-lg border border-neutral-800 bg-neutral-950 p-6 shadow-xl">
        <h2 className="text-lg font-semibold text-neutral-100">New main character</h2>
        <p className="mt-1 text-sm text-neutral-400">
          Generate a character reference in the style of {preset.name || "this preset"}.
        </p>

        <div className="mt-5 space-y-4">
          <label className="block">
            <span className="text-xs font-medium uppercase text-neutral-400">Name</span>
            <input
              type="text"
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="e.g. Maya"
              className="mt-1 w-full rounded-md border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 placeholder-neutral-500 focus:border-violet-500 focus:outline-none"
            />
          </label>
          <label className="block">
            <span className="text-xs font-medium uppercase text-neutral-400">Appearance</span>
            <textarea
              rows={5}
              value={appearance}
              onChange={(event) => setAppearance(event.target.value)}
              placeholder="Distinctive clothing, body language, age, silhouette..."
              className="mt-1 w-full resize-y rounded-md border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 placeholder-neutral-500 focus:border-violet-500 focus:outline-none"
            />
          </label>
          <label className="block">
            <span className="text-xs font-medium uppercase text-neutral-400">Vibe</span>
            <textarea
              rows={3}
              value={vibe}
              onChange={(event) => setVibe(event.target.value)}
              placeholder="Energetic, dry, curious..."
              className="mt-1 w-full resize-y rounded-md border border-neutral-800 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 placeholder-neutral-500 focus:border-violet-500 focus:outline-none"
            />
          </label>
        </div>

        {error && <div className="mt-4 text-sm text-red-400">{error}</div>}

        <div className="mt-6 flex justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-neutral-700 px-4 py-2 text-sm text-neutral-300 hover:bg-neutral-800 transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleGenerate}
            disabled={generating || !hasCharacterDetails}
            className="rounded bg-violet-600 px-4 py-2 text-sm text-white hover:bg-violet-500 disabled:opacity-50 transition-colors"
          >
            {generating ? "Generating..." : "Generate"}
          </button>
        </div>
      </div>
    </div>
  );
}

export function StylePresetsSection({ compact = false, showDefaults = true, showHeader = true, onContinue }: Props) {
  const [presets, setPresets] = useState<StylePreset[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [viewedId, setViewedId] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [showCharacterModal, setShowCharacterModal] = useState(false);
  const [characters, setCharacters] = useState<StylePresetCharacter[]>([]);
  const [viewedCharacterId, setViewedCharacterId] = useState<string | null>(null);
  const [characterRefTs, setCharacterRefTs] = useState(() => Date.now());
  const [eliEnabledDefault, setEliEnabledDefault] = useState("false");
  const [stylePresetEnabledDefault, setStylePresetEnabledDefault] = useState("true");
  const [originalEliEnabledDefault, setOriginalEliEnabledDefault] = useState("false");
  const [originalStylePresetEnabledDefault, setOriginalStylePresetEnabledDefault] = useState("true");
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const { refresh: refreshActive } = useStylePreset();

  const loadAll = async () => {
    const [list, active, settings] = await Promise.all([
      listStylePresets(),
      getActiveStylePreset(),
      api.get("/api/settings/keys"),
    ]);
    setPresets(list);
    setActiveId(active?.id ?? null);
    if (settings.ok) {
      const data = settings.data as Record<string, { masked: string }>;
      const eliVal = settingEnabled(data.ELI_ENABLED_DEFAULT?.masked || "false") ? "true" : "false";
      const styleVal = settingEnabled(data.STYLE_PRESET_ENABLED_DEFAULT?.masked || "true") ? "true" : "false";
      setEliEnabledDefault(eliVal);
      setOriginalEliEnabledDefault(eliVal);
      setStylePresetEnabledDefault(styleVal);
      setOriginalStylePresetEnabledDefault(styleVal);
    }
  };

  const loadCharacters = async (
    presetId: string | null,
    apply: (list: StylePresetCharacter[]) => void,
  ) => {
    if (!presetId) {
      apply([]);
      return;
    }
    const list = await listStylePresetCharacters(presetId);
    apply(list);
  };

  const applyCharacterList = (list: StylePresetCharacter[]) => {
    setCharacters(list);
    setViewedCharacterId((current) => {
      if (current && list.some((character) => character.id === current)) return current;
      return list.find((character) => character.active)?.id ?? list[0]?.id ?? null;
    });
    setCharacterRefTs(Date.now());
  };

  useEffect(() => {
    let cancelled = false;
    loadAll()
      .catch((err) => {
        console.error("Failed to load style preset settings", err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSetActive = async (id: string | null) => {
    await setActiveStylePreset(id);
    setActiveId(id);
    if (id) setViewedId(id);
    await refreshActive();
  };

  const handleDelete = async (id: string) => {
    const currentIndex = presets.findIndex((p) => p.id === id);
    const nextPreset = presets[currentIndex + 1] ?? presets[currentIndex - 1] ?? null;
    await deleteStylePreset(id);
    if (activeId === id) {
      setActiveId(null);
      await refreshActive();
    }
    setViewedId(nextPreset?.id ?? null);
    await loadAll();
  };

  const viewedIndex = useMemo(() => {
    if (presets.length === 0) return -1;
    const index = presets.findIndex((p) => p.id === viewedId);
    return index >= 0 ? index : 0;
  }, [presets, viewedId]);

  const viewedPreset = viewedIndex >= 0 ? presets[viewedIndex] : null;
  const activePreset = presets.find((preset) => preset.id === activeId) ?? null;
  const hasChanges =
    eliEnabledDefault !== originalEliEnabledDefault ||
    stylePresetEnabledDefault !== originalStylePresetEnabledDefault;

  useEffect(() => {
    if (presets.length === 0) {
      setViewedId(null);
      return;
    }
    if (viewedId && presets.some((p) => p.id === viewedId)) return;
    setViewedId(activeId ?? presets[0].id);
  }, [activeId, presets, viewedId]);

  useEffect(() => {
    let cancelled = false;
    loadCharacters(viewedPreset?.id ?? null, (list) => {
      if (!cancelled) applyCharacterList(list);
    }).catch((err) => {
      if (!cancelled) {
        console.error("Failed to load preset characters", err);
        applyCharacterList([]);
      }
    });
    return () => {
      cancelled = true;
    };
  }, [viewedPreset?.id]);

  const viewedCharacterIndex = useMemo(() => {
    if (characters.length === 0) return -1;
    const index = characters.findIndex((character) => character.id === viewedCharacterId);
    return index >= 0 ? index : 0;
  }, [characters, viewedCharacterId]);

  const viewedCharacter = viewedCharacterIndex >= 0 ? characters[viewedCharacterIndex] : null;
  const activeCharacterReady = Boolean(
    activeId &&
      viewedPreset?.id === activeId &&
      characters.some((character) => character.active),
  );

  const showPreviousPreset = () => {
    if (presets.length === 0) return;
    const nextIndex = (viewedIndex - 1 + presets.length) % presets.length;
    setViewedId(presets[nextIndex].id);
  };

  const showNextPreset = () => {
    if (presets.length === 0) return;
    const nextIndex = (viewedIndex + 1) % presets.length;
    setViewedId(presets[nextIndex].id);
  };

  const showPreviousCharacter = () => {
    if (characters.length === 0) return;
    const nextIndex = (viewedCharacterIndex - 1 + characters.length) % characters.length;
    setViewedCharacterId(characters[nextIndex].id);
  };

  const showNextCharacter = () => {
    if (characters.length === 0) return;
    const nextIndex = (viewedCharacterIndex + 1) % characters.length;
    setViewedCharacterId(characters[nextIndex].id);
  };

  const handleSelectCharacter = async (characterId: string) => {
    if (!viewedPreset) return;
    const selected = await selectStylePresetCharacter(viewedPreset.id, characterId);
    setCharacters((current) => current.map((character) => ({
      ...character,
      active: character.id === selected.id,
    })));
    setViewedCharacterId(selected.id);
    setCharacterRefTs(Date.now());
  };

  const handleCharacterCreated = (created: StylePresetCharacter) => {
    setCharacters((current) => [
      created,
      ...current.map((character) => ({ ...character, active: false })),
    ]);
    setViewedCharacterId(created.id);
    setCharacterRefTs(Date.now());
  };

  const handleSaveDefaults = useCallback(async () => {
    setSaving(true);
    const res = await api.put("/api/settings/keys", {
      ELI_ENABLED_DEFAULT: eliEnabledDefault,
      STYLE_PRESET_ENABLED_DEFAULT: stylePresetEnabledDefault,
    });
    setSaving(false);
    if (res.ok) {
      showToast("Brand defaults saved", "success");
      setOriginalEliEnabledDefault(eliEnabledDefault);
      setOriginalStylePresetEnabledDefault(stylePresetEnabledDefault);
    }
    return res.ok;
  }, [eliEnabledDefault, stylePresetEnabledDefault]);

  useDebouncedAutosave(showDefaults && hasChanges && !saving && !loading, handleSaveDefaults, [
    eliEnabledDefault,
    stylePresetEnabledDefault,
  ]);

  if (loading) {
    return <p className="text-sm text-neutral-500">Loading...</p>;
  }

  return (
    <section className={`${compact ? "space-y-4 pb-8" : "space-y-4 pb-20"}`}>
      {!compact && showHeader && (
        <header>
          <h2 className="text-lg font-semibold text-neutral-100">Brand & Style</h2>
          <p className="text-sm text-neutral-400">
            Set the visual style, recurring character, and defaults for new projects.
          </p>
        </header>
      )}

      <div
        data-testid="brand-style-workspace"
        className="grid gap-4 lg:grid-cols-2"
      >
        <div className="flex flex-col gap-3">
          <SettingsSectionHeader
            title="Style Presets"
            description="Global visual references used when Eli is disabled."
          />

          <div className="flex-1 space-y-3 rounded-lg border border-neutral-800 bg-neutral-900 p-3">
            {viewedPreset ? (
              <div className="rounded-md border border-neutral-800 bg-neutral-950/50 p-3">
                <div className="space-y-3">
                  <div className="grid grid-cols-[34px_minmax(0,1fr)_34px] items-center gap-2">
                    <button
                      type="button"
                      onClick={showPreviousPreset}
                      aria-label="Previous style preset"
                      className="flex size-8 items-center justify-center rounded-full border border-neutral-700 bg-neutral-950 text-neutral-300 hover:border-violet-500 hover:text-violet-300 transition-colors"
                    >
                      <ChevronLeft className="size-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => setViewedId(viewedPreset.id)}
                      className={`rounded-md border-2 bg-neutral-950 p-1 transition-colors ${
                        viewedPreset.id === activeId
                          ? "border-violet-500 shadow-[0_0_0_1px_rgba(139,92,246,0.45)]"
                          : "border-neutral-700 hover:border-violet-500/70"
                      }`}
                    >
                      <img
                        data-testid="style-preset-preview"
                        src={assetUrl(viewedPreset.image_url)}
                        alt={viewedPreset.name || "Untitled style preset"}
                        className="aspect-video max-h-[220px] w-full rounded object-cover"
                      />
                    </button>
                    <button
                      type="button"
                      onClick={showNextPreset}
                      aria-label="Next style preset"
                      className="flex size-8 items-center justify-center rounded-full border border-neutral-700 bg-neutral-950 text-neutral-300 hover:border-violet-500 hover:text-violet-300 transition-colors"
                    >
                      <ChevronRight className="size-4" />
                    </button>
                  </div>

                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex max-w-full items-center gap-2">
                        <h3 className="truncate text-sm font-medium text-neutral-100">
                          {viewedPreset.name || "Untitled"}
                        </h3>
                        {viewedPreset.id === activeId && (
                          <span className="shrink-0 rounded bg-violet-500/20 px-2 py-0.5 text-xs font-medium text-violet-300">
                            Active
                          </span>
                        )}
                      </div>
                      <ExpandablePrompt text={viewedPreset.prompt} />
                    </div>
                    <div className="flex shrink-0 flex-wrap gap-2">
                      {viewedPreset.id !== activeId && (
                        <button
                          type="button"
                          onClick={() => handleSetActive(viewedPreset.id)}
                          className="rounded-md bg-violet-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-violet-500 transition-colors"
                        >
                          Set active
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => handleDelete(viewedPreset.id)}
                        className="rounded-md border border-red-900 px-3 py-1.5 text-xs font-medium text-red-400 hover:bg-red-950 transition-colors"
                      >
                        Delete
                      </button>
                    </div>
                  </div>

                  <div className="flex max-h-28 flex-wrap items-center gap-2 overflow-y-auto pr-1">
                    {presets.map((p) => (
                      <button
                        key={p.id}
                        type="button"
                        onClick={() => setViewedId(p.id)}
                        aria-label={`View ${p.name || "Untitled"} style preset`}
                        className={`relative h-10 w-16 rounded border p-0.5 transition-colors ${
                          p.id === viewedPreset.id
                            ? "border-violet-500 bg-violet-500/10"
                            : p.id === activeId
                              ? "border-violet-400 bg-violet-500/5"
                              : "border-neutral-700 bg-neutral-950 hover:border-violet-500/70"
                        }`}
                      >
                        <img src={assetUrl(p.image_url)} alt="" className="h-full w-full rounded-sm object-cover" />
                        {p.id === activeId && (
                          <span className="absolute bottom-1 right-1 size-2 rounded-full bg-violet-400 shadow-[0_0_0_2px_rgba(10,10,10,0.85)]" />
                        )}
                      </button>
                    ))}
                    <button
                      type="button"
                      onClick={() => setShowModal(true)}
                      className="flex h-10 min-w-20 items-center justify-center gap-1 rounded border-2 border-dashed border-neutral-700 px-2 text-xs font-medium text-neutral-400 hover:border-violet-500 hover:text-violet-300 transition-colors"
                    >
                      <Plus className="size-4" />
                      New
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex aspect-video flex-col items-center justify-center rounded-md border border-dashed border-neutral-700 text-center">
                <p className="text-sm text-neutral-400">No style presets yet.</p>
                <button
                  type="button"
                  onClick={() => setShowModal(true)}
                  className="mt-4 flex items-center gap-2 rounded-lg border-2 border-dashed border-neutral-700 px-5 py-3 text-sm font-medium text-neutral-300 hover:border-violet-500 hover:text-violet-300 transition-colors"
                >
                  <Plus className="size-4" />
                  New preset
                </button>
              </div>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-3">
          <SettingsSectionHeader
            title="Main Character"
            description="Characters are scoped to the viewed style preset and inherit its visual style."
          />

          <div className="flex-1 space-y-3 rounded-lg border border-neutral-800 bg-neutral-900 p-3">
            {viewedPreset ? (
              <>
                <div className="rounded-md border border-neutral-800 bg-neutral-950/50 p-3">
                  {viewedCharacter ? (
                    <div className="space-y-3">
                      <div className={viewedCharacter.cutout_image_url ? "grid gap-3 lg:grid-cols-[minmax(0,1fr)_140px]" : ""}>
                        <div className="grid grid-cols-[34px_minmax(0,1fr)_34px] items-center gap-2">
                          <button
                            type="button"
                            onClick={showPreviousCharacter}
                            aria-label="Previous character reference"
                            className="flex size-8 items-center justify-center rounded-full border border-neutral-700 bg-neutral-950 text-neutral-300 hover:border-violet-500 hover:text-violet-300 transition-colors"
                          >
                            <ChevronLeft className="size-4" />
                          </button>
                          <img
                            data-testid="main-character-preview"
                            src={`${assetUrl(viewedCharacter.reference_image_url)}?t=${characterRefTs}`}
                            alt={viewedCharacter.name}
                            className="aspect-video max-h-[220px] w-full rounded object-cover"
                          />
                          <button
                            type="button"
                            onClick={showNextCharacter}
                            aria-label="Next character reference"
                            className="flex size-8 items-center justify-center rounded-full border border-neutral-700 bg-neutral-950 text-neutral-300 hover:border-violet-500 hover:text-violet-300 transition-colors"
                          >
                            <ChevronRight className="size-4" />
                          </button>
                        </div>
                        {viewedCharacter.cutout_image_url && (
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
                              src={`${assetUrl(viewedCharacter.cutout_image_url)}?t=${characterRefTs}`}
                              alt={`${viewedCharacter.name} transparent cutout`}
                              className="h-[156px] w-full rounded object-contain"
                            />
                          </div>
                        )}
                      </div>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex max-w-full items-center gap-2">
                          <h3 className="truncate text-sm font-medium text-neutral-100">{viewedCharacter.name}</h3>
                          {viewedCharacter.active && (
                            <span className="shrink-0 rounded bg-emerald-500/15 px-2 py-0.5 text-xs font-medium text-emerald-300">
                              Active
                            </span>
                          )}
                        </div>
                        <ExpandablePrompt text={viewedCharacter.appearance} />
                      </div>
                      {!viewedCharacter.active && (
                        <button
                          type="button"
                          onClick={() => handleSelectCharacter(viewedCharacter.id)}
                          className="shrink-0 rounded-md bg-emerald-500 px-3 py-1.5 text-xs font-medium text-neutral-950 hover:bg-emerald-400 transition-colors"
                        >
                          Set active
                        </button>
                      )}
                    </div>
                    <div className="flex max-h-28 flex-wrap items-center gap-2 overflow-y-auto pr-1">
                      {characters.map((character) => (
                        <button
                          key={character.id}
                          type="button"
                          onClick={() => setViewedCharacterId(character.id)}
                          aria-label={`View ${character.name}`}
                          className={`relative h-10 w-16 rounded border p-0.5 transition-colors ${
                            character.id === viewedCharacter.id
                              ? "border-violet-500 bg-violet-500/10"
                              : character.active
                                ? "border-emerald-400 bg-emerald-500/10"
                                : "border-neutral-700 bg-neutral-950 hover:border-violet-500"
                          }`}
                        >
                          <img
                            src={`${assetUrl(character.reference_image_url)}?t=${characterRefTs}`}
                            alt=""
                            className="h-full w-full rounded-sm object-cover"
                          />
                          {character.active && (
                            <span className="absolute bottom-1 right-1 size-2 rounded-full bg-emerald-400 shadow-[0_0_0_2px_rgba(10,10,10,0.85)]" />
                          )}
                        </button>
                      ))}
                      <button
                        type="button"
                        onClick={() => setShowCharacterModal(true)}
                        className="flex h-10 min-w-20 items-center justify-center gap-1 rounded border-2 border-dashed border-neutral-700 px-2 text-xs font-medium text-neutral-400 hover:border-violet-500 hover:text-violet-300 transition-colors"
                      >
                        <Plus className="size-4" />
                        New
                      </button>
                    </div>
                    </div>
                  ) : (
                    <div className="flex aspect-video flex-col items-center justify-center rounded-md border border-dashed border-neutral-700 text-center">
                      <p className="text-sm text-neutral-500">No characters for this preset yet.</p>
                      <button
                        type="button"
                        onClick={() => setShowCharacterModal(true)}
                        className="mt-4 flex items-center gap-2 rounded-lg border-2 border-dashed border-neutral-700 px-5 py-3 text-sm font-medium text-neutral-300 hover:border-violet-500 hover:text-violet-300 transition-colors"
                      >
                        <Plus className="size-4" />
                        New character
                      </button>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <div className="rounded-lg border border-neutral-800 bg-neutral-950/50 p-4 text-sm text-neutral-500">
                Create or select a style preset before generating a character.
              </div>
            )}

          {onContinue && (
            <div className="flex items-center justify-between gap-3 rounded-lg border border-neutral-800 bg-neutral-950/50 px-4 py-3">
              <p className="text-sm text-neutral-400">
                {activeCharacterReady
                  ? "This project will use the active character for the active style preset."
                  : "Set a style preset active, then generate or select its active character."}
              </p>
              <button
                type="button"
                onClick={onContinue}
                disabled={!activeCharacterReady}
                className="rounded-lg bg-emerald-500 px-4 py-2 text-sm font-medium text-neutral-950 hover:bg-emerald-400 disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
              >
                Continue
              </button>
            </div>
          )}
          </div>
        </div>

        {showDefaults && (
          <div
            data-testid="brand-defaults-panel"
            className="space-y-3 rounded-lg border border-neutral-800 bg-neutral-900 p-3 lg:col-span-2"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <SettingsSectionHeader
                title="New Project Visual Identity"
                description="Choose how new projects start. Existing projects are unchanged."
              />
              {saving && <span className="rounded bg-violet-500/15 px-2 py-1 text-xs font-medium text-violet-300">Saving...</span>}
            </div>
            <StylePresetToggle
              eliEnabled={eliEnabledDefault === "true"}
              enabled={stylePresetEnabledDefault === "true"}
              onEliChange={(next) => setEliEnabledDefault(next ? "true" : "false")}
              onChange={(next) => setStylePresetEnabledDefault(next ? "true" : "false")}
              activePresetName={activePreset?.name ?? null}
            />
          </div>
        )}
      </div>

      {showModal && (
        <StylePresetCreateModal
          onClose={() => setShowModal(false)}
          onCreated={async (preset) => {
            setViewedId(preset.id);
            await loadAll();
          }}
        />
      )}
      {showCharacterModal && viewedPreset && (
        <StylePresetCharacterCreateModal
          preset={viewedPreset}
          onClose={() => setShowCharacterModal(false)}
          onCreated={handleCharacterCreated}
        />
      )}

      {saving && (
        <div className="fixed bottom-0 left-0 right-0 z-40 border-t border-neutral-800 bg-neutral-900/95 backdrop-blur-sm px-8 py-3">
          <div className="mx-auto flex max-w-2xl items-center justify-between">
            <span className="text-sm text-neutral-400">Saving brand defaults...</span>
          </div>
        </div>
      )}
    </section>
  );
}
