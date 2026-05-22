import { useEffect, useState } from "react";

import {
  assetUrl,
  regenerateMainCharacterReference,
  updateMainCharacter,
} from "../../api";
import type { MainCharacter, ProjectConfig } from "../../api";

type Props = {
  scriptId: string;
  config: ProjectConfig;
  onClose: () => void;
  onUpdated: (next: ProjectConfig) => void;
};

export default function MainCharacterDrawer({
  scriptId,
  config,
  onClose,
  onUpdated,
}: Props) {
  const initial = config.main_character;
  const [name, setName] = useState(initial?.name ?? "");
  const [appearance, setAppearance] = useState(initial?.appearance ?? "");
  const [vibe, setVibe] = useState(initial?.vibe ?? "");
  const [saving, setSaving] = useState(false);
  const [regenerating, setRegenerating] = useState(false);

  useEffect(() => {
    setName(config.main_character?.name ?? "");
    setAppearance(config.main_character?.appearance ?? "");
    setVibe(config.main_character?.vibe ?? "");
  }, [config.main_character]);

  const dirty =
    name !== (initial?.name ?? "") ||
    appearance !== (initial?.appearance ?? "") ||
    vibe !== (initial?.vibe ?? "");

  const save = async () => {
    setSaving(true);
    const character: MainCharacter = { name, appearance, vibe };
    const res = await updateMainCharacter(scriptId, character);
    setSaving(false);
    if (res.ok) {
      onUpdated(res.data as ProjectConfig);
    }
  };

  const regenerate = async () => {
    setRegenerating(true);
    const res = await regenerateMainCharacterReference(scriptId);
    setRegenerating(false);
    if (res.ok) {
      onUpdated(res.data as ProjectConfig);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex justify-end" onClick={onClose}>
      <div
        className="w-[480px] h-full bg-neutral-950 border-l border-neutral-800 p-6 overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-neutral-100">Main Character</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-neutral-500 hover:text-neutral-200 transition-colors"
          >
            ✕
          </button>
        </div>

        {config.main_character_reference_url ? (
          <img
            src={assetUrl(config.main_character_reference_url)}
            alt="Main character reference"
            className="w-full aspect-video rounded-lg border border-neutral-800 mb-4 object-cover"
          />
        ) : (
          <div className="w-full aspect-video rounded-lg border border-dashed border-neutral-700 flex items-center justify-center text-neutral-500 text-sm mb-4">
            Reference image not generated yet
          </div>
        )}

        <button
          type="button"
          onClick={regenerate}
          disabled={regenerating || !name}
          className="w-full mb-6 px-3 py-2 text-sm rounded-md bg-neutral-800 text-neutral-200 hover:bg-neutral-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {regenerating ? "Regenerating..." : "Regenerate reference image"}
        </button>

        <div className="space-y-4">
          <label className="block">
            <span className="text-xs text-neutral-400 uppercase tracking-wide">Name</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="mt-1 w-full bg-neutral-900 border border-neutral-800 rounded-md px-3 py-2 text-sm text-neutral-100 focus:border-violet-500 focus:outline-none"
            />
          </label>
          <label className="block">
            <span className="text-xs text-neutral-400 uppercase tracking-wide">Appearance</span>
            <textarea
              rows={5}
              value={appearance}
              onChange={(e) => setAppearance(e.target.value)}
              className="mt-1 w-full bg-neutral-900 border border-neutral-800 rounded-md px-3 py-2 text-sm text-neutral-100 focus:border-violet-500 focus:outline-none resize-y"
            />
          </label>
          <label className="block">
            <span className="text-xs text-neutral-400 uppercase tracking-wide">Vibe</span>
            <textarea
              rows={3}
              value={vibe}
              onChange={(e) => setVibe(e.target.value)}
              className="mt-1 w-full bg-neutral-900 border border-neutral-800 rounded-md px-3 py-2 text-sm text-neutral-100 focus:border-violet-500 focus:outline-none resize-y"
            />
          </label>
        </div>

        <button
          type="button"
          onClick={save}
          disabled={!dirty || saving}
          className="mt-6 w-full px-3 py-2 text-sm rounded-md bg-violet-600 text-white hover:bg-violet-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {saving ? "Saving..." : "Save"}
        </button>

        <p className="mt-4 text-xs text-neutral-500">
          Editing the description or regenerating the reference will invalidate
          cached scene images that include the character. They will re-render on
          next batch.
        </p>
      </div>
    </div>
  );
}
