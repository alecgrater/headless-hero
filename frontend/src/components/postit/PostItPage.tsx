import { useCallback, useEffect, useMemo, useState } from "react";
import { getPostIts, createPostIt, updatePostIt, deletePostIt, getPostItCounts } from "../../api";
import type { PostIt, PostItStatus } from "../../types/postit";
import PostItCard from "./PostItCard";

const STATUS_FILTERS: { key: PostItStatus | "all"; label: string }[] = [
  { key: "all", label: "All" },
  { key: "idea", label: "Idea" },
  { key: "in_progress", label: "In Progress" },
  { key: "scripted", label: "Scripted" },
  { key: "published", label: "Published" },
];

interface Props {
  onGenerateIdeas: (niche: string) => void;
}

export default function PostItPage({ onGenerateIdeas }: Props) {
  const [postits, setPostits] = useState<PostIt[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [statusFilter, setStatusFilter] = useState<PostItStatus | "all">("all");
  const [newText, setNewText] = useState("");
  const [newRank, setNewRank] = useState(50);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [data, c] = await Promise.all([getPostIts(), getPostItCounts()]);
      setPostits(data);
      setCounts(c);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const refreshCounts = useCallback(async () => {
    const c = await getPostItCounts();
    setCounts(c);
  }, []);

  const handleAdd = async () => {
    const trimmed = newText.trim();
    if (!trimmed) return;
    const created = await createPostIt(trimmed, newRank);
    setPostits((prev) => {
      const next = [...prev, created];
      next.sort((a, b) => b.rank - a.rank || new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
      return next;
    });
    setNewText("");
    setNewRank(50);
    refreshCounts();
  };

  const handleUpdate = async (id: string, updates: { text?: string; rank?: number; status?: PostItStatus }) => {
    const updated = await updatePostIt(id, updates);
    setPostits((prev) => {
      const next = prev.map((p) => (p.id === id ? updated : p));
      next.sort((a, b) => b.rank - a.rank || new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
      return next;
    });
    if (updates.status) refreshCounts();
  };

  const handleDelete = async (id: string) => {
    await deletePostIt(id);
    setPostits((prev) => prev.filter((p) => p.id !== id));
    refreshCounts();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleAdd();
    }
  };

  const filteredPostits = useMemo(() => {
    if (statusFilter === "all") return postits;
    return postits.filter((p) => p.status === statusFilter);
  }, [postits, statusFilter]);

  return (
    <div className="max-w-3xl mx-auto px-6 py-8 space-y-6">
      <div>
        <h2 className="text-2xl font-bold mb-1">
          Post-Its
          {postits.length > 0 && (
            <span className="ml-2 text-base font-normal text-neutral-500">{postits.length}</span>
          )}
        </h2>
        <p className="text-neutral-400 text-sm">
          Jot down future video ideas. Rank them by priority and generate ideas with one click.
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
        <div className="flex items-center gap-2 shrink-0">
          <label className="text-xs text-neutral-500">Priority</label>
          <input
            type="range"
            min={1}
            max={100}
            value={newRank}
            onChange={(e) => setNewRank(Number(e.target.value))}
            className="w-20 accent-violet-500"
          />
          <span className="text-xs text-neutral-400 w-6 text-right">{newRank}</span>
        </div>
        <button
          onClick={handleAdd}
          disabled={!newText.trim()}
          className="text-sm px-4 py-1.5 rounded-lg bg-violet-600 hover:bg-violet-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-medium transition-colors"
        >
          Add
        </button>
      </div>

      {/* Status filter chips */}
      {postits.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          {STATUS_FILTERS.map(({ key, label }) => {
            const count = key === "all" ? postits.length : (counts[key] || 0);
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
      )}

      {/* Post-It list */}
      {loading && postits.length === 0 ? (
        <div className="text-center py-12 text-neutral-500 text-sm">Loading...</div>
      ) : filteredPostits.length === 0 && postits.length > 0 ? (
        <div className="text-center py-12 text-neutral-500 text-sm">
          No post-its with status &ldquo;{STATUS_FILTERS.find((f) => f.key === statusFilter)?.label}&rdquo;
        </div>
      ) : postits.length === 0 ? (
        <div className="text-center py-20 space-y-3">
          <div className="flex justify-center">
            <svg className="w-12 h-12 text-violet-500/40" fill="none" viewBox="0 0 24 24" strokeWidth={1.2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9.75a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
            </svg>
          </div>
          <p className="text-lg font-medium text-neutral-300">No post-its yet</p>
          <p className="text-sm text-neutral-500">Add your first video idea above</p>
        </div>
      ) : (
        <div className="space-y-2">
          {filteredPostits.map((postit) => (
            <PostItCard
              key={postit.id}
              postit={postit}
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
