import { useCallback, useEffect, useState } from "react";
import {
  assetUrl,
  exportShortFormThumbnails,
  generateShortFormThumbnailOne,
  generateShortFormThumbnailsAll,
  generateShortFormThumbnailsBatch,
  getShortFormJobStatus,
  getShortFormThumbnailsStatus,
  showInFolder,
} from "../../../api";
import { usePollJob } from "../../../hooks/usePollJob";
import type { ShortFormJobStatus } from "../../../types/render";

interface Props {
  scriptId: string;
  segments: { name: string }[];
  onStatusChange?: () => void;
}

type CurrentOp =
  | { type: "all" }
  | { type: "batch"; indices: number[] }
  | { type: "one"; index: number }
  | null;

function segmentLabel(segment: { name: string }, idx: number): string {
  return segment.name || `Segment ${idx + 1}`;
}

export default function ShortFormThumbnailsCard({ scriptId, segments, onStatusChange }: Props) {
  const [thumbnailUrls, setThumbnailUrls] = useState<Record<number, string | undefined>>({});
  const [thumbnailVersions, setThumbnailVersions] = useState<Record<number, number>>({});
  const [exportedPaths, setExportedPaths] = useState<Record<number, string | undefined>>({});
  const [busy, setBusy] = useState(false);
  const [busySegment, setBusySegment] = useState<number | null>(null);
  const [status, setStatus] = useState<ShortFormJobStatus | null>(null);
  const [currentOp, setCurrentOp] = useState<CurrentOp>(null);
  const [exporting, setExporting] = useState(false);
  const [exportFolder, setExportFolder] = useState<string | null>(null);

  const total = segments.length;
  const generatedCount = Object.values(thumbnailUrls).filter(Boolean).length;
  const missingIndices = segments.map((_, idx) => idx).filter((idx) => !thumbnailUrls[idx]);
  const missingCount = missingIndices.length;
  const allDone = total > 0 && generatedCount === total;
  const isBatchBusy = currentOp?.type === "all" || currentOp?.type === "batch";

  const refreshThumbnails = useCallback(async () => {
    const status = await getShortFormThumbnailsStatus(scriptId);
    setThumbnailUrls(status.paths);
    return status.paths;
  }, [scriptId]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const paths = await getShortFormThumbnailsStatus(scriptId);
        if (!cancelled) setThumbnailUrls(paths.paths);
      } catch {
        if (!cancelled) setThumbnailUrls({});
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [scriptId]);

  const { startPolling } = usePollJob<ShortFormJobStatus>({
    pollFn: (id) => getShortFormJobStatus(id),
    isComplete: (s) => s.status === "completed",
    isFailed: (s) => s.status === "failed",
    onStatus: (s) => {
      setStatus(s);
      if (s.status === "completed" || s.status === "failed") {
        setBusy(false);
        setBusySegment(null);
        setCurrentOp((op) => {
          if (s.status === "completed") {
            const ts = Date.now();
            if (op?.type === "all") {
              (s.output_urls ?? []).forEach((url, i) => {
                setThumbnailUrls((prev) => ({ ...prev, [i]: url }));
                setThumbnailVersions((prev) => ({ ...prev, [i]: ts }));
              });
            } else if (op?.type === "batch") {
              (s.output_urls ?? []).forEach((url, i) => {
                const segmentIdx = op.indices[i];
                if (segmentIdx != null) {
                  setThumbnailUrls((prev) => ({ ...prev, [segmentIdx]: url }));
                  setThumbnailVersions((prev) => ({ ...prev, [segmentIdx]: ts }));
                }
              });
            } else if (op?.type === "one") {
              const url = s.output_urls?.[0];
              if (url) {
                setThumbnailUrls((prev) => ({ ...prev, [op.index]: url }));
                setThumbnailVersions((prev) => ({ ...prev, [op.index]: ts }));
              }
            }
            onStatusChange?.();
          }
          return null;
        });
      }
    },
    onConnectionLost: () => {
      setBusy(false);
      setBusySegment(null);
      setCurrentOp(null);
    },
  });

  async function handleGenerateAll() {
    try {
      setBusy(true);
      setStatus(null);
      setCurrentOp({ type: "all" });
      const { job_id } = await generateShortFormThumbnailsAll(scriptId);
      startPolling(job_id);
    } catch (err) {
      setBusy(false);
      setCurrentOp(null);
      console.error(err);
    }
  }

  async function handleGenerateMissing() {
    try {
      setBusy(true);
      setStatus(null);
      const refreshed = await refreshThumbnails();
      const indices = segments.map((_, idx) => idx).filter((idx) => !refreshed[idx]);
      if (indices.length === 0) {
        setBusy(false);
        return;
      }
      setCurrentOp({ type: "batch", indices });
      const { job_id } = await generateShortFormThumbnailsBatch(scriptId, indices);
      startPolling(job_id);
    } catch (err) {
      setBusy(false);
      setCurrentOp(null);
      console.error(err);
    }
  }

  async function handleGenerateOne(idx: number) {
    try {
      setBusySegment(idx);
      setStatus(null);
      setCurrentOp({ type: "one", index: idx });
      const { job_id } = await generateShortFormThumbnailOne(scriptId, idx);
      startPolling(job_id);
    } catch (err) {
      setBusySegment(null);
      setCurrentOp(null);
      console.error(err);
    }
  }

  async function handleExport() {
    try {
      setExporting(true);
      const result = await exportShortFormThumbnails(scriptId);
      setExportFolder(result.folder_path);
      setExportedPaths(result.paths);
      await refreshThumbnails();
      onStatusChange?.();
    } catch (err) {
      console.error(err);
    } finally {
      setExporting(false);
    }
  }

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-neutral-300 uppercase tracking-wider">Short-Form Thumbnails</h3>
          <p className={`text-xs ${allDone ? "text-emerald-400" : "text-neutral-500"}`}>
            {generatedCount}/{total} generated
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <button
            onClick={handleGenerateMissing}
            disabled={busy || busySegment !== null || missingCount === 0}
            className="text-sm px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 disabled:opacity-40 rounded-lg font-medium transition-colors"
          >
            {isBatchBusy && currentOp?.type === "batch"
              ? "Generating..."
              : `Generate missing (${missingCount})`}
          </button>
          <button
            onClick={handleGenerateAll}
            disabled={busy || busySegment !== null || total === 0}
            className="text-sm px-3 py-1.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 rounded-lg font-medium transition-colors"
          >
            {isBatchBusy && currentOp?.type === "all" ? "Generating..." : "Generate all"}
          </button>
          {exportFolder && (
            <button
              onClick={() => showInFolder(exportFolder)}
              className="text-sm px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 rounded-lg font-medium text-neutral-300 transition-colors"
            >
              Show Exports
            </button>
          )}
          <button
            onClick={handleExport}
            disabled={exporting || busy || busySegment !== null || total === 0}
            className="text-sm px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 rounded-lg font-medium transition-colors"
          >
            {exporting ? "Exporting..." : "Export thumbnails"}
          </button>
        </div>
      </div>

      {(busy || busySegment !== null) && status && (
        <div className="space-y-1 rounded-lg border border-violet-500/20 bg-violet-500/10 p-3">
          <div className="flex justify-between text-xs text-violet-200">
            <span>{status.current_step || "Generating thumbnails..."}</span>
            <span>{Math.round((status.progress || 0) * 100)}%</span>
          </div>
          <div className="w-full h-1.5 bg-neutral-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-violet-500 transition-all duration-300"
              style={{ width: `${Math.max((status.progress || 0) * 100, 1)}%` }}
            />
          </div>
          {status.status === "failed" && status.error && (
            <p className="text-xs text-red-300">{status.error}</p>
          )}
        </div>
      )}

      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
        {segments.map((segment, idx) => {
          const url = thumbnailUrls[idx];
          const version = thumbnailVersions[idx];
          const imgSrc = url ? (version ? `${assetUrl(url)}?v=${version}` : assetUrl(url)) : null;
          const exportedPath = exportedPaths[idx];
          const segBusy = busySegment === idx;
          return (
            <article
              key={idx}
              className="rounded-lg border border-neutral-800 bg-neutral-950/60 overflow-hidden"
            >
              <div className="aspect-[9/16] bg-neutral-900">
                {url ? (
                  <img
                    src={imgSrc!}
                    alt={segmentLabel(segment, idx)}
                    className="w-full h-full object-cover"
                  />
                ) : (
                  <div className="w-full h-full flex items-center justify-center text-xs text-neutral-500">
                    Not generated
                  </div>
                )}
              </div>
              <div className="p-3 space-y-3">
                <div className="min-w-0">
                  <div className="text-[10px] uppercase tracking-wide text-neutral-500">
                    Thumbnail {idx + 1}
                  </div>
                  <p className="text-sm text-neutral-200 truncate">
                    {segmentLabel(segment, idx)}
                  </p>
                </div>
                <div className="flex items-center justify-between gap-2">
                  {exportedPath ? (
                    <button
                      onClick={() => showInFolder(exportedPath)}
                      className="text-xs px-2.5 py-1 bg-neutral-800 hover:bg-neutral-700 rounded text-neutral-300 transition-colors"
                    >
                      Show in Finder
                    </button>
                  ) : (
                    <span className="text-[10px] text-neutral-600">
                      {url ? "Ready to export" : "Needs generation"}
                    </span>
                  )}
                  <button
                    onClick={() => handleGenerateOne(idx)}
                    disabled={busy || busySegment !== null}
                    className="text-xs px-2.5 py-1 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 rounded text-white transition-colors"
                  >
                    {segBusy ? "..." : url ? "Regenerate" : "Generate"}
                  </button>
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
