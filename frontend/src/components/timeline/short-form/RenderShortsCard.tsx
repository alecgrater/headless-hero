import { useState } from "react";
import {
  getShortFormJobStatus,
  renderShortAll,
  renderShortBatch,
  renderShortOne,
  showInFolder,
} from "../../../api";
import { usePollJob } from "../../../hooks/usePollJob";
import type { ShortFormJobStatus } from "../../../types/render";

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
  onRefreshRendered: () => Promise<Record<number, string | undefined>>;
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
  onRefreshRendered,
  onRenderComplete,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<ShortFormJobStatus | null>(null);
  const [busySegment, setBusySegment] = useState<number | null>(null);
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
