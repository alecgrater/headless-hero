import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
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
import { StylePresetCreateModal } from "./StylePresetCreateModal";

const DISABLED_SETTING_VALUES = new Set(["", "0", "false", "no", "off"]);

function settingEnabled(val: string): boolean {
  return !DISABLED_SETTING_VALUES.has(val.trim().toLowerCase());
}

type Props = {
  compact?: boolean;
  showDefaults?: boolean;
  onContinue?: () => void;
};

export function StylePresetsSection({ compact = false, showDefaults = true, onContinue }: Props) {
  const [presets, setPresets] = useState<StylePreset[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [viewedId, setViewedId] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [characters, setCharacters] = useState<StylePresetCharacter[]>([]);
  const [viewedCharacterId, setViewedCharacterId] = useState<string | null>(null);
  const [characterName, setCharacterName] = useState("");
  const [characterAppearance, setCharacterAppearance] = useState("");
  const [characterVibe, setCharacterVibe] = useState("");
  const [generatingCharacter, setGeneratingCharacter] = useState(false);
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
  const hasCharacterDetails = Boolean(characterName.trim() && characterAppearance.trim());
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

  const handleCreateCharacter = async () => {
    if (!viewedPreset || !hasCharacterDetails) return;
    setGeneratingCharacter(true);
    try {
      const created = await createStylePresetCharacter(viewedPreset.id, {
        name: characterName,
        appearance: characterAppearance,
        vibe: characterVibe,
      });
      setCharacters((current) => [
        created,
        ...current.map((character) => ({ ...character, active: false })),
      ]);
      setViewedCharacterId(created.id);
      setCharacterName("");
      setCharacterAppearance("");
      setCharacterVibe("");
      setCharacterRefTs(Date.now());
    } finally {
      setGeneratingCharacter(false);
    }
  };

  const handleSaveDefaults = async () => {
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
  };

  if (loading) {
    return <p className="text-sm text-neutral-500">Loading...</p>;
  }

  return (
    <section className={`${compact ? "space-y-5 pb-8" : "space-y-6 pb-24"}`}>
      {!compact && (
        <header>
          <h2 className="text-lg font-semibold text-neutral-100">Brand & Style</h2>
          <p className="text-sm text-neutral-400">
            Set the visual style, recurring character, and defaults for new projects.
          </p>
        </header>
      )}

      <div className="space-y-5">
        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-semibold text-neutral-100">Style Presets</h3>
            <p className="text-xs text-neutral-500">
              Global visual references used when Eli is disabled.
            </p>
          </div>

          <div className="rounded-xl border border-neutral-800 bg-neutral-900/60 px-4 py-5">
            {viewedPreset ? (
              <div className="grid grid-cols-[44px_minmax(0,1fr)_44px] items-center gap-3">
                <button
                  type="button"
                  onClick={showPreviousPreset}
                  aria-label="Previous style preset"
                  className="flex size-11 items-center justify-center rounded-full border border-neutral-700 bg-neutral-950/80 text-neutral-300 hover:border-violet-500 hover:bg-violet-950/30 hover:text-violet-200 transition-colors"
                >
                  <ChevronLeft className="size-6" />
                </button>

                <div className="min-w-0">
                  <button
                    type="button"
                    onClick={() => setViewedId(viewedPreset.id)}
                    className={`w-full rounded-lg border-2 bg-neutral-950 p-1 transition-colors ${
                      viewedPreset.id === activeId
                        ? "border-violet-500 shadow-[0_0_0_1px_rgba(139,92,246,0.45)]"
                        : "border-neutral-700 hover:border-violet-500/70"
                    }`}
                  >
                    <img
                      src={assetUrl(viewedPreset.image_url)}
                      alt={viewedPreset.name || "Untitled style preset"}
                      className="aspect-video w-full rounded-md object-cover"
                    />
                  </button>

                  <div className="mt-4 flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex max-w-full items-center gap-2">
                        <h3 className="truncate text-lg font-semibold text-neutral-100">
                          {viewedPreset.name || "Untitled"}
                        </h3>
                        {viewedPreset.id === activeId && (
                          <span className="shrink-0 rounded bg-violet-500/20 px-2 py-0.5 text-xs font-medium text-violet-300">
                            Active
                          </span>
                        )}
                      </div>
                      <p
                        title={viewedPreset.prompt}
                        className="mt-1 max-w-2xl overflow-hidden text-sm leading-5 text-neutral-400 [display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:2]"
                      >
                        {viewedPreset.prompt}
                      </p>
                    </div>
                    <div className="flex shrink-0 flex-wrap gap-2">
                      {viewedPreset.id !== activeId && (
                        <button
                          type="button"
                          onClick={() => handleSetActive(viewedPreset.id)}
                          className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 transition-colors"
                        >
                          Set active
                        </button>
                      )}
                      <button
                        type="button"
                        onClick={() => handleDelete(viewedPreset.id)}
                        className="rounded-lg border border-red-900 px-4 py-2 text-sm font-medium text-red-400 hover:bg-red-950 transition-colors"
                      >
                        Delete
                      </button>
                    </div>
                  </div>

                  <div className="mt-4 flex flex-wrap items-center gap-2">
                    {presets.map((p) => (
                      <button
                        key={p.id}
                        type="button"
                        onClick={() => setViewedId(p.id)}
                        aria-label={`View ${p.name || "Untitled"} style preset`}
                        className={`relative h-12 w-20 rounded border p-0.5 transition-colors ${
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
                      className="flex h-12 min-w-24 items-center justify-center gap-1 rounded border-2 border-dashed border-neutral-700 px-3 text-xs font-medium text-neutral-400 hover:border-violet-500 hover:text-violet-300 transition-colors"
                    >
                      <Plus className="size-4" />
                      New preset
                    </button>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={showNextPreset}
                  aria-label="Next style preset"
                  className="flex size-11 items-center justify-center rounded-full border border-neutral-700 bg-neutral-950/80 text-neutral-300 hover:border-violet-500 hover:bg-violet-950/30 hover:text-violet-200 transition-colors"
                >
                  <ChevronRight className="size-6" />
                </button>
              </div>
            ) : (
              <div className="flex min-h-72 flex-col items-center justify-center text-center">
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

        <div className="flex flex-col gap-5">
          {showDefaults && (
            <div className="order-2 space-y-4 rounded-xl border border-neutral-800 bg-neutral-900 p-4">
              <div>
                <h3 className="text-sm font-semibold text-neutral-100">New Project Defaults</h3>
                <p className="text-xs text-neutral-500">
                  Choose how new projects start. Existing projects are unchanged.
                </p>
              </div>
              <div className="flex items-start justify-between gap-5">
                <div>
                  <h4 className="text-sm font-medium text-neutral-100">Enable Eli host overlay</h4>
                  <p className="text-xs text-neutral-500">
                    New projects start with the Eli overlay instead of a scene-integrated main character.
                  </p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={eliEnabledDefault === "true"}
                  aria-label="Enable Eli host overlay by default for new projects"
                  onClick={() => setEliEnabledDefault(eliEnabledDefault === "true" ? "false" : "true")}
                  className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 ${
                    eliEnabledDefault === "true" ? "bg-violet-600 shadow-sm shadow-violet-500/30" : "bg-neutral-700"
                  }`}
                >
                  <span
                    className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow transition-transform ${
                      eliEnabledDefault === "true" ? "translate-x-5" : "translate-x-0"
                    }`}
                  />
                </button>
              </div>
              <StylePresetToggle
                eliEnabled={eliEnabledDefault === "true"}
                enabled={stylePresetEnabledDefault === "true"}
                onChange={(next) => setStylePresetEnabledDefault(next ? "true" : "false")}
                activePresetName={activePreset?.name ?? null}
              />
            </div>
          )}

          <div className="order-1 space-y-4 rounded-xl border border-neutral-800 bg-neutral-900 p-4">
            <div>
              <h3 className="text-sm font-semibold text-neutral-100">Main Character</h3>
              <p className="text-xs text-neutral-500">
                Characters are scoped to the viewed style preset and inherit its visual style.
              </p>
            </div>

            {viewedPreset ? (
              <>
                <div className="rounded-lg border border-neutral-800 bg-neutral-950/50 p-3">
                  {viewedCharacter ? (
                    <div className="space-y-3">
                      <div className="grid grid-cols-[40px_minmax(0,1fr)_40px] items-center gap-3">
                        <button
                          type="button"
                          onClick={showPreviousCharacter}
                          aria-label="Previous character reference"
                          className="flex size-10 items-center justify-center rounded-full border border-neutral-700 bg-neutral-950 text-neutral-300 hover:border-violet-500 hover:text-violet-300 transition-colors"
                        >
                          <ChevronLeft className="size-5" />
                        </button>
                        <img
                          src={`${assetUrl(viewedCharacter.reference_image_url)}?t=${characterRefTs}`}
                          alt={viewedCharacter.name}
                          className="aspect-video w-full rounded-md object-cover"
                        />
                        <button
                          type="button"
                          onClick={showNextCharacter}
                          aria-label="Next character reference"
                          className="flex size-10 items-center justify-center rounded-full border border-neutral-700 bg-neutral-950 text-neutral-300 hover:border-violet-500 hover:text-violet-300 transition-colors"
                        >
                          <ChevronRight className="size-5" />
                        </button>
                      </div>
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="truncate text-sm font-medium text-neutral-100">{viewedCharacter.name}</p>
                            {viewedCharacter.active && (
                              <span className="rounded bg-emerald-500/15 px-2 py-0.5 text-xs font-medium text-emerald-300">
                                Active
                              </span>
                            )}
                          </div>
                          <p className="mt-1 line-clamp-2 text-xs text-neutral-500">
                            {viewedCharacter.appearance}
                          </p>
                        </div>
                        {!viewedCharacter.active && (
                          <button
                            type="button"
                            onClick={() => handleSelectCharacter(viewedCharacter.id)}
                            className="shrink-0 rounded-lg bg-emerald-500 px-3 py-2 text-xs font-medium text-neutral-950 hover:bg-emerald-400 transition-colors"
                          >
                            Set active
                          </button>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {characters.map((character) => (
                          <button
                            key={character.id}
                            type="button"
                            onClick={() => setViewedCharacterId(character.id)}
                            aria-label={`View ${character.name}`}
                            className={`relative h-12 w-20 rounded border p-0.5 transition-colors ${
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
                      </div>
                    </div>
                  ) : (
                    <div className="flex aspect-video items-center justify-center rounded-md border border-dashed border-neutral-700 text-center text-sm text-neutral-500">
                      Generate a character reference for this preset.
                    </div>
                  )}
                </div>

                <div className="space-y-3">
                  <label className="block">
                    <span className="text-xs font-medium uppercase text-neutral-400">Name</span>
                    <input
                      type="text"
                      value={characterName}
                      onChange={(event) => setCharacterName(event.target.value)}
                      placeholder="e.g. Maya"
                      className="mt-1 w-full rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-100 placeholder-neutral-500 focus:border-violet-500 focus:outline-none"
                    />
                  </label>
                  <label className="block">
                    <span className="text-xs font-medium uppercase text-neutral-400">Appearance</span>
                    <textarea
                      rows={4}
                      value={characterAppearance}
                      onChange={(event) => setCharacterAppearance(event.target.value)}
                      placeholder="Distinctive clothing, body language, age, silhouette..."
                      className="mt-1 w-full resize-y rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-100 placeholder-neutral-500 focus:border-violet-500 focus:outline-none"
                    />
                  </label>
                  <label className="block">
                    <span className="text-xs font-medium uppercase text-neutral-400">Vibe</span>
                    <textarea
                      rows={2}
                      value={characterVibe}
                      onChange={(event) => setCharacterVibe(event.target.value)}
                      placeholder="Energetic, dry, curious..."
                      className="mt-1 w-full resize-y rounded-md border border-neutral-800 bg-neutral-950 px-3 py-2 text-sm text-neutral-100 placeholder-neutral-500 focus:border-violet-500 focus:outline-none"
                    />
                  </label>
                  <button
                    type="button"
                    onClick={handleCreateCharacter}
                    disabled={generatingCharacter || !hasCharacterDetails}
                    className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-50 transition-colors"
                  >
                    {generatingCharacter ? "Generating..." : "Generate character"}
                  </button>
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

      {hasChanges && (
        <div className="fixed bottom-0 left-0 right-0 z-40 border-t border-neutral-800 bg-neutral-900/95 backdrop-blur-sm px-8 py-3">
          <div className="mx-auto flex max-w-2xl items-center justify-between">
            <span className="text-sm text-neutral-400">You have unsaved brand defaults</span>
            <button
              onClick={handleSaveDefaults}
              disabled={saving}
              className="btn-primary px-5 py-2 rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950"
            >
              {saving ? "Saving..." : "Save Changes"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
