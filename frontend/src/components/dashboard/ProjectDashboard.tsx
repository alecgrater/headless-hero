import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Grid2X2, List } from "lucide-react";
import api, { assetUrl, setUploadTracking } from "../../api";
import type { ScriptSummary, UploadTracking } from "../../types/script";
import { Button } from "../ui/Button";
import { EmptyState } from "../ui/EmptyState";
import { Tooltip } from "../ui/Tooltip";

interface Props {
  onNewVideo: () => void;
  onOpenProject: (scriptId: string) => void;
  isActive?: boolean;
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

type ProjectStateFilter = "unfinished" | "finished" | "uploaded";
type FilterValue = "all" | ProjectStateFilter;
type SortValue = "newest" | "oldest" | "title";
type ViewMode = "grid" | "rows";

const FILTER_OPTIONS: { value: FilterValue; label: string }[] = [
  { value: "all", label: "All" },
  { value: "unfinished", label: "Unfinished" },
  { value: "finished", label: "Finished" },
  { value: "uploaded", label: "Uploaded" },
];

const SORT_OPTIONS: { value: SortValue; label: string }[] = [
  { value: "newest", label: "Newest First" },
  { value: "oldest", label: "Oldest First" },
  { value: "title", label: "Title A-Z" },
];

function isFullyUploaded(project: ScriptSummary) {
  return (
    !!project.upload_tracking?.longform_youtube &&
    !!project.upload_tracking?.shortform_youtube &&
    !!project.upload_tracking?.shortform_instagram &&
    !!project.upload_tracking?.shortform_tiktok
  );
}

function getProjectState(project: ScriptSummary): ProjectStateFilter {
  if (project.status !== "exported") return "unfinished";
  return isFullyUploaded(project) ? "uploaded" : "finished";
}

function ProjectThumbnail({ project, compact = false }: { project: ScriptSummary; compact?: boolean }) {
  return (
    <div className={`${compact ? "w-28 h-16 rounded-lg" : "aspect-video rounded-t-xl"} bg-neutral-900 relative overflow-hidden shrink-0`}>
      {project.thumbnail_url ? (
        <img
          src={assetUrl(project.thumbnail_url)}
          alt=""
          className="w-full h-full object-cover"
        />
      ) : (
        <div className="w-full h-full bg-gradient-to-br from-violet-950/60 via-neutral-900 to-neutral-900 flex items-center justify-center text-neutral-600">
          <svg className={compact ? "w-6 h-6" : "w-10 h-10"} fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="m15.75 10.5 4.72-4.72a.75.75 0 0 1 1.28.53v11.38a.75.75 0 0 1-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25h-9A2.25 2.25 0 0 0 2.25 7.5v9a2.25 2.25 0 0 0 2.25 2.25Z" />
          </svg>
        </div>
      )}
    </div>
  );
}

function UploadIndicators({
  project,
  onToggle,
  pendingKey,
}: {
  project: ScriptSummary;
  onToggle: (project: ScriptSummary, key: keyof UploadTracking) => void;
  pendingKey: keyof UploadTracking | null;
}) {
  const handleClick = (e: React.MouseEvent, key: keyof UploadTracking) => {
    e.stopPropagation();
    if (pendingKey) return;
    onToggle(project, key);
  };
  const baseBtn = "transition-opacity hover:opacity-80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 rounded-sm disabled:cursor-wait";
  return (
    <div className="flex items-center gap-2">
      <Tooltip content={project.upload_tracking?.longform_youtube ? "Uploaded to YouTube — click to mark unpublished" : "Not yet on YouTube — click to mark published"}>
        <button
          type="button"
          onClick={(e) => handleClick(e, "longform_youtube")}
          disabled={pendingKey === "longform_youtube"}
          aria-label="Toggle YouTube long-form publish state"
          aria-pressed={!!project.upload_tracking?.longform_youtube}
          className={baseBtn}
        >
          <svg
            className={`w-4 h-4 ${project.upload_tracking?.longform_youtube ? "text-red-500" : "text-neutral-600"}`}
            viewBox="0 0 24 24"
            fill={project.upload_tracking?.longform_youtube ? "currentColor" : "none"}
            stroke={project.upload_tracking?.longform_youtube ? "none" : "currentColor"}
            strokeWidth={1.5}
          >
            <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0C.488 3.45.029 5.804 0 12c.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0C23.512 20.55 23.971 18.196 24 12c-.029-6.185-.484-8.549-4.385-8.816zM9 16V8l8 4-8 4z" />
          </svg>
        </button>
      </Tooltip>
      <Tooltip content={project.upload_tracking?.shortform_youtube ? "Shorts uploaded to YouTube — click to mark unpublished" : "Shorts not yet on YouTube — click to mark published"}>
        <button
          type="button"
          onClick={(e) => handleClick(e, "shortform_youtube")}
          disabled={pendingKey === "shortform_youtube"}
          aria-label="Toggle YouTube Shorts publish state"
          aria-pressed={!!project.upload_tracking?.shortform_youtube}
          className={baseBtn}
        >
          <svg
            className={`w-4 h-4 ${project.upload_tracking?.shortform_youtube ? "text-red-400" : "text-neutral-600"}`}
            viewBox="0 0 24 24"
            fill={project.upload_tracking?.shortform_youtube ? "currentColor" : "none"}
            stroke={project.upload_tracking?.shortform_youtube ? "none" : "currentColor"}
            strokeWidth={1.5}
          >
            <path d="M14.4 12c0 1.33-.53 2.53-1.4 3.4-.87.87-2.07 1.4-3.4 1.4a4.8 4.8 0 1 1 4.8-4.8zM10.8 7.2a7.2 7.2 0 1 0 0 14.4 7.2 7.2 0 0 0 0-14.4zM21 2l-4 4h3v7h-3l4 4V2z" />
          </svg>
        </button>
      </Tooltip>
      <Tooltip content={project.upload_tracking?.shortform_instagram ? "Uploaded to Instagram — click to mark unpublished" : "Not yet on Instagram — click to mark published"}>
        <button
          type="button"
          onClick={(e) => handleClick(e, "shortform_instagram")}
          disabled={pendingKey === "shortform_instagram"}
          aria-label="Toggle Instagram publish state"
          aria-pressed={!!project.upload_tracking?.shortform_instagram}
          className={baseBtn}
        >
          <svg
            className={`w-4 h-4 ${project.upload_tracking?.shortform_instagram ? "text-pink-500" : "text-neutral-600"}`}
            viewBox="0 0 24 24"
            fill={project.upload_tracking?.shortform_instagram ? "currentColor" : "none"}
            stroke={project.upload_tracking?.shortform_instagram ? "none" : "currentColor"}
            strokeWidth={1.5}
          >
            <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z" />
          </svg>
        </button>
      </Tooltip>
      <Tooltip content={project.upload_tracking?.shortform_tiktok ? "Uploaded to TikTok — click to mark unpublished" : "Not yet on TikTok — click to mark published"}>
        <button
          type="button"
          onClick={(e) => handleClick(e, "shortform_tiktok")}
          disabled={pendingKey === "shortform_tiktok"}
          aria-label="Toggle TikTok publish state"
          aria-pressed={!!project.upload_tracking?.shortform_tiktok}
          className={baseBtn}
        >
          <svg
            className={`w-4 h-4 ${project.upload_tracking?.shortform_tiktok ? "text-neutral-100" : "text-neutral-600"}`}
            viewBox="0 0 24 24"
            fill={project.upload_tracking?.shortform_tiktok ? "currentColor" : "none"}
            stroke={project.upload_tracking?.shortform_tiktok ? "none" : "currentColor"}
            strokeWidth={1.5}
          >
            <path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-2.88 2.5 2.89 2.89 0 01-2.89-2.89 2.89 2.89 0 012.89-2.89c.28 0 .54.04.79.1V9.01a6.27 6.27 0 00-.79-.05 6.34 6.34 0 00-6.34 6.34 6.34 6.34 0 006.34 6.34 6.34 6.34 0 006.33-6.34V8.95a8.19 8.19 0 004.79 1.53V7.03a4.85 4.85 0 01-1.02-.34z" />
          </svg>
        </button>
      </Tooltip>
    </div>
  );
}

export default function ProjectDashboard({ onNewVideo, onOpenProject, isActive = true }: Props) {
  const [projects, setProjects] = useState<ScriptSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeFilter, setActiveFilter] = useState<FilterValue>("all");
  const [sortBy, setSortBy] = useState<SortValue>("newest");
  const [search, setSearch] = useState("");
  const [viewMode, setViewMode] = useState<ViewMode>("grid");
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [pendingToggle, setPendingToggle] = useState<{ scriptId: string; key: keyof UploadTracking } | null>(null);

  const handleToggleUpload = useCallback(async (project: ScriptSummary, key: keyof UploadTracking) => {
    if (pendingToggle) return;
    const current = !!project.upload_tracking?.[key];
    const next = !current;
    setPendingToggle({ scriptId: project.id, key });
    // Optimistic update
    setProjects((prev) =>
      prev.map((p) =>
        p.id === project.id
          ? { ...p, upload_tracking: { ...p.upload_tracking, [key]: next } }
          : p,
      ),
    );
    try {
      const updated = await setUploadTracking(project.id, { [key]: next });
      setProjects((prev) =>
        prev.map((p) => (p.id === project.id ? { ...p, upload_tracking: updated } : p)),
      );
    } catch {
      // Revert on failure
      setProjects((prev) =>
        prev.map((p) =>
          p.id === project.id
            ? { ...p, upload_tracking: { ...p.upload_tracking, [key]: current } }
            : p,
        ),
      );
    } finally {
      setPendingToggle(null);
    }
  }, [pendingToggle]);

  const fetchProjects = useCallback(async () => {
    setLoading(true);
    const res = await api.get("/api/scripts");
    if (res.ok) setProjects(res.data as ScriptSummary[]);
    setLoading(false);
  }, []);

  useEffect(() => {
    if (isActive) fetchProjects();
  }, [fetchProjects, isActive]);

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
      result = result.filter((p) => getProjectState(p) === activeFilter);
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
  const unfinishedCount = projects.filter((p) => getProjectState(p) === "unfinished").length;
  const finishedCount = projects.filter((p) => getProjectState(p) === "finished").length;
  const uploadedCount = projects.filter((p) => getProjectState(p) === "uploaded").length;

  return (
    <div className="px-6 py-8 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-neutral-100">Projects</h1>
          {!loading && projects.length > 0 && (
            <p className="text-sm text-neutral-500 mt-0.5">
              {projects.length} {projects.length === 1 ? "project" : "projects"}
              {" · "}{unfinishedCount} unfinished
              {" · "}{finishedCount} finished
              {" · "}{uploadedCount} uploaded
            </p>
          )}
        </div>
        <Button
          variant="primary"
          onClick={onNewVideo}
          icon={
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
            </svg>
          }
        >
          New Video
        </Button>
      </div>

      {/* Loading */}
      {loading && (
        <div className="text-center py-16 text-neutral-400">Loading projects...</div>
      )}

      {/* Empty state */}
      {!loading && projects.length === 0 && (
        <EmptyState
          icon={
            <svg className="w-full h-full" fill="none" viewBox="0 0 24 24" strokeWidth={1} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="m15.75 10.5 4.72-4.72a.75.75 0 0 1 1.28.53v11.38a.75.75 0 0 1-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25h-9A2.25 2.25 0 0 0 2.25 7.5v9a2.25 2.25 0 0 0 2.25 2.25Z" />
            </svg>
          }
          title="No videos yet"
          description="Create your first video to get started."
          action={{ label: "Create Your First Video", onClick: onNewVideo }}
        />
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

            {/* View toggle */}
            <div className="flex items-center rounded-lg border border-neutral-700 bg-neutral-900/70 p-0.5">
              <Tooltip content="Grid view">
                <button
                  type="button"
                  onClick={() => setViewMode("grid")}
                  className={`h-8 w-8 flex items-center justify-center rounded-md transition-colors ${
                    viewMode === "grid"
                      ? "bg-neutral-700 text-neutral-100"
                      : "text-neutral-500 hover:bg-neutral-800 hover:text-neutral-300"
                  }`}
                  aria-label="Grid view"
                  aria-pressed={viewMode === "grid"}
                >
                  <Grid2X2 className="w-4 h-4" strokeWidth={2} />
                </button>
              </Tooltip>
              <Tooltip content="Row view">
                <button
                  type="button"
                  onClick={() => setViewMode("rows")}
                  className={`h-8 w-8 flex items-center justify-center rounded-md transition-colors ${
                    viewMode === "rows"
                      ? "bg-neutral-700 text-neutral-100"
                      : "text-neutral-500 hover:bg-neutral-800 hover:text-neutral-300"
                  }`}
                  aria-label="Row view"
                  aria-pressed={viewMode === "rows"}
                >
                  <List className="w-4 h-4" strokeWidth={2} />
                </button>
              </Tooltip>
            </div>

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
                className="w-48 pl-8 pr-3 py-1.5 rounded-lg bg-neutral-800 border border-neutral-700 text-sm text-neutral-200 placeholder:text-neutral-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 transition-colors"
              />
            </div>

            {/* Sort dropdown */}
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as SortValue)}
              className="px-3 py-1.5 rounded-lg bg-neutral-800 border border-neutral-700 text-sm text-neutral-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-violet-500 focus-visible:ring-offset-2 focus-visible:ring-offset-neutral-950 transition-colors"
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
          {filteredProjects.length > 0 && viewMode === "grid" && (
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
                  <div className="relative">
                    <ProjectThumbnail project={project} />

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
                        className="w-7 h-7 flex items-center justify-center rounded-md text-neutral-500 hover:text-neutral-300 hover:bg-neutral-700 transition-all opacity-0 group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
                        aria-label="More options"
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
                          <Tooltip content="Predicted engagement score based on title and hook strength">
                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                              project.hook_score_overall >= 80
                                ? "bg-emerald-500/20 text-emerald-300"
                                : project.hook_score_overall >= 50
                                  ? "bg-amber-500/20 text-amber-300"
                                  : "bg-red-500/20 text-red-300"
                            }`}>
                              Hook {project.hook_score_overall}
                            </span>
                          </Tooltip>
                        )}
                      </span>
                      <span className="flex items-center gap-1.5">
                        <span className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT_COLORS[project.status]}`} />
                        {formatDate(project.created_at)}
                      </span>
                    </div>
                    {/* Platform upload indicators */}
                    <div className="pt-1.5">
                      <UploadIndicators
                        project={project}
                        onToggle={handleToggleUpload}
                        pendingKey={pendingToggle?.scriptId === project.id ? pendingToggle.key : null}
                      />
                    </div>

                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Project rows */}
          {filteredProjects.length > 0 && viewMode === "rows" && (
            <div className="overflow-x-auto rounded-xl border border-neutral-800 bg-neutral-900/40">
              <div className="min-w-[820px] grid grid-cols-[112px_minmax(0,1fr)_120px_120px_110px_96px_40px] gap-4 px-4 py-2.5 text-[11px] font-medium uppercase tracking-wide text-neutral-500 border-b border-neutral-800">
                <span>Preview</span>
                <span>Project</span>
                <span>Status</span>
                <span>Structure</span>
                <span>Published</span>
                <span>Created</span>
                <span className="sr-only">Actions</span>
              </div>
              <div className="divide-y divide-neutral-800">
                {filteredProjects.map((project) => (
                  <div
                    key={project.id}
                    role="button"
                    tabIndex={0}
                    onClick={() => onOpenProject(project.id)}
                    onKeyDown={(e) => { if (e.key === "Enter") onOpenProject(project.id); }}
                    className="group min-w-[820px] grid grid-cols-[112px_minmax(0,1fr)_120px_120px_110px_96px_40px] gap-4 px-4 py-3 items-center bg-neutral-900/20 hover:bg-neutral-800/60 transition-colors cursor-pointer"
                  >
                    <ProjectThumbnail project={project} compact />
                    <div className="min-w-0">
                      <h3 className="font-medium text-neutral-100 truncate group-hover:text-violet-300 transition-colors">
                        {project.topic_title || "Untitled"}
                      </h3>
                      <p className="text-sm text-neutral-500 truncate mt-0.5">
                        {project.topic_description || "No description"}
                      </p>
                    </div>
                    <div className="flex flex-col items-start gap-1.5">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[project.status]}`}>
                        {STATUS_LABELS[project.status]}
                      </span>
                      {project.hook_score_overall != null && (
                        <Tooltip content="Predicted engagement score based on title and hook strength">
                          <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                            project.hook_score_overall >= 80
                              ? "bg-emerald-500/20 text-emerald-300"
                              : project.hook_score_overall >= 50
                                ? "bg-amber-500/20 text-amber-300"
                                : "bg-red-500/20 text-red-300"
                          }`}>
                            Hook {project.hook_score_overall}
                          </span>
                        </Tooltip>
                      )}
                    </div>
                    <div className="text-sm text-neutral-400">
                      <div>{project.segment_count} segments</div>
                      <div className="text-xs text-neutral-600">{project.scene_count} scenes</div>
                    </div>
                    <UploadIndicators
                      project={project}
                      onToggle={handleToggleUpload}
                      pendingKey={pendingToggle?.scriptId === project.id ? pendingToggle.key : null}
                    />
                    <div className="flex items-center gap-1.5 text-xs text-neutral-500">
                      <span className={`w-1.5 h-1.5 rounded-full ${STATUS_DOT_COLORS[project.status]}`} />
                      {formatDate(project.created_at)}
                    </div>
                    <div className="relative" ref={openMenuId === project.id ? menuRef : undefined}>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setOpenMenuId(openMenuId === project.id ? null : project.id);
                        }}
                        className="w-8 h-8 flex items-center justify-center rounded-md text-neutral-500 hover:text-neutral-300 hover:bg-neutral-700 transition-all opacity-0 group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-500"
                        aria-label="More options"
                      >
                        <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                          <path d="M10 6a2 2 0 110-4 2 2 0 010 4zm0 6a2 2 0 110-4 2 2 0 010 4zm0 6a2 2 0 110-4 2 2 0 010 4z" />
                        </svg>
                      </button>

                      {openMenuId === project.id && (
                        <div className="absolute right-0 top-9 w-36 bg-neutral-800 border border-neutral-700 rounded-lg shadow-xl shadow-black/40 py-1 z-20">
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
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
