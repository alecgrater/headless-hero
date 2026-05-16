import { useState } from "react";
import {
  generateShortIntroOne,
  generateShortIntrosAll,
  getShortFormJobStatus,
  assetUrl,
} from "../../../api";
import { usePollJob } from "../../../hooks/usePollJob";
import type { ShortFormJobStatus, ShortIntro } from "../../../types/render";

interface Props {
  scriptId: string;
  videoTitle: string;
  segments: { name: string }[];
  intros: ShortIntro[] | null | undefined;
  onIntrosChanged: () => void; // refetch script after generation completes
}

function buildDisplayPreview(videoTitle: string, segmentName: string): string {
  const stripped = videoTitle.replace(/^\d+\s+/, "");
  return `${stripped} — ${segmentName}`;
}

export default function ShortIntrosCard({
  scriptId,
  videoTitle,
  segments,
  intros,
  onIntrosChanged,
}: Props) {
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<ShortFormJobStatus | null>(null);

  const introMap = new Map<number, ShortIntro>();
  (intros ?? []).forEach((i) => introMap.set(i.segment_idx, i));
  const generatedCount = introMap.size;
  const total = segments.length;
  const allDone = generatedCount === total && total > 0;

  function isStale(idx: number): boolean {
    const existing = introMap.get(idx);
    if (!existing) return false;
    const expected = buildDisplayPreview(videoTitle, segments[idx].name);
    return existing.display_text !== expected;
  }

  const staleIndexes = segments
    .map((_, i) => i)
    .filter((i) => introMap.has(i) && isStale(i));

  const { startPolling } = usePollJob<ShortFormJobStatus>({
    pollFn: (id) => getShortFormJobStatus(id),
    isComplete: (s) => s.status === "completed",
    isFailed: (s) => s.status === "failed",
    onStatus: (s) => {
      setStatus(s);
      if (s.status === "completed" || s.status === "failed") {
        setBusy(false);
        if (s.status === "completed") {
          onIntrosChanged();
        }
      }
    },
    onConnectionLost: () => setBusy(false),
  });

  async function handleGenerateAll() {
    setBusy(true);
    const { job_id } = await generateShortIntrosAll(scriptId, /* force */ false);
    startPolling(job_id);
  }

  async function handleRegenAll() {
    setBusy(true);
    const { job_id } = await generateShortIntrosAll(scriptId, /* force */ true);
    startPolling(job_id);
  }

  async function handleRegenOne(idx: number) {
    setBusy(true);
    const { job_id } = await generateShortIntroOne(scriptId, idx);
    startPolling(job_id);
  }

  const statusColor = allDone
    ? staleIndexes.length > 0
      ? "text-amber-400"
      : "text-emerald-400"
    : "text-amber-400";
  const statusLabel = allDone
    ? staleIndexes.length > 0
      ? `${generatedCount}/${total} generated · ${staleIndexes.length} stale`
      : `${total}/${total} generated`
    : `${generatedCount}/${total} generated — required before render`;

  return (
    <section className="bg-neutral-900 border border-neutral-800 rounded-xl p-4 space-y-3">
      <header className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-neutral-200">Short Form Intros</h3>
          <p className={`text-xs ${statusColor}`}>{statusLabel}</p>
        </div>
        <div className="flex items-center gap-2">
          {!allDone && (
            <button
              onClick={handleGenerateAll}
              disabled={busy}
              className="text-sm px-3 py-1.5 bg-violet-600 hover:bg-violet-500 disabled:opacity-40 rounded-lg font-medium transition-colors"
            >
              Generate All Intros
            </button>
          )}
          {allDone && (
            <button
              onClick={handleRegenAll}
              disabled={busy}
              className="text-sm px-3 py-1.5 bg-neutral-800 hover:bg-neutral-700 disabled:opacity-40 rounded-lg font-medium transition-colors"
            >
              Regenerate All
            </button>
          )}
        </div>
      </header>

      {busy && status && (
        <div className="space-y-1">
          <div className="flex justify-between text-xs text-neutral-400">
            <span>{status.current_step || "Working..."}</span>
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
          const intro = introMap.get(idx);
          const stale = intro && isStale(idx);
          const preview = buildDisplayPreview(videoTitle, seg.name);
          return (
            <li key={idx} className="py-2 flex items-center gap-3">
              <div className="w-6 text-xs text-neutral-500 text-center">{idx + 1}</div>
              <div className="flex-1 min-w-0">
                <p className="text-sm text-neutral-200 truncate">{seg.name}</p>
                <p className="text-[11px] text-neutral-500 truncate">{preview}</p>
              </div>
              {intro && (
                <audio
                  src={assetUrl(intro.audio_url)}
                  controls
                  className="h-7"
                  style={{ maxWidth: 200 }}
                />
              )}
              <button
                onClick={() => handleRegenOne(idx)}
                disabled={busy}
                className={`text-xs px-2.5 py-1 rounded transition-colors ${
                  stale
                    ? "bg-amber-600 hover:bg-amber-500 text-white"
                    : intro
                      ? "bg-neutral-800 hover:bg-neutral-700 text-neutral-300"
                      : "bg-violet-600 hover:bg-violet-500 text-white"
                } disabled:opacity-40`}
              >
                {!intro ? "Generate" : stale ? "Regenerate (stale)" : "Regenerate"}
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
