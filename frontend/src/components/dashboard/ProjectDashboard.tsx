import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import api, { assetUrl } from "../../api";
import type { ScriptSummary } from "../../types/script";

interface Props {
  onNewVideo: () => void;
  onOpenProject: (scriptId: string) => void;
}

const STATUS_LABELS: Record<ScriptSummary["status"], string> = {
  script: "Script",
  images: "Images",
  audio: "Audio",
  exported: "Exported",
};

const STATUS_COLORS: Record<ScriptSummary["status"], string> = {
  script: "bg-neutral-600/80 text-neutral-300",
  images: "bg-blue-500/20 text-blue-300",
  audio: "bg-amber-500/20 text-amber-300",
  exported: "bg-emerald-500/20 text-emerald-300",
};

const STATUS_DOT_COLORS: Record<ScriptSummary["status"], string> = {
  script: "bg-neutral-400",
  images: "bg-blue-400",
  audio: "bg-amber-400",
  exported: "bg-emerald-400",
};

type FilterValue = "all" | ScriptSummary["status"];
type SortValue = "newest" | "oldest" | "title";

const FILTER_OPTIONS: { value: FilterValue; label: string }[] = [
  { value: "all", label: "All" },
  { value: "exported", label: "Exported" },
];

const SORT_OPTIONS: { value: SortValue; label: string }[] = [
  { value: "newest", label: "Newest First" },
  { value: "oldest", label: "Oldest First" },
  { value: "title", label: "Title A-Z" },
];

export default function ProjectDashboard({ onNewVideo, onOpenProject }: Props) {
  const [projects, setProjects] = useState<ScriptSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState<FilterValue>("all");
  const [sortBy, setSortBy] = useState<SortValue>("newest");
  const [search, setSearch] = useState("");
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const fetchProjects = useCallback(async () => {
    setLoading(true);
    const res = await api.get("/api/scripts");
    if (res.ok) setProjects(res.data as ScriptSummary[]);
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  // Close overflow menu on outside click or Escape
  useEffect(() => {
    if (!openMenuId) return;
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setOpenMenuId(null);
      }
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpenMenuId(null);
    };
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [openMenuId]);

  const handleDelete = async (e: React.MouseEvent, project: ScriptSummary) => {
    e.stopPropagation();
    setOpenMenuId(null);
    if (!confirm(`Delete "${project.topic_title}"? This will remove all generated media.`)) return;
    const res = await api.delete(`/api/scripts/${project.id}`);
    if (res.ok) {
      setProjects((prev) => prev.filter((p) => p.id !== project.id));
    }
  };

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  };

  // Filtered + sorted projects
  const filteredProjects = useMemo(() => {
    let result = [...projects];

    // Search filter
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter(
        (p) =>
          p.topic_title.toLowerCase().includes(q) ||
          p.topic_description.toLowerCase().includes(q),
      );
    }

    // Status filter
    if (activeFilter !== "all") {
      result = result.filter((p) => p.status === activeFilter);
    }

    // Sort
    if (sortBy === "newest") {
      result.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    } else if (sortBy === "oldest") {
      result.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime());
    } else {
      result.sort((a, b) => (a.topic_title || "").localeCompare(b.topic_title || ""));
    }

    return result;
  }, [projects, search, activeFilter, sortBy]);

  // Stats for header
  const exportedCount = projects.filter((p) => p.status === "exported").length;
  const draftCount = projects.length - exportedCount;

  return (
    <div className="px-6 py-8 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-neutral-100">Projects</h1>
          {!loading && projects.length > 0 && (
            <p className="text-sm text-neutral-500 mt-0.5">
              {projects.length} {projects.length === 1 ? "project" : "projects"}
              {" · "}{exportedCount} exported
              {" · "}{draftCount} draft
            </p>
          )}
        </div>
        <button
          onClick={onNewVideo}
          className="btn-primary px-4 py-2 rounded-lg flex items-center gap-2"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
          </svg>
          New Video
        </button>
      </div>

      {/* Loading */}
      {loading && (
        <div className="text-center py-16 text-neutral-400">Loading projects...</div>
      )}

      {/* Empty state */}
      {!loading && projects.length === 0 && (
        <div className="text-center py-20 space-y-4">
          <div className="text-neutral-600">
            <svg className="w-16 h-16 mx-auto" fill="none" viewBox="0 0 24 24" strokeWidth={1} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="m15.75 10.5 4.72-4.72a.75.75 0 0 1 1.28.53v11.38a.75.75 0 0 1-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25h-9A2.25 2.25 0 0 0 2.25 7.5v9a2.25 2.25 0 0 0 2.25 2.25Z" />
            </svg>
          </div>
          <h2 className="text-xl font-semibold text-neutral-300">No videos yet</h2>
          <p className="text-neutral-500 max-w-sm mx-auto">
            Create your first video to get started.
          </p>
          <button
            onClick={onNewVideo}
            className="px-5 py-2.5 bg-violet-600 hover:bg-violet-500 rounded-lg font-medium transition-colors"
          >
            Create Your First Video
          </button>
        </div>
      )}

      {/* Filter bar + grid */}
      {!loading && projects.length > 0 && (
        <>
          {/* Filter Bar */}
          <div className="flex flex-wrap items-center gap-3">
            {/* Filter pills */}
            <div className="flex flex-wrap items-center gap-1.5">
              {FILTER_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  onClick={() => setActiveFilter(opt.value)}
                  className={`px-3.5 py-1.5 rounded-full text-sm font-medium transition-colors ${
                    activeFilter === opt.value
                      ? "bg-violet-600 text-white shadow-sm shadow-violet-500/25"
                      : "bg-neutral-800/60 text-neutral-400 hover:bg-neutral-700 hover:text-neutral-300"
                  }`}
                >
                  {opt.label}
                </button>
              ))}
            </div>

            <div className="flex-1" />

            {/* Search */}
            <div className="relative">
              <svg
                className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-neutral-500"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607Z" />
              </svg>
              <input
                type="text"
                placeholder="Search projects..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-48 pl-8 pr-3 py-1.5 rounded-lg bg-neutral-800 border border-neutral-700 text-sm text-neutral-200 placeholder:text-neutral-500 focus:outline-none focus:border-violet-500/50 transition-colors"
              />
            </div>

            {/* Sort dropdown */}
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortValue)}
              className="px-3 py-1.5 rounded-lg bg-neutral-800 border border-neutral-700 text-sm text-neutral-300 focus:outline-none focus:border-violet-500/50 transition-colors"
            >
              {SORT_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* No results for filters */}
          {filteredProjects.length === 0 && (
            <div className="text-center py-16 space-y-2">
              <p className="text-neutral-400">No projects match your filters.</p>
              <button
                onClick={() => { setActiveFilter("all"); setSearch(""); }}
                className="text-sm text-violet-400 hover:text-violet-300 transition-colors"
              >
                Clear filters
              </button>
            </div>
          )}

          {/* Project grid */}
          {filteredProjects.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredProjects.map((project) => (
                <div
                  key={project.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => onOpenProject(project.id)}
                  onKeyDown={(e) => { if (e.key === "Enter") onOpenProject(project.id); }}
                  className="group text-left bg-neutral-800/50 border border-neutral-700 rounded-xl hover:border-violet-500/50 hover:bg-neutral-800 hover:-translate-y-1 hover:shadow-xl hover:shadow-black/30 transition-all duration-200 cursor-pointer"
                >
                  {/* Thumbnail */}
                  <div className="aspect-video bg-neutral-900 relative overflow-hidden rounded-t-xl">
                    {project.thumbnail_url ? (
                      <img
                        src={assetUrl(project.thumbnail_url)}
                        alt=""
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <div className="w-full h-full bg-gradient-to-br from-violet-950/60 via-neutral-900 to-neutral-900 flex items-center justify-center text-neutral-600">
                        <svg className="w-10 h-10" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" d="m15.75 10.5 4.72-4.72a.75.75 0 0 1 1.28.53v11.38a.75.75 0 0 1-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25h-9A2.25 2.25 0 0 0 2.25 7.5v9a2.25 2.25 0 0 0 2.25 2.25Z" />
                        </svg>
                      </div>
                    )}

                    {/* Bottom gradient fade */}
                    <div className="absolute inset-x-0 bottom-0 h-12 bg-gradient-to-t from-neutral-900 to-transparent pointer-events-none" />

                    {/* Status badge — top-left */}
                    <span className={`absolute top-2 left-2 px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[project.status]}`}>
                      {STATUS_LABELS[project.status]}
                    </span>

                    {/* Hover overlay with Open button */}
                    <div className="absolute inset-0 bg-black/50 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-200">
                      <span className="px-4 py-1.5 rounded-lg bg-violet-600 text-sm font-medium text-white shadow-lg">
                        Open
                      </span>
                    </div>
                  </div>

                  {/* Card body */}
                  <div className="p-4 pb-3 space-y-1.5 relative">
                    {/* Overflow menu trigger */}
                    <div className="absolute top-3 right-3 z-10">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setOpenMenuId(openMenuId === project.id ? null : project.id);
                        }}
                        className="w-7 h-7 flex items-center justify-center rounded-md text-neutral-500 hover:text-neutral-300 hover:bg-neutral-700 transition-colors"
                        title="More options"
                      >
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M10 6a2 2 0 110-4 2 2 0 010 4zm0 6a2 2 0 110-4 2 2 0 010 4zm0 6a2 2 0 110-4 2 2 0 010 4z" />
                        </svg>
                      </button>

                      {/* Dropdown menu */}
                      {openMenuId === project.id && (
                        <div
                          ref={menuRef}
                          className="absolute right-0 top-8 w-36 bg-neutral-800 border border-neutral-700 rounded-lg shadow-xl shadow-black/40 py-1 z-20"
                        >
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setOpenMenuId(null);
                              onOpenProject(project.id);
                            }}
                            className="w-full text-left px-3 py-1.5 text-sm text-neutral-200 hover:bg-neutral-700 transition-colors"
                          >
                            Open
                          </button>
                          <div className="border-t border-neutral-700 my-1" />
                          <button
                            onClick={(e) => handleDelete(e, project)}
                            className="w-full text-left px-3 py-1.5 text-sm text-red-400 hover:bg-neutral-700 transition-colors"
                          >
                            Delete
                          </button>
                        </div>
                      )}
                    </div>

                    <h3 className="font-semibold text-neutral-100 line-clamp-2 pr-8 group-hover:text-violet-300 transition-colors leading-snug">
                      {project.topic_title || "Untitled"}
                    </h3>
                    <p className="text-sm text-neutral-500 truncate">
                      {project.topic_description || "No description"}
                    </p>
                    <div className="flex items-center justify-between text-xs text-neutral-500 pt-1">
                      <span className="flex items-center gap-2">
                        <span>{project.segment_count} segments &middot; {project.scene_count} scenes</span>
                        {project.hook_score_overall != null && (
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                            project.hook_score_overall >= 80
                              ? "bg-emerald-500/20 text-emerald-300"
                              : project.hook_score_overall >= 50
                                ? "bg-amber-500/20 text-amber-300"
                                : "bg-red-500/20 text-red-300"
                          }`} title="Hook retention score">
                            Hook {project.hook_score_overall}
                          </span>
                        )}
                      </span>
                      <span className="flex items-center gap-1.5">
                        <span className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT_COLORS[project.status]}`} />
                        {formatDate(project.created_at)}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
