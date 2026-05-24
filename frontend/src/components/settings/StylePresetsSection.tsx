import { ChevronLeft, ChevronRight, Plus } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  assetUrl,
  deleteStylePreset,
  getActiveStylePreset,
  listStylePresets,
  setActiveStylePreset,
  type StylePreset,
} from "../../api";
import { useStylePreset } from "../../contexts/StylePresetContext";
import { MainCharacterSection } from "./MainCharacterSection";
import { StylePresetCreateModal } from "./StylePresetCreateModal";

export function StylePresetsSection() {
  const [activeTab, setActiveTab] = useState<"style" | "character">("style");
  const [presets, setPresets] = useState<StylePreset[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [viewedId, setViewedId] = useState<string | null>(null);
  const [showModal, setShowModal] = useState(false);
  const { refresh: refreshActive } = useStylePreset();

  const loadAll = async () => {
    const [list, active] = await Promise.all([
      listStylePresets(),
      getActiveStylePreset(),
    ]);
    setPresets(list);
    setActiveId(active?.id ?? null);
  };

  useEffect(() => {
    loadAll();
  }, []);

  const handleSetActive = async (id: string | null) => {
    await setActiveStylePreset(id);
    setActiveId(id);
    if (id) {
      setViewedId(id);
    }
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

  useEffect(() => {
    if (presets.length === 0) {
      setViewedId(null);
      return;
    }

    if (viewedId && presets.some((p) => p.id === viewedId)) {
      return;
    }

    setViewedId(activeId ?? presets[0].id);
  }, [activeId, presets, viewedId]);

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

  return (
    <section className="space-y-4">
      <header>
        <h2 className="text-lg font-semibold text-neutral-100">Style Presets</h2>
        <p className="text-sm text-neutral-400">
          Global visual references used when Eli is disabled.
        </p>
      </header>

      <div className="inline-flex rounded-md border border-neutral-800 bg-neutral-900 p-1">
        <button
          type="button"
          onClick={() => setActiveTab("style")}
          className={`rounded px-3 py-1.5 text-sm font-medium transition-colors ${
            activeTab === "style"
              ? "bg-neutral-700 text-neutral-100"
              : "text-neutral-400 hover:text-neutral-200"
          }`}
        >
          Style Presets
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("character")}
          className={`rounded px-3 py-1.5 text-sm font-medium transition-colors ${
            activeTab === "character"
              ? "bg-neutral-700 text-neutral-100"
              : "text-neutral-400 hover:text-neutral-200"
          }`}
        >
          Main Character
        </button>
      </div>

      {activeTab === "character" && <MainCharacterSection />}

      {activeTab === "style" && (
        <>

      <div className="rounded-md border border-neutral-800 bg-neutral-900 p-4">
        <label className="mb-1 block text-xs font-medium text-neutral-400">
          Active preset
        </label>
        <select
          value={activeId ?? ""}
          onChange={(e) => handleSetActive(e.target.value || null)}
          className="w-full rounded border border-neutral-700 bg-neutral-800 px-3 py-2 text-sm text-neutral-100"
        >
          <option value="">None</option>
          {presets.map((p) => (
            <option key={p.id} value={p.id}>{p.name || "Untitled"}</option>
          ))}
        </select>
        <p className="mt-2 text-xs text-neutral-500">
          All non-Eli projects with the style toggle on will use this preset.
        </p>
      </div>

      <div className="rounded-md border border-neutral-800 bg-neutral-900/60 px-4 py-5">
        {viewedPreset ? (
          <div className="mx-auto flex max-w-6xl flex-col items-center">
            <div className="grid w-full grid-cols-[48px_minmax(0,1fr)_48px] items-center gap-3 sm:grid-cols-[64px_minmax(0,1fr)_64px]">
              <button
                type="button"
                onClick={showPreviousPreset}
                aria-label="Previous style preset"
                className="flex size-12 items-center justify-center rounded-full border border-neutral-700 bg-neutral-950/80 text-neutral-300 hover:border-violet-500 hover:bg-violet-950/30 hover:text-violet-200 transition-colors sm:size-14"
              >
                <ChevronLeft className="size-7" />
              </button>

              <div className="grid min-w-0 items-center gap-4 lg:grid-cols-[minmax(0,760px)_minmax(220px,1fr)]">
                <button
                  type="button"
                  onClick={() => setViewedId(viewedPreset.id)}
                  className={`w-full max-w-[760px] rounded-md border-2 bg-neutral-950 p-1 transition-colors ${
                    viewedPreset.id === activeId
                      ? "border-violet-500 shadow-[0_0_0_1px_rgba(139,92,246,0.45)]"
                      : "border-neutral-700 hover:border-violet-500/70"
                  }`}
                >
                  <img
                    src={assetUrl(viewedPreset.image_url)}
                    alt={viewedPreset.name || "Untitled style preset"}
                    className="aspect-video w-full rounded object-cover"
                  />
                </button>

                <div className="flex min-w-0 flex-col items-center text-center lg:items-start lg:text-left">
                  <div className="flex max-w-full items-center justify-center gap-2 lg:justify-start">
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
                    className="mt-1 max-w-full overflow-hidden text-sm leading-5 text-neutral-400 [display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:2]"
                  >
                    {viewedPreset.prompt}
                  </p>
                  <div className="mt-4 flex flex-wrap items-center justify-center gap-2 lg:justify-start">
                    {viewedPreset.id !== activeId && (
                      <button
                        type="button"
                        onClick={() => handleSetActive(viewedPreset.id)}
                        className="rounded bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-500 transition-colors"
                      >
                        Set as active
                      </button>
                    )}
                    <button
                      type="button"
                      onClick={() => handleDelete(viewedPreset.id)}
                      className="rounded border border-red-900 px-4 py-2 text-sm font-medium text-red-400 hover:bg-red-950 transition-colors"
                    >
                      Delete
                    </button>
                  </div>
                  <div className="mt-4 flex flex-wrap items-center justify-center gap-2 lg:justify-start">
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
                        <img
                          src={assetUrl(p.image_url)}
                          alt=""
                          className="h-full w-full rounded-sm object-cover"
                        />
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
              </div>

              <button
                type="button"
                onClick={showNextPreset}
                aria-label="Next style preset"
                className="flex size-12 items-center justify-center rounded-full border border-neutral-700 bg-neutral-950/80 text-neutral-300 hover:border-violet-500 hover:bg-violet-950/30 hover:text-violet-200 transition-colors sm:size-14"
              >
                <ChevronRight className="size-7" />
              </button>
            </div>
          </div>
        ) : (
          <div className="flex min-h-72 flex-col items-center justify-center text-center">
            <p className="text-sm text-neutral-400">No style presets yet.</p>
            <button
              type="button"
              onClick={() => setShowModal(true)}
              className="mt-4 flex items-center gap-2 rounded-md border-2 border-dashed border-neutral-700 px-5 py-3 text-sm font-medium text-neutral-300 hover:border-violet-500 hover:text-violet-300 transition-colors"
            >
              <Plus className="size-4" />
              New preset
            </button>
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
        </>
      )}
    </section>
  );
}
