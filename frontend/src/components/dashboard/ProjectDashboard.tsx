import { useCallback, useEffect, useState } from "react";
import api, { assetUrl } from "../../api";
import type { BrandProfile } from "../../types/brand";
import type { ScriptSummary } from "../../types/script";

interface Props {
  brand: BrandProfile;
  onNewVideo: () => void;
  onOpenProject: (scriptId: string) => void;
  onBack: () => void;
}

const STATUS_LABELS: Record<ScriptSummary["status"], string> = {
  script: "Script",
  images: "Images",
  audio: "Audio",
  exported: "Exported",
};

const STATUS_COLORS: Record<ScriptSummary["status"], string> = {
  script: "bg-neutral-600 text-neutral-200",
  images: "bg-blue-600/80 text-blue-100",
  audio: "bg-amber-600/80 text-amber-100",
  exported: "bg-emerald-600/80 text-emerald-100",
};

export default function ProjectDashboard({ brand, onNewVideo, onOpenProject, onBack }: Props) {
  const [projects, setProjects] = useState<ScriptSummary[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchProjects = useCallback(async () => {
    setLoading(true);
    const res = await api.get(`/api/scripts?brand_id=${brand.id}`);
    if (res.ok) setProjects(res.data as ScriptSummary[]);
    setLoading(false);
  }, [brand.id]);

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const handleDelete = async (e: React.MouseEvent, project: ScriptSummary) => {
    e.stopPropagation();
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

  return (
    <div className="px-6 py-8 max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <button
            onClick={onBack}
            className="text-neutral-400 hover:text-neutral-200 transition-colors"
            title="Back to brands"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
            </svg>
          </button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">{brand.name}</h1>
            <p className="text-sm text-neutral-400">
              {projects.length} {projects.length === 1 ? "project" : "projects"}
            </p>
          </div>
        </div>
        <button
          onClick={onNewVideo}
          className="px-4 py-2 bg-violet-600 hover:bg-violet-500 rounded-lg font-medium transition-colors flex items-center gap-2"
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
            Create your first video for {brand.name} to get started.
          </p>
          <button
            onClick={onNewVideo}
            className="px-5 py-2.5 bg-violet-600 hover:bg-violet-500 rounded-lg font-medium transition-colors"
          >
            Create Your First Video
          </button>
        </div>
      )}

      {/* Project grid */}
      {!loading && projects.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {projects.map((project) => (
            <button
              key={project.id}
              onClick={() => onOpenProject(project.id)}
              className="group text-left bg-neutral-800/50 border border-neutral-700 rounded-xl overflow-hidden hover:border-violet-500/50 hover:bg-neutral-800 transition-all"
            >
              {/* Thumbnail */}
              <div className="aspect-video bg-neutral-900 relative overflow-hidden">
                {project.thumbnail_url ? (
                  <img
                    src={assetUrl(project.thumbnail_url)}
                    alt=""
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-neutral-700">
                    <svg className="w-12 h-12" fill="none" viewBox="0 0 24 24" strokeWidth={1} stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" d="m2.25 15.75 5.159-5.159a2.25 2.25 0 0 1 3.182 0l5.159 5.159m-1.5-1.5 1.409-1.409a2.25 2.25 0 0 1 3.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0 0 22.5 18.75V5.25A2.25 2.25 0 0 0 20.25 3H3.75A2.25 2.25 0 0 0 1.5 5.25v13.5A2.25 2.25 0 0 0 3.75 21Z" />
                    </svg>
                  </div>
                )}
                {/* Status badge */}
                <span className={`absolute top-2 right-2 px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLORS[project.status]}`}>
                  {STATUS_LABELS[project.status]}
                </span>
                {/* Format badge */}
                {project.content_format === "shortform" && (
                  <span className="absolute top-2 left-2 px-2 py-0.5 rounded text-xs font-medium bg-emerald-500/20 text-emerald-300">
                    Short-Form
                  </span>
                )}
              </div>

              {/* Card body */}
              <div className="p-4 space-y-2">
                <h3 className="font-semibold text-neutral-100 truncate group-hover:text-violet-300 transition-colors">
                  {project.topic_title || "Untitled"}
                </h3>
                <p className="text-sm text-neutral-500 truncate">
                  {project.topic_description || "No description"}
                </p>
                <div className="flex items-center justify-between text-xs text-neutral-500 pt-1">
                  <span>
                    {project.segment_count} segments &middot; {project.scene_count} scenes
                  </span>
                  <span>{formatDate(project.created_at)}</span>
                </div>
              </div>

              {/* Delete button */}
              <div className="px-4 pb-3">
                <span
                  role="button"
                  tabIndex={0}
                  onClick={(e) => handleDelete(e, project)}
                  onKeyDown={(e) => { if (e.key === "Enter") handleDelete(e as unknown as React.MouseEvent, project); }}
                  className="text-xs text-neutral-600 hover:text-red-400 transition-colors"
                >
                  Delete
                </span>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
