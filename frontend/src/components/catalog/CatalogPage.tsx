import { useCallback, useEffect, useRef, useState } from "react";
import {
  assetUrl,
  catalogUpload,
  fetchCatalog,
  getPublishStatus,
  getYouTubeOAuthStatus,
  openInBrowser,
  showInFolder,
  syncCatalogYouTube,
  toggleUploaded,
} from "../../api";
import type { CatalogEntry, CatalogUploadOptions, PublishJobStatus } from "../../api";
import { usePollJob } from "../../hooks/usePollJob";

interface Props {
  onNavigateToSettings: () => void;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function VideoModal({
  entry,
  onClose,
}: {
  entry: CatalogEntry;
  onClose: () => void;
}) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  const videoSrc = entry.video_file
    ? assetUrl(`/static/catalog/${encodeURIComponent(entry.folder_name)}/${encodeURIComponent(entry.video_file)}`)
    : null;

  return (
    <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-8" onClick={onClose}>
      <div
        className="bg-neutral-900 border border-neutral-800 rounded-2xl w-full max-w-5xl max-h-[90vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-6 py-4 border-b border-neutral-800 shrink-0">
          <h2 className="text-lg font-bold truncate">{entry.seo_title || entry.folder_name}</h2>
          <button
            onClick={onClose}
            className="text-neutral-400 hover:text-white transition-colors text-xl leading-none ml-4"
          >
            &times;
          </button>
        </div>
        <div className="p-6 overflow-y-auto flex-1">
          {videoSrc ? (
            <video
              src={videoSrc}
              controls
              autoPlay
              className="w-full rounded-lg border border-neutral-700"
            />
          ) : (
            <div className="w-full aspect-video bg-neutral-800 rounded-lg flex items-center justify-center text-neutral-500">
              No video file
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // clipboard may not be available
    }
  };

  return (
    <button
      onClick={handleCopy}
      className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-400 hover:text-neutral-200 transition-colors"
    >
      {copied ? (
        <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="m4.5 12.75 6 6 9-13.5" />
        </svg>
      ) : (
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M15.666 3.888A2.25 2.25 0 0 0 13.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 0 1-.75.75H9.75a.75.75 0 0 1-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 0 1-2.25 2.25H6.75A2.25 2.25 0 0 1 4.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 0 1 1.927-.184" />
        </svg>
      )}
      {copied ? "Copied!" : label}
    </button>
  );
}

function UploadPanel({
  entry,
  youtubeConnected,
  onNavigateToSettings,
  onUploadComplete,
}: {
  entry: CatalogEntry;
  youtubeConnected: boolean;
  onNavigateToSettings: () => void;
  onUploadComplete: (youtubeUrl: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(entry.seo_title || entry.folder_name);
  const [description, setDescription] = useState(entry.seo_description || "");
  const [tags, setTags] = useState(entry.seo_tags.join(", "));
  const [privacy, setPrivacy] = useState("unlisted");
  const [uploading, setUploading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<PublishJobStatus | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const { startPolling, stopPolling } = usePollJob<PublishJobStatus>({
    pollFn: async (jobId) => getPublishStatus(jobId),
    isComplete: (s) => s.status === "completed",
    isFailed: (s) => s.status === "failed",
    onStatus: (status) => {
      setUploadStatus(status);
      if (status.status === "completed" && status.output_urls.length > 0) {
        setUploading(false);
        onUploadComplete(status.output_urls[0]);
      }
      if (status.status === "failed") {
        setUploading(false);
        setUploadError(status.error || "Upload failed");
      }
    },
    onConnectionLost: () => {
      setUploading(false);
      setUploadError("Lost connection to upload job");
    },
  });

  useEffect(() => () => stopPolling(), [stopPolling]);

  if (!youtubeConnected) {
    return (
      <div className="px-4 pb-4 pt-3 border-t border-neutral-800/60">
        <button
          onClick={(e) => {
            e.stopPropagation();
            onNavigateToSettings();
          }}
          className="flex items-center gap-2 text-sm px-4 py-2 bg-red-600/20 border border-red-500/30 hover:bg-red-600/30 rounded-lg text-red-300 transition-colors"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 0 1 1.242 7.244l-4.5 4.5a4.5 4.5 0 0 1-6.364-6.364l1.757-1.757m9.86-3.061a4.5 4.5 0 0 0-1.242-7.244l4.5-4.5a4.5 4.5 0 1 1 6.364 6.364l-1.757 1.757" />
          </svg>
          Connect YouTube in Settings
        </button>
      </div>
    );
  }

  const handleUpload = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setUploading(true);
    setUploadError(null);
    setUploadStatus(null);
    try {
      const options: CatalogUploadOptions = {
        folder_name: entry.folder_name,
        title,
        description,
        tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
        privacy_status: privacy,
      };
      const { job_id } = await catalogUpload(options);
      startPolling(job_id);
    } catch (err) {
      setUploading(false);
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    }
  };

  const progress = uploadStatus?.progress ?? 0;

  return (
    <div className="px-4 pb-4 pt-3 border-t border-neutral-800/60 space-y-3" onClick={(e) => e.stopPropagation()}>
      {uploading && (
        <div className="space-y-1.5">
          <div className="flex justify-between text-xs text-neutral-400">
            <span>{uploadStatus?.current_step || "Starting upload..."}</span>
            <span>{Math.round(progress * 100)}%</span>
          </div>
          <div className="w-full h-2 bg-neutral-800 rounded-full overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-violet-600 via-violet-400 to-violet-600 bg-[length:200%_100%] animate-[shimmer_2s_ease-in-out_infinite] transition-all duration-300"
              style={{ width: `${Math.max(progress * 100, 1)}%` }}
            />
          </div>
        </div>
      )}

      {uploadError && (
        <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/30 rounded-lg p-2">
          {uploadError}
        </div>
      )}

      {!uploading && (
        <>
          <div className="flex items-center justify-between">
            <h4 className="text-xs font-semibold text-neutral-400 uppercase tracking-wider">Upload to YouTube</h4>
            <button
              onClick={() => setEditing(!editing)}
              className="text-[11px] text-violet-400 hover:text-violet-300 transition-colors"
            >
              {editing ? "Done Editing" : "Edit Metadata"}
            </button>
          </div>

          <div className="space-y-2">
            <div>
              <label className="text-[11px] text-neutral-500 block mb-0.5">Title</label>
              {editing ? (
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-2.5 py-1.5 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 transition-colors"
                />
              ) : (
                <p className="text-sm text-neutral-200">{title}</p>
              )}
            </div>
            <div>
              <label className="text-[11px] text-neutral-500 block mb-0.5">Description</label>
              {editing ? (
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={3}
                  className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-2.5 py-1.5 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 transition-colors resize-none"
                />
              ) : (
                <p className="text-xs text-neutral-400 line-clamp-3 whitespace-pre-wrap">{description || "No description"}</p>
              )}
            </div>
            <div>
              <label className="text-[11px] text-neutral-500 block mb-0.5">Tags</label>
              {editing ? (
                <input
                  type="text"
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  className="w-full bg-neutral-800 border border-neutral-700 rounded-lg px-2.5 py-1.5 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 transition-colors"
                  placeholder="tag1, tag2, tag3"
                />
              ) : (
                <p className="text-xs text-neutral-400">{tags || "No tags"}</p>
              )}
            </div>
            <div>
              <label className="text-[11px] text-neutral-500 block mb-0.5">Privacy</label>
              <select
                value={privacy}
                onChange={(e) => setPrivacy(e.target.value)}
                className="bg-neutral-800 border border-neutral-700 rounded-lg px-2.5 py-1.5 text-sm text-neutral-100 focus:outline-none focus:border-violet-500 transition-colors"
              >
                <option value="unlisted">Unlisted</option>
                <option value="private">Private</option>
                <option value="public">Public</option>
              </select>
            </div>
          </div>

          <button
            onClick={handleUpload}
            disabled={!entry.video_file}
            className="flex items-center gap-2 text-sm px-4 py-2 bg-red-600 hover:bg-red-500 disabled:opacity-50 rounded-lg font-medium transition-colors text-white"
          >
            <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0C.488 3.45.029 5.804 0 12c.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0C23.512 20.55 23.971 18.196 24 12c-.029-6.185-.484-8.549-4.385-8.816zM9 16V8l8 4-8 4z" />
            </svg>
            Upload to YouTube
          </button>
        </>
      )}
    </div>
  );
}

function YouTubeIcon({ className }: { className?: string }) {
  return (
    <svg className={className ?? "w-3 h-3"} fill="currentColor" viewBox="0 0 24 24">
      <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0C.488 3.45.029 5.804 0 12c.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0C23.512 20.55 23.971 18.196 24 12c-.029-6.185-.484-8.549-4.385-8.816zM9 16V8l8 4-8 4z" />
    </svg>
  );
}

function QuickUploadButton({
  entry,
  youtubeConnected,
  onNavigateToSettings,
  onUploadComplete,
}: {
  entry: CatalogEntry;
  youtubeConnected: boolean;
  onNavigateToSettings: () => void;
  onUploadComplete: (youtubeUrl: string) => void;
}) {
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState("");
  const [error, setError] = useState<string | null>(null);
  const uploadingRef = useRef(false);

  const { startPolling, stopPolling } = usePollJob<PublishJobStatus>({
    pollFn: async (jobId) => getPublishStatus(jobId),
    isComplete: (s) => s.status === "completed",
    isFailed: (s) => s.status === "failed",
    onStatus: (status) => {
      setProgress(status.progress ?? 0);
      setCurrentStep(status.current_step || "");
      if (status.status === "completed" && status.output_urls.length > 0) {
        setUploading(false);
        uploadingRef.current = false;
        onUploadComplete(status.output_urls[0]);
      }
      if (status.status === "failed") {
        setUploading(false);
        uploadingRef.current = false;
        setError(status.error || "Upload failed");
      }
    },
    onConnectionLost: () => {
      setUploading(false);
      uploadingRef.current = false;
      setError("Lost connection");
    },
  });

  useEffect(() => () => stopPolling(), [stopPolling]);

  if (!entry.video_file || entry.uploaded) return null;

  const handleClick = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (uploadingRef.current) return;
    uploadingRef.current = true;
    setUploading(true);
    setError(null);
    try {
      const options: CatalogUploadOptions = {
        folder_name: entry.folder_name,
        title: entry.seo_title || entry.folder_name,
        description: entry.seo_description || "",
        tags: entry.seo_tags,
        privacy_status: "unlisted",
      };
      const { job_id } = await catalogUpload(options);
      startPolling(job_id);
    } catch (err) {
      setUploading(false);
      uploadingRef.current = false;
      setError(err instanceof Error ? err.message : "Upload failed");
    }
  };

  if (uploading) {
    return (
      <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
        <span className="text-[11px] text-violet-400 whitespace-nowrap shrink-0">
          {currentStep || "Uploading..."} {Math.round(progress * 100)}%
        </span>
        <div className="w-24 h-1.5 bg-neutral-800 rounded-full overflow-hidden shrink-0">
          <div
            className="h-full rounded-full bg-gradient-to-r from-violet-600 via-violet-400 to-violet-600 bg-[length:200%_100%] animate-[shimmer_2s_ease-in-out_infinite] transition-all duration-300"
            style={{ width: `${Math.max(progress * 100, 2)}%` }}
          />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <button
        type="button"
        onClick={handleClick}
        className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full font-medium bg-red-500/15 text-red-400 border border-red-500/30 hover:bg-red-500/25 transition-colors"
        title={error}
      >
        <YouTubeIcon />
        Retry
      </button>
    );
  }

  if (!youtubeConnected) {
    return (
      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          onNavigateToSettings();
        }}
        className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full font-medium bg-neutral-700/40 text-neutral-400 border border-neutral-600/30 hover:bg-neutral-700/60 transition-colors"
        title="Connect YouTube account in Settings to upload"
      >
        <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" d="M13.19 8.688a4.5 4.5 0 0 1 1.242 7.244l-4.5 4.5a4.5 4.5 0 0 1-6.364-6.364l1.757-1.757m9.86-3.061a4.5 4.5 0 0 0-1.242-7.244l4.5-4.5a4.5 4.5 0 1 1 6.364 6.364l-1.757 1.757" />
        </svg>
        Connect YT
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full font-medium bg-red-600/20 text-red-400 border border-red-500/30 hover:bg-red-600/30 transition-colors"
      title="Upload to YouTube (unlisted)"
    >
      <YouTubeIcon />
      Upload
    </button>
  );
}

function AccordionContent({
  entry,
  youtubeConnected,
  onNavigateToSettings,
  onUploadComplete,
  onToggleUploaded,
}: {
  entry: CatalogEntry;
  youtubeConnected: boolean;
  onNavigateToSettings: () => void;
  onUploadComplete: (youtubeUrl: string) => void;
  onToggleUploaded: () => void;
}) {
  return (
    <div className="space-y-0">
      <div className="px-4 pb-4 pt-3 border-t border-neutral-800/60 space-y-4">
        {/* Action buttons */}
        <div className="flex items-center gap-2 flex-wrap">
          {entry.folder_path && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                showInFolder(entry.folder_path);
              }}
              className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-400 hover:text-neutral-200 transition-colors"
            >
              <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.25 12.75V12A2.25 2.25 0 0 1 4.5 9.75h15A2.25 2.25 0 0 1 21.75 12v.75m-8.69-6.44-2.12-2.12a1.5 1.5 0 0 0-1.061-.44H4.5A2.25 2.25 0 0 0 2.25 6v12a2.25 2.25 0 0 0 2.25 2.25h15A2.25 2.25 0 0 0 21.75 18V9a2.25 2.25 0 0 0-2.25-2.25h-5.379a1.5 1.5 0 0 1-1.06-.44Z" />
              </svg>
              Open in Finder
            </button>
          )}
          {entry.seo_description && (
            <CopyButton text={entry.seo_description} label="Copy Description" />
          )}
          {entry.seo_tags.length > 0 && (
            <CopyButton text={entry.seo_tags.join(", ")} label="Copy Tags" />
          )}
          {!entry.youtube_url && (
            <label className="flex items-center gap-1.5 cursor-pointer select-none text-xs px-3 py-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-400 hover:text-neutral-200 transition-colors">
              <input
                type="checkbox"
                checked={entry.uploaded}
                onChange={onToggleUploaded}
                className="w-3.5 h-3.5 rounded border-neutral-600 bg-neutral-800 text-emerald-500 focus:ring-0 focus:ring-offset-0 cursor-pointer accent-emerald-500"
              />
              Uploaded
            </label>
          )}
        </div>

        {/* Full SEO Title */}
        {entry.seo_title && (
          <div>
            <h4 className="text-[11px] font-medium text-neutral-500 uppercase tracking-wider mb-1">Title</h4>
            <p className="text-sm text-neutral-200 font-medium">{entry.seo_title}</p>
          </div>
        )}

        {/* Full Description */}
        {entry.seo_description && (
          <div>
            <h4 className="text-[11px] font-medium text-neutral-500 uppercase tracking-wider mb-1">Description</h4>
            <p className="text-sm text-neutral-400 whitespace-pre-wrap leading-relaxed">{entry.seo_description}</p>
          </div>
        )}

        {/* All Tags */}
        {entry.seo_tags.length > 0 && (
          <div>
            <h4 className="text-[11px] font-medium text-neutral-500 uppercase tracking-wider mb-1.5">
              Tags ({entry.seo_tags.length})
            </h4>
            <div className="flex flex-wrap gap-1.5">
              {entry.seo_tags.map((tag) => (
                <span
                  key={tag}
                  className="text-xs px-2 py-0.5 bg-neutral-800 text-neutral-400 rounded-full"
                >
                  {tag}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* No SEO data message */}
        {!entry.seo_title && !entry.seo_description && entry.seo_tags.length === 0 && (
          <p className="text-sm text-neutral-600 italic">No SEO metadata found in this export folder.</p>
        )}
      </div>

      {/* Upload panel — only show if not already uploaded to YouTube */}
      {!entry.youtube_url && (
        <UploadPanel
          entry={entry}
          youtubeConnected={youtubeConnected}
          onNavigateToSettings={onNavigateToSettings}
          onUploadComplete={onUploadComplete}
        />
      )}
    </div>
  );
}

export default function CatalogPage({ onNavigateToSettings }: Props) {
  const [entries, setEntries] = useState<CatalogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filterUploaded, setFilterUploaded] = useState<"all" | "uploaded" | "not-uploaded">("all");
  const [selectedEntry, setSelectedEntry] = useState<CatalogEntry | null>(null);
  const [expandedFolder, setExpandedFolder] = useState<string | null>(null);
  const [youtubeConnected, setYoutubeConnected] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchCatalog();
      setEntries(data);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    getYouTubeOAuthStatus().then(async (status) => {
      const connected = status.youtube.connected;
      setYoutubeConnected(connected);
      if (connected) {
        try {
          const { matched } = await syncCatalogYouTube();
          if (matched > 0) load();
        } catch {
          // sync is best-effort
        }
      }
    }).catch(() => {});
  }, [load]);

  const handleToggleUploaded = async (entry: CatalogEntry, e?: React.SyntheticEvent) => {
    e?.stopPropagation();
    try {
      const result = await toggleUploaded(entry.folder_name);
      setEntries((prev) =>
        prev.map((en) =>
          en.folder_name === entry.folder_name ? { ...en, uploaded: result.uploaded } : en,
        ),
      );
    } catch {
      // toast handled by global interceptor
    }
  };

  const handlePlayClick = (entry: CatalogEntry, e: React.MouseEvent) => {
    e.stopPropagation();
    if (entry.video_file) {
      setSelectedEntry(entry);
    }
  };

  const handleUploadComplete = (folderName: string, youtubeUrl: string) => {
    setEntries((prev) =>
      prev.map((en) =>
        en.folder_name === folderName
          ? { ...en, uploaded: true, youtube_url: youtubeUrl }
          : en,
      ),
    );
  };

  const toggleExpand = (folderName: string) => {
    setExpandedFolder((prev) => (prev === folderName ? null : folderName));
  };

  const filtered = entries.filter((e) => {
    const title = (e.seo_title || e.folder_name).toLowerCase();
    if (search && !title.includes(search.toLowerCase())) return false;
    if (filterUploaded === "uploaded" && !e.uploaded) return false;
    if (filterUploaded === "not-uploaded" && e.uploaded) return false;
    return true;
  });

  return (
    <div className="flex-1 flex flex-col h-full">
      <div className="border-b border-neutral-800/40 px-6 py-4 flex items-center justify-between shrink-0">
        <h1 className="text-lg font-bold">Catalog</h1>
        <div className="flex items-center gap-3">
          <input
            type="text"
            placeholder="Search videos..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="text-sm bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-neutral-200 placeholder-neutral-500 focus:outline-none focus:ring-1 focus:ring-violet-500 w-56"
          />
          <select
            value={filterUploaded}
            onChange={(e) => setFilterUploaded(e.target.value as typeof filterUploaded)}
            className="text-sm bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-neutral-200 focus:outline-none focus:ring-1 focus:ring-violet-500"
          >
            <option value="all">All</option>
            <option value="uploaded">Uploaded</option>
            <option value="not-uploaded">Not Uploaded</option>
          </select>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="flex items-center justify-center py-20 text-neutral-500">
            <span className="w-5 h-5 border-2 border-neutral-500 border-t-transparent rounded-full animate-spin mr-3" />
            Loading catalog...
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-neutral-500">
            <svg className="w-12 h-12 mb-3 text-neutral-700" fill="none" viewBox="0 0 24 24" strokeWidth={1} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="m15.75 10.5 4.72-4.72a.75.75 0 0 1 1.28.53v11.38a.75.75 0 0 1-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25h-9A2.25 2.25 0 0 0 2.25 7.5v9a2.25 2.25 0 0 0 2.25 2.25Z" />
            </svg>
            <p className="text-sm">
              {entries.length === 0
                ? "No exported videos yet. Use Export All from the timeline to get started."
                : "No videos match your filter."}
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {filtered.map((entry) => {
              const thumbSrc = entry.thumbnail_file
                ? assetUrl(`/static/catalog/${encodeURIComponent(entry.folder_name)}/${entry.thumbnail_file}`)
                : null;
              const isExpanded = expandedFolder === entry.folder_name;

              return (
                <div
                  key={entry.folder_name}
                  className="bg-neutral-900 border border-neutral-800 hover:border-neutral-700 rounded-xl transition-colors overflow-hidden"
                >
                  {/* Collapsed row — always visible */}
                  <div
                    onClick={() => toggleExpand(entry.folder_name)}
                    className="w-full flex items-start gap-4 p-4 text-left cursor-pointer"
                  >
                    {/* Thumbnail with play overlay */}
                    <div className="relative w-48 aspect-video shrink-0 group/thumb">
                      {thumbSrc ? (
                        <img
                          src={thumbSrc}
                          alt=""
                          className="w-full h-full object-cover rounded-lg bg-neutral-800"
                        />
                      ) : (
                        <div className="w-full h-full bg-neutral-800 rounded-lg flex items-center justify-center">
                          <svg className="w-8 h-8 text-neutral-700" fill="none" viewBox="0 0 24 24" strokeWidth={1} stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" d="m15.75 10.5 4.72-4.72a.75.75 0 0 1 1.28.53v11.38a.75.75 0 0 1-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25h-9A2.25 2.25 0 0 0 2.25 7.5v9a2.25 2.25 0 0 0 2.25 2.25Z" />
                          </svg>
                        </div>
                      )}
                      {entry.video_file && (
                        <div
                          onClick={(e) => handlePlayClick(entry, e)}
                          className="absolute inset-0 rounded-lg bg-black/0 group-hover/thumb:bg-black/50 flex items-center justify-center opacity-0 group-hover/thumb:opacity-100 transition-all cursor-pointer"
                        >
                          <svg className="w-10 h-10 text-white drop-shadow-lg" fill="currentColor" viewBox="0 0 24 24">
                            <path d="M8 5v14l11-7z" />
                          </svg>
                        </div>
                      )}
                    </div>

                    {/* Info */}
                    <div className="flex-1 min-w-0 space-y-2">
                      <div className="flex items-start justify-between gap-3">
                        <h3 className="text-base font-semibold text-neutral-100 truncate">
                          {entry.seo_title || entry.folder_name}
                        </h3>
                        <div className="flex items-center gap-2 shrink-0">
                          {entry.youtube_url ? (
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                openInBrowser(entry.youtube_url!);
                              }}
                              title="Open on YouTube"
                              className="flex items-center justify-center w-8 h-8 rounded-full bg-red-600/20 hover:bg-red-600/40 transition-colors"
                            >
                              <svg className="w-4 h-4 text-red-400" fill="currentColor" viewBox="0 0 24 24">
                                <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0C.488 3.45.029 5.804 0 12c.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0C23.512 20.55 23.971 18.196 24 12c-.029-6.185-.484-8.549-4.385-8.816zM9 16V8l8 4-8 4z" />
                              </svg>
                            </button>
                          ) : (
                            <QuickUploadButton
                              entry={entry}
                              youtubeConnected={youtubeConnected}
                              onNavigateToSettings={onNavigateToSettings}
                              onUploadComplete={(url) => handleUploadComplete(entry.folder_name, url)}
                            />
                          )}
                          {/* Chevron */}
                          <svg
                            className={`w-4 h-4 text-neutral-500 transition-transform duration-200 ${isExpanded ? "rotate-180" : ""}`}
                            fill="none"
                            viewBox="0 0 24 24"
                            strokeWidth={2}
                            stroke="currentColor"
                          >
                            <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
                          </svg>
                        </div>
                      </div>
                      {entry.seo_description && (
                        <p className="text-sm text-neutral-500 line-clamp-2">{entry.seo_description}</p>
                      )}
                      {!isExpanded && entry.seo_tags.length > 0 && (
                        <div className="flex flex-wrap gap-1.5">
                          {entry.seo_tags.slice(0, 5).map((tag) => (
                            <span
                              key={tag}
                              className="text-[11px] px-2 py-0.5 bg-neutral-800 text-neutral-500 rounded-full"
                            >
                              {tag}
                            </span>
                          ))}
                          {entry.seo_tags.length > 5 && (
                            <span className="text-[11px] text-neutral-600">+{entry.seo_tags.length - 5}</span>
                          )}
                        </div>
                      )}
                      <div className="flex items-center gap-4 text-xs text-neutral-600">
                        <span>{entry.file_size_mb} MB</span>
                        <span>{formatDate(entry.exported_at)}</span>
                      </div>
                    </div>
                  </div>

                  {/* Accordion content */}
                  <div
                    className="grid transition-[grid-template-rows] duration-200 ease-out"
                    style={{ gridTemplateRows: isExpanded ? "1fr" : "0fr" }}
                  >
                    <div className="overflow-hidden">
                      {isExpanded && (
                        <AccordionContent
                          entry={entry}
                          youtubeConnected={youtubeConnected}
                          onNavigateToSettings={onNavigateToSettings}
                          onUploadComplete={(url) => handleUploadComplete(entry.folder_name, url)}
                          onToggleUploaded={() => handleToggleUploaded(entry)}
                        />
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {selectedEntry && (
        <VideoModal entry={selectedEntry} onClose={() => setSelectedEntry(null)} />
      )}
    </div>
  );
}
