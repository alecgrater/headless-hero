import { useCallback, useEffect, useState } from "react";
import { assetUrl, fetchCatalog, showInFolder, toggleUploaded } from "../../api";
import type { CatalogEntry } from "../../api";

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

function AccordionContent({ entry }: { entry: CatalogEntry }) {
  return (
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
  );
}

export default function CatalogPage() {
  const [entries, setEntries] = useState<CatalogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filterUploaded, setFilterUploaded] = useState<"all" | "uploaded" | "not-uploaded">("all");
  const [selectedEntry, setSelectedEntry] = useState<CatalogEntry | null>(null);
  const [expandedFolder, setExpandedFolder] = useState<string | null>(null);

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
  }, [load]);

  const handleToggleUploaded = async (entry: CatalogEntry, e: React.MouseEvent) => {
    e.stopPropagation();
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
                  <button
                    onClick={() => toggleExpand(entry.folder_name)}
                    className="w-full flex items-start gap-4 p-4 text-left"
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
                          <span
                            onClick={(e) => handleToggleUploaded(entry, e)}
                            title="Click to toggle upload status"
                            className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full font-medium cursor-pointer transition-colors border ${
                              entry.uploaded
                                ? "bg-emerald-500/15 text-emerald-400 border-emerald-500/30 hover:bg-emerald-500/25"
                                : "bg-neutral-800 text-neutral-500 border-neutral-700 hover:bg-neutral-700 hover:text-neutral-300"
                            }`}
                          >
                            {/* Toggle circle indicator */}
                            <span className={`w-2.5 h-2.5 rounded-full transition-colors ${
                              entry.uploaded ? "bg-emerald-400" : "bg-neutral-600"
                            }`} />
                            {entry.uploaded ? "Uploaded" : "Not Uploaded"}
                          </span>
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
                  </button>

                  {/* Accordion content */}
                  <div
                    className="grid transition-[grid-template-rows] duration-200 ease-out"
                    style={{ gridTemplateRows: isExpanded ? "1fr" : "0fr" }}
                  >
                    <div className="overflow-hidden">
                      {isExpanded && <AccordionContent entry={entry} />}
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
