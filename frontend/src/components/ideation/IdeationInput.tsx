import { forwardRef, useImperativeHandle, useState, type FormEvent } from "react";

interface Props {
  onGenerate: (niche: string, guide?: string) => void;
  onCancel?: () => void;
  loading: boolean;
}

export interface IdeationInputHandle {
  setNiche: (value: string) => void;
}

const IdeationInput = forwardRef<IdeationInputHandle, Props>(
  function IdeationInput({ onGenerate, onCancel, loading }, ref) {
    const [niche, setNiche] = useState("");
    const [guideMode, setGuideMode] = useState(false);
    const [guide, setGuide] = useState("");

    useImperativeHandle(ref, () => ({
      setNiche: (value: string) => setNiche(value),
    }));

    const handleSubmit = (e: FormEvent) => {
      e.preventDefault();
      if (loading && onCancel) {
        onCancel();
        return;
      }
      if (niche.trim()) {
        onGenerate(niche.trim(), guideMode ? guide.trim() || undefined : undefined);
      }
    };

    return (
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="flex gap-3">
          <input
            value={niche}
            onChange={(e) => setNiche(e.target.value)}
            placeholder="Describe your video niche — e.g. 'deep sea creatures', 'unsolved crimes', 'retro gaming history'..."
            className="flex-1 rounded-lg bg-neutral-800 border border-neutral-700 px-4 py-3 text-neutral-100 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500/50 transition-all duration-200"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={!loading && !niche.trim()}
            className={`px-6 py-3 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg whitespace-nowrap font-medium transition-colors ${
              loading
                ? "bg-neutral-800 border border-red-500/30 text-neutral-200 hover:border-red-500/50"
                : "btn-primary"
            }`}
          >
            {loading ? "Cancel" : "Generate Ideas"}
          </button>
        </div>

        <label className="inline-flex items-center gap-2 text-sm text-neutral-300">
          <input
            type="checkbox"
            checked={guideMode}
            onChange={(e) => setGuideMode(e.target.checked)}
            disabled={loading}
            className="h-4 w-4 rounded border-neutral-600 bg-neutral-900 text-violet-500 focus:ring-violet-500/50"
          />
          Guide mode
        </label>

        {guideMode && (
          <textarea
            value={guide}
            onChange={(e) => setGuide(e.target.value)}
            placeholder="Explain the angle, constraints, examples, or thought process you want the ideas to follow..."
            rows={7}
            disabled={loading}
            className="w-full resize-y rounded-lg bg-neutral-800 border border-neutral-700 px-4 py-3 text-sm text-neutral-100 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-violet-500/50 focus:border-violet-500/50 transition-all duration-200"
          />
        )}
      </form>
    );
  },
);

export default IdeationInput;
