import { useCallback, useEffect, useState } from "react";
import { assetUrl, fetchCatalog, toggleUploaded } from "../../api";
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
        <div className="p-6 overflow-y-auto flex-1 space-y-4">
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
          {entry.seo_description && (
            <p className="text-sm text-neutral-400 whitespace-pre-wrap">{entry.seo_description}</p>
          )}
          {entry.seo_tags.length > 0 && (
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
          )}
        </div>
      </div>
    </div>
  );
}

export default function CatalogPage() {
  const [entries, setEntries] = useState<CatalogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [filterUploaded, setFilterUploaded] = useState<"all" | "uploaded" | "not-uploaded">("all");
  const [selectedEntry, setSelectedEntry] = useState<CatalogEntry | null>(null);

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

              return (
                <button
                  key={entry.folder_name}
                  onClick={() => setSelectedEntry(entry)}
                  className="w-full flex items-start gap-4 bg-neutral-900 hover:bg-neutral-800 border border-neutral-800 hover:border-neutral-700 rounded-xl p-4 transition-colors text-left"
                >
                  {thumbSrc ? (
                    <img
                      src={thumbSrc}
                      alt=""
                      className="w-48 aspect-video object-cover rounded-lg shrink-0 bg-neutral-800"
                    />
                  ) : (
                    <div className="w-48 aspect-video bg-neutral-800 rounded-lg shrink-0 flex items-center justify-center">
                      <svg className="w-8 h-8 text-neutral-700" fill="none" viewBox="0 0 24 24" strokeWidth={1} stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" d="m15.75 10.5 4.72-4.72a.75.75 0 0 1 1.28.53v11.38a.75.75 0 0 1-1.28.53l-4.72-4.72M4.5 18.75h9a2.25 2.25 0 0 0 2.25-2.25v-9a2.25 2.25 0 0 0-2.25-2.25h-9A2.25 2.25 0 0 0 2.25 7.5v9a2.25 2.25 0 0 0 2.25 2.25Z" />
                      </svg>
                    </div>
                  )}
                  <div className="flex-1 min-w-0 space-y-2">
                    <div className="flex items-start justify-between gap-3">
                      <h3 className="text-base font-semibold text-neutral-100 truncate">
                        {entry.seo_title || entry.folder_name}
                      </h3>
                      <span
                        onClick={(e) => handleToggleUploaded(entry, e)}
                        className={`shrink-0 text-xs px-2.5 py-1 rounded-full font-medium cursor-pointer transition-colors ${
                          entry.uploaded
                            ? "bg-emerald-500/15 text-emerald-400 hover:bg-emerald-500/25"
                            : "bg-neutral-800 text-neutral-500 hover:bg-neutral-700 hover:text-neutral-300"
                        }`}
                      >
                        {entry.uploaded ? "Uploaded" : "Not Uploaded"}
                      </span>
                    </div>
                    {entry.seo_description && (
                      <p className="text-sm text-neutral-500 line-clamp-2">{entry.seo_description}</p>
                    )}
                    {entry.seo_tags.length > 0 && (
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
