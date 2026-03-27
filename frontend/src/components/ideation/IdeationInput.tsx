import { useState } from "react";

interface Props {
  onGenerate: (niche: string) => void;
  loading: boolean;
}

export default function IdeationInput({ onGenerate, loading }: Props) {
  const [niche, setNiche] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (niche.trim()) onGenerate(niche.trim());
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-3">
      <input
        value={niche}
        onChange={(e) => setNiche(e.target.value)}
        placeholder="Enter a niche — e.g. psychology, gaming, history..."
        className="flex-1 rounded-lg bg-neutral-800 border border-neutral-700 px-4 py-3 text-neutral-100 placeholder-neutral-500 focus:outline-none focus:ring-2 focus:ring-violet-600"
        disabled={loading}
      />
      <button
        type="submit"
        disabled={loading || !niche.trim()}
        className="px-6 py-3 bg-violet-600 hover:bg-violet-500 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg font-medium transition-colors whitespace-nowrap"
      >
        {loading ? "Generating..." : "Generate Ideas"}
      </button>
    </form>
  );
}
