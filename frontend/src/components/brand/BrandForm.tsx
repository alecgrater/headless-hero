import { useState } from "react";
import type { BrandProfileCreate } from "../types/brand";

const EMPTY_FORM: BrandProfileCreate = {
  name: "",
  art_style: "",
  color_palette: "",
  font: "",
  voice_id: "",
  youtube_channel_id: "",
  tiktok_handle: "",
  instagram_handle: "",
};

interface Props {
  onSave: (brand: BrandProfileCreate) => Promise<void>;
  onCancel: () => void;
  initial?: BrandProfileCreate;
  saving?: boolean;
}

export default function BrandForm({ onSave, onCancel, initial, saving }: Props) {
  const [form, setForm] = useState<BrandProfileCreate>(initial ?? EMPTY_FORM);

  const set = (field: keyof BrandProfileCreate, value: string) =>
    setForm((prev) => ({ ...prev, [field]: value }));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave(form);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-5 max-w-xl">
      {/* Name */}
      <div>
        <label className="block text-sm font-medium text-neutral-300 mb-1">
          Brand / Channel Name <span className="text-red-400">*</span>
        </label>
        <input
          required
          value={form.name}
          onChange={(e) => set("name", e.target.value)}
          className="w-full rounded-lg bg-neutral-800 border border-neutral-700 px-3 py-2 text-neutral-100 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-violet-600"
          placeholder="Everything Professor"
        />
      </div>

      {/* Art style */}
      <div>
        <label className="block text-sm font-medium text-neutral-300 mb-1">
          Art Style Description
        </label>
        <textarea
          rows={3}
          value={form.art_style}
          onChange={(e) => set("art_style", e.target.value)}
          className="w-full rounded-lg bg-neutral-800 border border-neutral-700 px-3 py-2 text-neutral-100 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-violet-600"
          placeholder="Flat illustration, muted earth tones, thick outlines, dark background"
        />
        <p className="text-xs text-neutral-500 mt-1">
          Prepended to every image generation prompt to enforce visual consistency.
        </p>
      </div>

      {/* Color palette */}
      <div>
        <label className="block text-sm font-medium text-neutral-300 mb-1">
          Color Palette
        </label>
        <input
          value={form.color_palette}
          onChange={(e) => set("color_palette", e.target.value)}
          className="w-full rounded-lg bg-neutral-800 border border-neutral-700 px-3 py-2 text-neutral-100 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-violet-600"
          placeholder="#1a1a2e, #e94560, #0f3460, #16213e"
        />
        <p className="text-xs text-neutral-500 mt-1">
          Comma-separated hex codes for overlays, text, and backgrounds.
        </p>
      </div>

      {/* Font */}
      <div>
        <label className="block text-sm font-medium text-neutral-300 mb-1">
          Font
        </label>
        <input
          value={form.font}
          onChange={(e) => set("font", e.target.value)}
          className="w-full rounded-lg bg-neutral-800 border border-neutral-700 px-3 py-2 text-neutral-100 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-violet-600"
          placeholder="Montserrat Bold"
        />
      </div>

      {/* Voice */}
      <div>
        <label className="block text-sm font-medium text-neutral-300 mb-1">
          Voice ID
        </label>
        <input
          value={form.voice_id}
          onChange={(e) => set("voice_id", e.target.value)}
          className="w-full rounded-lg bg-neutral-800 border border-neutral-700 px-3 py-2 text-neutral-100 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-violet-600"
          placeholder="ElevenLabs voice ID (or leave blank)"
        />
      </div>

      {/* Platform section */}
      <fieldset className="border border-neutral-700 rounded-lg p-4 space-y-3">
        <legend className="text-sm font-medium text-neutral-400 px-2">
          Platform Accounts (optional)
        </legend>

        <div>
          <label className="block text-xs text-neutral-400 mb-1">YouTube Channel ID</label>
          <input
            value={form.youtube_channel_id}
            onChange={(e) => set("youtube_channel_id", e.target.value)}
            className="w-full rounded-lg bg-neutral-800 border border-neutral-700 px-3 py-2 text-sm text-neutral-100 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-violet-600"
            placeholder="UCxxxxx"
          />
        </div>
        <div>
          <label className="block text-xs text-neutral-400 mb-1">TikTok Handle</label>
          <input
            value={form.tiktok_handle}
            onChange={(e) => set("tiktok_handle", e.target.value)}
            className="w-full rounded-lg bg-neutral-800 border border-neutral-700 px-3 py-2 text-sm text-neutral-100 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-violet-600"
            placeholder="@myhandle"
          />
        </div>
        <div>
          <label className="block text-xs text-neutral-400 mb-1">Instagram Handle</label>
          <input
            value={form.instagram_handle}
            onChange={(e) => set("instagram_handle", e.target.value)}
            className="w-full rounded-lg bg-neutral-800 border border-neutral-700 px-3 py-2 text-sm text-neutral-100 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-violet-600"
            placeholder="@myhandle"
          />
        </div>
      </fieldset>

      {/* Actions */}
      <div className="flex gap-3 pt-2">
        <button
          type="submit"
          disabled={saving || !form.name.trim()}
          className="px-5 py-2.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg font-medium transition-colors"
        >
          {saving ? "Saving..." : "Save Brand"}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="px-5 py-2.5 bg-neutral-800 hover:bg-neutral-700 rounded-lg font-medium transition-colors border border-neutral-700"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}
