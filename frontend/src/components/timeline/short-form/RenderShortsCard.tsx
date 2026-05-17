import { useState } from "react";
import api, {
  INSTAGRAM_URL,
  TIKTOK_STUDIO_UPLOAD_URL,
  YOUTUBE_STUDIO_URL,
  getShortFormJobStatus,
  openInBrowser,
  renderShortAll,
  renderShortBatch,
  renderShortOne,
  showInFolder,
  uploadShortForm,
} from "../../../api";
import { usePollJob } from "../../../hooks/usePollJob";
import type { OAuthStatusResponse, ShortUploadStatus } from "../../../types/publish";
import type { ShortFormJobStatus, ShortFormSEOMetadata } from "../../../types/render";

const PLATFORMS = ["youtube", "tiktok", "instagram"] as const;
type PlatformKey = (typeof PLATFORMS)[number];

interface Props {
  scriptId: string;
  segments: { name: string }[];
  /**
   * Map of segment_idx -> path string.
   * Values set by the disk probe are web-relative paths (/static/…).
   * Values set after a render are absolute filesystem paths to the Downloads copy.
   * Show in Finder is only shown for filesystem paths (not /static/… probe values).
   */
  renderedUrls: Record<number, string | undefined>;
  downloadsUrls: Record<number, string | undefined>;
  connections: OAuthStatusResponse | null;
  uploadStatuses: Record<number, ShortUploadStatus>;
  shortFormSeoMetadata: ShortFormSEOMetadata | null;
  onRefreshRendered: () => Promise<Record<number, string | undefined>>;
  onRefreshUploads: () => Promise<Record<number, ShortUploadStatus>>;
  onRenderComplete: (segmentIdx: number, url: string) => void;
}

type CurrentOp =
  | { type: "all" }
  | { type: "batch"; indices: number[] }
  | { type: "one"; index: number }
  | null;

export default function RenderShortsCard({
  scriptId,
  segments,
  renderedUrls,
  downloadsUrls,
  connections,
  uploadStatuses,
  shortFormSeoMetadata,
  onRefreshRendered,
  onRefreshUploads,
  onRenderComplete,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<ShortFormJobStatus | null>(null);
  const [busySegment, setBusySegment] = useState<number | null>(null);
  const [uploadingSegment, setUploadingSegment] = useState<number | null>(null);
  const [uploadStatus, setUploadStatus] = useState<ShortFormJobStatus | null>(null);
  const [currentOp, setCurrentOp] = useState<CurrentOp>(null);

  const total = segments.length;
  const renderedCount = Object.values(renderedUrls).filter(Boolean).length;
  const remainingIndices = segments
    .map((_, idx) => idx)
    .filter((idx) => !renderedUrls[idx]);
  const remainingCount = remainingIndices.length;
  const allDone = renderedCount === total && total > 0;
  const isBatchBusy = currentOp?.type === "all" || currentOp?.type === "batch";

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
            if (op?.type === "all") {
              (s.output_urls ?? []).forEach((url, i) => onRenderComplete(i, url));
            } else if (op?.type === "batch") {
              (s.output_urls ?? []).forEach((url, i) => {
                const segmentIdx = op.indices[i];
                if (segmentIdx != null) onRenderComplete(segmentIdx, url);
              });
            } else if (op?.type === "one") {
              const url = s.output_urls?.[0];
              if (url) onRenderComplete(op.index, url);
            }
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

  const { startPolling: startUploadPolling } = usePollJob<ShortFormJobStatus>({
    pollFn: async (id) => {
      const res = await api.get(`/api/publish/status/${id}`);
      if (!res.ok) return null;
      return res.data as ShortFormJobStatus;
    },
    isComplete: (s) => s.status === "completed",
    isFailed: (s) => s.status === "failed",
    onStatus: (s) => {
      setUploadStatus(s);
      if (s.status === "completed" || s.status === "failed") {
        setUploadingSegment(null);
        onRefreshUploads();
      }
    },
    onConnectionLost: () => {
      setUploadingSegment(null);
    },
  });

  async function handleRenderAll() {
    try {
      setBusy(true);
      setStatus(null);
      setCurrentOp({ type: "all" });
      const { job_id } = await renderShortAll(scriptId);
      startPolling(job_id);
    } catch (err) {
      setBusy(false);
      setCurrentOp(null);
      console.error(err);
    }
  }

  async function handleRenderRemaining() {
    try {
      setBusy(true);
      setStatus(null);
      const refreshedUrls = await onRefreshRendered();
      const indices = segments
        .map((_, idx) => idx)
        .filter((idx) => !refreshedUrls[idx]);
      if (indices.length === 0) {
        setBusy(false);
        return;
      }
      setCurrentOp({ type: "batch", indices });
      const { job_id } = await renderShortBatch(scriptId, indices);
      startPolling(job_id);
    } catch (err) {
      setBusy(false);
      setCurrentOp(null);
      console.error(err);
    }
  }

  async function handleRenderOne(idx: number) {
    try {
      setBusySegment(idx);
      setStatus(null);
      setCurrentOp({ type: "one", index: idx });
      const { job_id } = await renderShortOne(scriptId, idx);
      startPolling(job_id);
    } catch (err) {
      setBusySegment(null);
      setCurrentOp(null);
      console.error(err);
    }
  }

  async function handleUploadShort(idx: number) {
    try {
      setUploadingSegment(idx);
      setUploadStatus(null);
      const { job_id } = await uploadShortForm(scriptId, idx);
      startUploadPolling(job_id);
    } catch (err) {
      setUploadingSegment(null);
      console.error(err);
    }
  }

  function shortHasSeo(idx: number) {
    const shorts = shortFormSeoMetadata?.shorts ?? [];
    const usesOneBasedIndices = shorts.some((item) => item.index === 1);
    const expectedIndex = usesOneBasedIndices ? idx + 1 : idx;
    return shorts.some((item) => item.index === expectedIndex);
  }

  function platformChipState(idx: number, platform: PlatformKey) {
    const connected = connections?.[platform]?.connected ?? false;
    if (!connected) return "Not connected";
    if (uploadingSegment === idx) return "Uploading";
    const status = uploadStatuses[idx]?.platforms?.[platform]?.status;
    if (status === "published" || status === "scheduled") return "Uploaded";
    if (status === "failed") return "Failed";
    if (status === "pending") return "Processing";
    if (status === "uploading") return "Uploading";
    return "Ready";
  }

  function uploadButtonLabel(idx: number) {
    if (uploadingSegment === idx) return "Uploading...";
    const connected = PLATFORMS.filter((p) => connections?.[p]?.connected);
    const uploaded = connected.filter((p) => {
      const status = uploadStatuses[idx]?.platforms?.[p]?.status;
      return status === "published" || status === "scheduled";
    });
    const processing = connected.some((p) => {
      const status = uploadStatuses[idx]?.platforms?.[p]?.status;
      return status === "pending" || status === "uploading";
    });
    if (processing) return "Processing";
    if (connected.length > 0 && uploaded.length === connected.length) return "Uploaded";
    if (uploaded.length > 0) return "Upload remaining";
    return "Upload";
  }

  function canUpload(idx: number) {
    if (!renderedUrls[idx]) return false;
    if (!shortHasSeo(idx)) return false;
    if (busy || busySegment !== null) return false;
    if (uploadingSegment !== null) return false;
    const connected = PLATFORMS.filter((p) => connections?.[p]?.connected);
    if (connected.length === 0) return false;
    return connected.some((p) => {
      const status = uploadStatuses[idx]?.platforms?.[p]?.status;
      return status !== "pending" && status !== "uploading" && status !== "published" && status !== "scheduled";
    });
  }

  return (
    <section className="bg-neutral-900 border border-neutral-800 rounded-xl p-4 space-y-3">
      <header className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-neutral-200">Render Shorts</h3>
          <p
            className={`text-xs ${
              allDone ? "text-emerald-400" : "text-neutral-500"
            }`}
          >
            {`${renderedCount}/${total} rendered`}
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <button
            onClick={handleRenderRemaining}
            disabled={busy || busySegment !== null}
            className="text-sm px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 disabled:opacity-40 rounded-lg font-medium transition-colors"
          >
            {isBatchBusy && currentOp?.type === "batch"
              ? "Rendering..."
              : `Render Remaining Shorts (${remainingCount})`}
          </button>
          <button
            onClick={handleRenderAll}
            disabled={busy || busySegment !== null}
            className="text-sm px-3 py-1.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 rounded-lg font-medium transition-colors"
          >
            {isBatchBusy && currentOp?.type === "all" ? "Rendering..." : `Render All ${total} Shorts`}
          </button>
        </div>
      </header>

      {(busy || busySegment !== null) && status && (
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-neutral-400">
            <span>{status.current_step || "Rendering..."}</span>
            <span>{Math.round((status.progress || 0) * 100)}%</span>
          </div>
          <div className="w-full h-1.5 bg-neutral-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-violet-500 transition-all duration-300"
              style={{ width: `${Math.max((status.progress || 0) * 100, 1)}%` }}
            />
          </div>
        </div>
      )}

      {uploadingSegment !== null && uploadStatus && (
        <div className="space-y-1 rounded-lg border border-sky-500/20 bg-sky-500/10 p-3">
          <div className="flex justify-between text-xs text-sky-200">
            <span>{uploadStatus.current_step || "Uploading..."}</span>
            <span>{Math.round((uploadStatus.progress || 0) * 100)}%</span>
          </div>
          <div className="w-full h-1.5 bg-neutral-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-sky-500 transition-all duration-300"
              style={{ width: `${Math.max((uploadStatus.progress || 0) * 100, 1)}%` }}
            />
          </div>
          {uploadStatus.status === "failed" && uploadStatus.error && (
            <p className="text-xs text-red-300">{uploadStatus.error}</p>
          )}
        </div>
      )}

      <ul className="divide-y divide-neutral-800">
        {segments.map((seg, idx) => {
          const url = renderedUrls[idx];
          const downloadsUrl = downloadsUrls[idx];
          const segBusy = busySegment === idx;
          return (
            <li key={idx} className="py-2 flex items-center gap-3">
              <div className="w-6 text-xs text-neutral-500 text-center">{idx + 1}</div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-neutral-200 truncate">{seg.name}</p>
                <div className="mt-1 flex flex-wrap gap-1.5">
                  {PLATFORMS.map((platform) => {
                    const state = platformChipState(idx, platform);
                    const chipClass =
                      state === "Uploaded"
                        ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
                        : state === "Failed"
                          ? "border-red-500/30 bg-red-500/10 text-red-300"
                          : state === "Uploading" || state === "Processing"
                            ? "border-sky-500/30 bg-sky-500/10 text-sky-300"
                            : state === "Ready"
                              ? "border-violet-500/30 bg-violet-500/10 text-violet-300"
                              : "border-neutral-700 bg-neutral-800 text-neutral-500";
                    return (
                      <span
                        key={platform}
                        className={`rounded border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${chipClass}`}
                      >
                        {platform === "youtube" ? "YouTube" : platform === "tiktok" ? "TikTok" : "Instagram"}: {state}
                      </span>
                    );
                  })}
                  {!shortHasSeo(idx) && (
                    <span className="rounded border border-amber-500/30 bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-amber-300">
                      SEO needed
                    </span>
                  )}
                </div>
              </div>
              {downloadsUrl && (
                <button
                  onClick={() => showInFolder(downloadsUrl)}
                  className="text-xs px-2.5 py-1 bg-neutral-800 hover:bg-neutral-700 rounded text-neutral-300 transition-colors"
                >
                  Show in Finder
                </button>
              )}
              <button
                onClick={() => openInBrowser(YOUTUBE_STUDIO_URL)}
                title="Open YouTube"
                className="text-xs px-2 py-1 bg-neutral-800 hover:bg-red-600/80 rounded text-neutral-300 hover:text-white transition-colors"
              >
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0C.488 3.45.029 5.804 0 12c.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0C23.512 20.55 23.971 18.196 24 12c-.029-6.185-.484-8.549-4.385-8.816zM9 16V8l8 4-8 4z" />
                </svg>
              </button>
              <button
                onClick={() => openInBrowser(TIKTOK_STUDIO_UPLOAD_URL)}
                title="Open TikTok Studio"
                className="text-xs px-2 py-1 bg-neutral-800 hover:bg-neutral-900 rounded text-neutral-300 hover:text-white transition-colors"
              >
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-2.88 2.5 2.89 2.89 0 01-2.89-2.89 2.89 2.89 0 012.89-2.89c.28 0 .54.04.79.1V9.01a6.27 6.27 0 00-.79-.05 6.34 6.34 0 00-6.34 6.34 6.34 6.34 0 006.34 6.34 6.34 6.34 0 006.33-6.34V8.95a8.19 8.19 0 004.79 1.53V7.03a4.85 4.85 0 01-1.02-.34z" />
                </svg>
              </button>
              <button
                onClick={() => openInBrowser(INSTAGRAM_URL)}
                title="Open Instagram"
                className="text-xs px-2 py-1 bg-neutral-800 hover:bg-pink-600/80 rounded text-neutral-300 hover:text-white transition-colors"
              >
                <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 2.163c3.204 0 3.584.012 4.85.07 3.252.148 4.771 1.691 4.919 4.919.058 1.265.069 1.645.069 4.849 0 3.205-.012 3.584-.069 4.849-.149 3.225-1.664 4.771-4.919 4.919-1.266.058-1.644.07-4.85.07-3.204 0-3.584-.012-4.849-.07-3.26-.149-4.771-1.699-4.919-4.92-.058-1.265-.07-1.644-.07-4.849 0-3.204.013-3.583.07-4.849.149-3.227 1.664-4.771 4.919-4.919 1.266-.057 1.645-.069 4.849-.069zM12 0C8.741 0 8.333.014 7.053.072 2.695.272.273 2.69.073 7.052.014 8.333 0 8.741 0 12c0 3.259.014 3.668.072 4.948.2 4.358 2.618 6.78 6.98 6.98C8.333 23.986 8.741 24 12 24c3.259 0 3.668-.014 4.948-.072 4.354-.2 6.782-2.618 6.979-6.98.059-1.28.073-1.689.073-4.948 0-3.259-.014-3.667-.072-4.947-.196-4.354-2.617-6.78-6.979-6.98C15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z" />
                </svg>
              </button>
              <button
                onClick={() => handleUploadShort(idx)}
                disabled={!canUpload(idx)}
                className="text-xs px-2.5 py-1 bg-sky-600 hover:bg-sky-500 disabled:opacity-40 rounded text-white transition-colors"
              >
                {uploadButtonLabel(idx)}
              </button>
              <button
                onClick={() => handleRenderOne(idx)}
                disabled={busy || busySegment !== null}
                className="text-xs px-2.5 py-1 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 rounded text-white transition-colors"
              >
                {segBusy ? "..." : url ? "Re-render" : "Render"}
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
