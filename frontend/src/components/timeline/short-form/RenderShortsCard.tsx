import { useState } from "react";
import {
  getShortFormJobStatus,
  renderShortAll,
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
  onRenderComplete: (segmentIdx: number, url: string) => void;
}

export default function RenderShortsCard({
  scriptId,
  segments,
  renderedUrls,
  onRenderComplete,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<ShortFormJobStatus | null>(null);
  const [busySegment, setBusySegment] = useState<number | null>(null);
  const [currentOp, setCurrentOp] = useState<"all" | number | null>(null);

  const total = segments.length;
  const renderedCount = Object.values(renderedUrls).filter(Boolean).length;
  const allDone = renderedCount === total && total > 0;

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
            if (op === "all") {
              (s.output_urls ?? []).forEach((url, i) => onRenderComplete(i, url));
            } else if (typeof op === "number") {
              const url = s.output_urls?.[0];
              if (url) onRenderComplete(op, url);
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
    setBusy(true);
    setCurrentOp("all");
    const { job_id } = await renderShortAll(scriptId);
    startPolling(job_id);
  }

  async function handleRenderOne(idx: number) {
    setBusySegment(idx);
    setCurrentOp(idx);
    const { job_id } = await renderShortOne(scriptId, idx);
    startPolling(job_id);
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
        <button
          onClick={handleRenderAll}
          disabled={busy || busySegment !== null}
          className="text-sm px-3 py-1.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 rounded-lg font-medium transition-colors"
        >
          {busy ? "Rendering..." : `Render All ${total} Shorts`}
        </button>
      </header>

      {busy && status && (
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
          const segBusy = busySegment === idx;
          return (
            <li key={idx} className="py-2 flex items-center gap-3">
              <div className="w-6 text-xs text-neutral-500 text-center">{idx + 1}</div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-neutral-200 truncate">{seg.name}</p>
              </div>
              {url && !url.startsWith("/static/") && (
                <button
                  onClick={() => showInFolder(url)}
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
