import { useState } from "react";
import { assetUrl, createStylePreset, pollStylePresetJob, type StylePreset } from "../../api";

const PROMPT_PLACEHOLDER =
  "A 16:9 reference sheet showing 6 diverse people in different poses, 4 everyday objects, and 2 environments — all in 90s Nickelodeon style with thick outlines and muted earth tones.";

type Props = {
  onClose: () => void;
  onCreated: (preset: StylePreset) => void;
};

export function StylePresetCreateModal({ onClose, onCreated }: Props) {
  const [name, setName] = useState("");
  const [prompt, setPrompt] = useState("");
  const [generating, setGenerating] = useState(false);
  const [previewPreset, setPreviewPreset] = useState<StylePreset | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleGenerate = async () => {
    if (!prompt.trim()) {
      setError("Prompt is required");
      return;
    }
    setError(null);
    setGenerating(true);
    try {
      const { job_id } = await createStylePreset(prompt, name || "Untitled");
      const preset = await pollStylePresetJob(job_id);
      setPreviewPreset(preset);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setGenerating(false);
    }
  };

  const handleSave = () => {
    if (previewPreset) {
      onCreated(previewPreset);
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="w-full max-w-2xl rounded-lg border border-neutral-800 bg-neutral-950 p-6 shadow-xl">
        <h2 className="mb-4 text-lg font-semibold text-neutral-100">New style preset</h2>

        <div className="mb-4 space-y-2">
          <label className="block text-xs font-medium text-neutral-400">Name</label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Saturday Cartoon"
            className="w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 focus:border-violet-500 focus:outline-none"
          />
        </div>

        <div className="mb-2 rounded border border-neutral-800 bg-neutral-900/50 p-3 text-xs text-neutral-400">
          This prompt is sent to Gemini as-is. Tip: include multiple subjects (people, objects, environments) so the reference can guide many kinds of scene generations.
        </div>

        <div className="mb-4 space-y-2">
          <label className="block text-xs font-medium text-neutral-400">Prompt</label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={PROMPT_PLACEHOLDER}
            rows={5}
            className="w-full rounded border border-neutral-700 bg-neutral-900 px-3 py-2 text-sm text-neutral-100 focus:border-violet-500 focus:outline-none"
          />
        </div>

        {previewPreset && (
          <div className="mb-4">
            <div className="mb-2 text-xs text-neutral-400">Preview</div>
            <img
              src={assetUrl(previewPreset.image_url)}
              alt={previewPreset.name}
              className="w-full rounded border border-neutral-700"
            />
          </div>
        )}

        {error && <div className="mb-4 text-sm text-red-400">{error}</div>}

        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="rounded border border-neutral-700 px-4 py-2 text-sm text-neutral-300 hover:bg-neutral-800 transition-colors"
          >
            Cancel
          </button>
          {previewPreset ? (
            <>
              <button
                onClick={() => {
                  setPreviewPreset(null);
                  handleGenerate();
                }}
                disabled={generating}
                className="rounded border border-neutral-700 px-4 py-2 text-sm text-neutral-300 hover:bg-neutral-800 transition-colors disabled:opacity-50"
              >
                Regenerate
              </button>
              <button
                onClick={handleSave}
                className="rounded bg-violet-600 px-4 py-2 text-sm text-white hover:bg-violet-500 transition-colors"
              >
                Save
              </button>
            </>
          ) : (
            <button
              onClick={handleGenerate}
              disabled={generating || !prompt.trim()}
              className="rounded bg-violet-600 px-4 py-2 text-sm text-white hover:bg-violet-500 transition-colors disabled:opacity-50"
            >
              {generating ? "Generating…" : "Generate"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
