import { useEffect, useState } from "react";
import {
  assetUrl,
  deleteStylePreset,
  getActiveStylePreset,
  listStylePresets,
  setActiveStylePreset,
  type StylePreset,
} from "../../api";
import { useStylePreset } from "../../contexts/StylePresetContext";
import { StylePresetCreateModal } from "./StylePresetCreateModal";

export function StylePresetsSection() {
  const [presets, setPresets] = useState<StylePreset[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
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
    await refreshActive();
  };

  const handleDelete = async (id: string) => {
    await deleteStylePreset(id);
    if (activeId === id) {
      setActiveId(null);
      await refreshActive();
    }
    await loadAll();
  };

  return (
    <section className="space-y-4">
      <header>
        <h2 className="text-lg font-semibold text-neutral-100">Style Presets</h2>
        <p className="text-sm text-neutral-400">
          A reference image attached to AI image generation. Used to enforce a consistent visual art style across all videos. Only applies when Eli is disabled for a video.
        </p>
      </header>

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

      <div className="grid grid-cols-3 gap-3">
        {presets.map((p) => (
          <div
            key={p.id}
            className={`relative rounded-md border bg-neutral-900 p-3 ${
              p.id === activeId ? "border-violet-500" : "border-neutral-800"
            }`}
          >
            <img
              src={assetUrl(p.image_url)}
              alt={p.name}
              className="mb-2 aspect-video w-full rounded object-cover"
            />
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-medium text-neutral-100">{p.name || "Untitled"}</div>
                <div className="truncate text-xs text-neutral-400" title={p.prompt}>{p.prompt}</div>
              </div>
              {p.id === activeId && (
                <span className="rounded bg-violet-500/20 px-2 py-0.5 text-xs text-violet-300">Active</span>
              )}
            </div>
            <button
              onClick={() => handleDelete(p.id)}
              className="mt-2 w-full rounded border border-red-900 px-2 py-1 text-xs text-red-400 hover:bg-red-950 transition-colors"
            >
              Delete
            </button>
          </div>
        ))}
        <button
          onClick={() => setShowModal(true)}
          className="flex aspect-[4/3] items-center justify-center rounded-md border-2 border-dashed border-neutral-700 text-sm text-neutral-400 hover:border-violet-500 hover:text-violet-400 transition-colors"
        >
          + New preset
        </button>
      </div>

      {showModal && (
        <StylePresetCreateModal
          onClose={() => setShowModal(false)}
          onCreated={async () => {
            await loadAll();
          }}
        />
      )}
    </section>
  );
}
