import { useCallback, useEffect, useState } from "react";
import {
  getIdeas,
  createIdea,
  updateIdea,
  deleteIdea,
  getIdeaCounts,
  getIdeaCategories,
} from "../../api";
import type { Idea, IdeaStatus } from "../../types/idea";
import IdeaCard from "./IdeaCard";
import { EmptyState } from "../ui/EmptyState";

const STATUS_FILTERS: { key: IdeaStatus | "all"; label: string }[] = [
  { key: "all", label: "All" },
  { key: "idea", label: "Idea" },
  { key: "in_progress", label: "In Progress" },
  { key: "scripted", label: "Scripted" },
  { key: "published", label: "Published" },
];

const SORT_OPTIONS: { key: string; label: string }[] = [
  { key: "hook_score", label: "Hook Score" },
  { key: "rank", label: "Priority" },
  { key: "newest", label: "Newest" },
];

interface Props {
  onGenerateIdeas: (niche: string) => void;
}

export default function IdeaPage({ onGenerateIdeas }: Props) {
  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [statusFilter, setStatusFilter] = useState<IdeaStatus | "all">("all");
  const [sortBy, setSortBy] = useState("hook_score");
  const [categories, setCategories] = useState<string[]>([]);
  const [categoryFilter, setCategoryFilter] = useState<string | null>(null);
  const [newText, setNewText] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [data, c, cats] = await Promise.all([
        getIdeas(sortBy, categoryFilter ?? undefined, statusFilter === "all" ? undefined : statusFilter),
        getIdeaCounts(),
        getIdeaCategories(),
      ]);
      setIdeas(data);
      setCounts(c);
      setCategories(cats);
    } finally {
      setLoading(false);
    }
  }, [sortBy, categoryFilter, statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const refreshCounts = useCallback(async () => {
    const [c, cats] = await Promise.all([getIdeaCounts(), getIdeaCategories()]);
    setCounts(c);
    setCategories(cats);
  }, []);

  const handleAdd = async () => {
    const trimmed = newText.trim();
    if (!trimmed) return;
    try {
      const created = await createIdea(trimmed);
      setIdeas((prev) => [created, ...prev]);
      setNewText("");
      refreshCounts();
    } catch { /* toast shown by interceptor */ }
  };

  const handleUpdate = async (id: string, updates: { text?: string; rank?: number; status?: IdeaStatus }) => {
    try {
      const updated = await updateIdea(id, updates);
      setIdeas((prev) => prev.map((i) => (i.id === id ? updated : i)));
      if (updates.status) refreshCounts();
    } catch { /* toast shown by interceptor */ }
  };

  const handleDelete = async (id: string) => {
    try {
      await deleteIdea(id);
      setIdeas((prev) => prev.filter((i) => i.id !== id));
      refreshCounts();
    } catch { /* toast shown by interceptor */ }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleAdd();
    }
  };

  return (
    <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
      <div>
        <h2 className="text-2xl font-bold mb-1">
          Ideas
          {ideas.length > 0 && (
            <span className="ml-2 text-base font-normal text-neutral-500">{ideas.length}</span>
          )}
        </h2>
        <p className="text-neutral-400 text-sm">
          Save video ideas. Each gets auto-scored with 3 cold openings.
        </p>
      </div>

      {/* Quick-add bar */}
      <div className="flex items-center gap-3 rounded-lg border border-neutral-700 bg-neutral-800/50 p-3">
        <input
          type="text"
          value={newText}
          onChange={(e) => setNewText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Add a video idea..."
          className="flex-1 bg-transparent text-sm text-neutral-100 placeholder-neutral-500 focus:outline-none"
        />
        <button
          onClick={handleAdd}
          disabled={!newText.trim()}
          className="text-sm px-4 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-medium transition-colors active:scale-[0.97] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950"
        >
          Add
        </button>
      </div>

      {/* Sort + filter row */}
      {ideas.length > 0 && (
        <div className="flex items-center gap-4 flex-wrap">
          {/* Sort dropdown */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-neutral-500">Sort:</span>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="text-xs bg-neutral-800 border border-neutral-700 rounded-lg px-2 py-1.5 text-neutral-300 focus:outline-none focus:border-violet-500"
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.key} value={opt.key}>{opt.label}</option>
              ))}
            </select>
          </div>

          {/* Status filter chips */}
          <div className="flex items-center gap-2 flex-wrap">
            {STATUS_FILTERS.map(({ key, label }) => {
              const count = key === "all"
                ? Object.values(counts).reduce((sum, n) => sum + n, 0)
                : (counts[key] || 0);
              return (
                <button
                  key={key}
                  onClick={() => setStatusFilter(key)}
                  className={`text-xs font-medium px-3 py-1.5 rounded-lg transition-colors ${
                    statusFilter === key
                      ? "bg-violet-600 text-white"
                      : "bg-neutral-800 text-neutral-400 border border-neutral-700/60 hover:text-neutral-200 hover:border-neutral-600"
                  }`}
                >
                  {label} ({count})
                </button>
              );
            })}
          </div>

          {/* Category filter chips */}
          {categories.length > 0 && (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs text-neutral-500">Category:</span>
              <button
                onClick={() => setCategoryFilter(null)}
                className={`text-xs font-medium px-2.5 py-1 rounded-lg transition-colors ${
                  categoryFilter === null
                    ? "bg-sky-600 text-white"
                    : "bg-neutral-800 text-neutral-400 border border-neutral-700/60 hover:text-neutral-200 hover:border-neutral-600"
                }`}
              >
                All
              </button>
              {categories.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setCategoryFilter(categoryFilter === cat ? null : cat)}
                  className={`text-xs font-medium px-2.5 py-1 rounded-lg transition-colors ${
                    categoryFilter === cat
                      ? "bg-sky-600 text-white"
                      : "bg-neutral-800 text-neutral-400 border border-neutral-700/60 hover:text-neutral-200 hover:border-neutral-600"
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Idea list */}
      {loading && ideas.length === 0 ? (
        <div className="text-center py-12 text-neutral-500 text-sm">Loading...</div>
      ) : ideas.length === 0 ? (
        <EmptyState
          icon={
            <svg className="w-full h-full" fill="none" viewBox="0 0 24 24" strokeWidth={1.2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18" />
            </svg>
          }
          title="No ideas yet"
          description="Add your first video idea above"
        />
      ) : (
        <div className="space-y-2">
          {ideas.map((idea) => (
            <IdeaCard
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
