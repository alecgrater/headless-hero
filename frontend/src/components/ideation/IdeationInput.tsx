import { forwardRef, useImperativeHandle, useState } from "react";

interface Props {
  onGenerate: (niche: string) => void;
  loading: boolean;
}

export interface IdeationInputHandle {
  setNiche: (value: string) => void;
}

const IdeationInput = forwardRef<IdeationInputHandle, Props>(
  function IdeationInput({ onGenerate, loading }, ref) {
    const [niche, setNiche] = useState("");

    useImperativeHandle(ref, () => ({
      setNiche: (value: string) => setNiche(value),
    }));

    const handleSubmit = (e: React.FormEvent) => {
      e.preventDefault();
      if (niche.trim()) onGenerate(niche.trim());
    };

    return (
      <form onSubmit={handleSubmit} className="flex gap-3">
        <input
          value={niche}
          onChange={(e) => setNiche(e.target.value)}
          placeholder="Describe your video niche — e.g. 'deep sea creatures', 'unsolved crimes', 'retro gaming history'..."
          className="flex-1 rounded-lg bg-neutral-800 border border-neutral-700 px-4 py-3 text-neutral-100 placeholder-neutral-500 focus:outline-none focus:ring-1 focus:ring-violet-500/50 focus:border-violet-500/50"
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !niche.trim()}
          className="px-6 py-3 bg-transparent border border-violet-500 text-violet-400 hover:bg-violet-500/10 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg font-medium transition-colors whitespace-nowrap"
        >
          {loading ? "Generating..." : "Generate Ideas"}
        </button>
      </form>
    );
  },
);

export default IdeationInput;
