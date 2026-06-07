import { useCallback, useEffect, useState } from "react";
import { Plus } from "lucide-react";
import {
  getIdeas,
  createIdea,
  updateIdea,
  deleteIdea,
  getIdeaCategories,
} from "../../api";
import type { Idea, IdeaStatus } from "../../types/idea";
import SavedIdeaCard from "./SavedIdeaCard";
import { EmptyState } from "../ui/EmptyState";

interface Props {
  onGenerateIdeas: (niche: string) => void;
}

export default function IdeaPage({ onGenerateIdeas }: Props) {
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [newText, setNewText] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [data, cats] = await Promise.all([
        getIdeas("newest", categoryFilter ?? undefined, undefined),
        getIdeaCategories(),
      ]);
      setIdeas(data);
      setCategories(cats);
    } finally {
      setLoading(false);
    }
  }, [categoryFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const refreshCategories = useCallback(async () => {
    const cats = await getIdeaCategories();
    setCategories(cats);
  }, []);

  const handleAdd = async () => {
    const trimmed = newText.trim();
    if (!trimmed) return;
    try {
      const created = await createIdea(trimmed);
      setIdeas((prev) => [created, ...prev]);
      setNewText("");
      refreshCategories();
    } catch { /* toast shown by interceptor */ }
  };

  const handleUpdate = async (id: string, updates: { text?: string; status?: IdeaStatus }) => {
    try {
      const updated = await updateIdea(id, updates);
      setIdeas((prev) => prev.map((i) => (i.id === id ? updated : i)));
      if (updates.status) refreshCategories();
    } catch { /* toast shown by interceptor */ }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteIdea(id);
      setIdeas((prev) => prev.filter((i) => i.id !== id));
      refreshCategories();
    } catch { /* toast shown by interceptor */ }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleAdd();
    }
  };

  return (
    <div className="mx-auto max-w-4xl px-6 py-10">
      <div className="mb-7 flex items-end justify-between gap-6">
        <div>
          <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-violet-300/80">
            Idea Queue
          </p>
          <h2 className="text-3xl font-semibold tracking-tight text-neutral-100">
            Ideas
          </h2>
        </div>
        {ideas.length > 0 && (
          <div className="rounded-full border border-neutral-800 bg-neutral-900/80 px-3 py-1 text-xs font-medium text-neutral-400">
            {ideas.length} saved
          </div>
        )}
      </div>

      {/* Quick-add bar */}
      <div className="group flex items-center gap-3 rounded-xl border border-neutral-800 bg-neutral-900/80 p-2 shadow-[0_18px_60px_rgba(0,0,0,0.24)] transition-colors focus-within:border-violet-500/60">
        <input
          type="text"
          value={newText}
          onChange={(e) => setNewText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Add a video idea..."
          className="min-h-10 flex-1 bg-transparent px-3 text-sm text-neutral-100 placeholder-neutral-500 focus:outline-none"
        />
        <button
          onClick={handleAdd}
          disabled={!newText.trim()}
          aria-label="Add idea"
          className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-violet-600 text-white transition-colors hover:bg-violet-500 disabled:cursor-not-allowed disabled:opacity-35 active:scale-[0.97] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950"
        >
          <Plus className="h-4 w-4" strokeWidth={2} />
        </button>
      </div>

      {categories.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-1.5">
          <button
            onClick={() => setCategoryFilter(null)}
            className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
              categoryFilter === null
                ? "bg-neutral-100 text-neutral-950"
                : "text-neutral-500 hover:bg-neutral-900 hover:text-neutral-300"
            }`}
          >
            All
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              onClick={() => setCategoryFilter(categoryFilter === cat ? null : cat)}
              className={`rounded-full px-3 py-1 text-xs font-medium transition-colors ${
                categoryFilter === cat
                  ? "bg-neutral-100 text-neutral-950"
                  : "text-neutral-500 hover:bg-neutral-900 hover:text-neutral-300"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      )}

      {/* Idea list */}
      {loading && ideas.length === 0 ? (
        <div className="py-16 text-center text-sm text-neutral-500">Loading...</div>
      ) : ideas.length === 0 ? (
        <div className="mt-10">
          <EmptyState
            icon={
              <svg className="w-full h-full" fill="none" viewBox="0 0 24 24" strokeWidth={1.2} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
              </svg>
            }
            title="No ideas yet"
            description="Add your first video idea above"
          />
        </div>
      ) : (
        <div className="mt-6 overflow-hidden rounded-2xl border border-neutral-800 bg-neutral-900/45">
          {ideas.map((idea) => (
            <SavedIdeaCard
              key={idea.id}
              idea={idea}
              onUpdate={handleUpdate}
              onDelete={handleDelete}
              onGenerateIdeas={onGenerateIdeas}
            />
          ))}
        </div>
      )}
    </div>
  );
}
