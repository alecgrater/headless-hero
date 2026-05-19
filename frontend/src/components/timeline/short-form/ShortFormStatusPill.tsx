import { useCallback, useEffect, useRef, useState } from "react";
import { getExportFileStatus, type ExportFileCategoryStatus, type ExportFileStatus } from "../../../api";

interface Props {
  scriptId: string;
  segmentCount: number;
}

export default function ShortFormStatusPill({
  scriptId,
  segmentCount,
}: Props) {
  const [status, setStatus] = useState<ExportFileStatus | null>(null);
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const latestScriptIdRef = useRef(scriptId);
  const requestSeqRef = useRef(0);

  useEffect(() => {
    latestScriptIdRef.current = scriptId;
    setStatus(null);
  }, [scriptId]);

  const refresh = useCallback(async () => {
    const requestedScriptId = scriptId;
    const requestId = requestSeqRef.current + 1;
    requestSeqRef.current = requestId;
    try {
      const nextStatus = await getExportFileStatus(requestedScriptId);
      if (requestSeqRef.current !== requestId || latestScriptIdRef.current !== requestedScriptId) return;
      setStatus(nextStatus);
    } catch {
      if (requestSeqRef.current !== requestId || latestScriptIdRef.current !== requestedScriptId) return;
      setStatus(null);
    }
  }, [scriptId]);

  useEffect(() => {
    void refresh();
  }, [refresh, segmentCount]);

  useEffect(() => {
    if (!open) return;

    function handlePointerDown(event: PointerEvent) {
      const target = event.target;
      if (!(target instanceof Node)) return;
      if (wrapperRef.current?.contains(target)) return;
      setOpen(false);
    }

    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, [open]);

  const exported = status?.exported ?? 0;
  const total = status?.total ?? segmentCount * 3 + 3;

  return (
    <div ref={wrapperRef} className="relative shrink-0">
      <button
        type="button"
        onClick={() => {
          setOpen((show) => !show);
          void refresh();
        }}
        title="Show exported file breakdown"
        className="inline-flex h-7 w-[10.25rem] shrink-0 items-center justify-center whitespace-nowrap text-xs px-2.5 bg-neutral-800 hover:bg-neutral-700 rounded-md text-neutral-300 transition-colors tabular-nums"
      >
        Exports: {exported}/{total} files
      </button>
      {open && (
        <ExportFileBreakdownPopover status={status} segmentCount={segmentCount} />
      )}
    </div>
  );
}

function ExportFileBreakdownPopover({
  status,
  segmentCount,
}: {
  status: ExportFileStatus | null;
  segmentCount: number;
}) {
  const fallbackTotal = segmentCount * 3 + 3;
  const rows: Array<[string, ExportFileCategoryStatus]> = status
    ? [
        ["longform_video", status.categories.longform_video],
        ["longform_thumbnail", status.categories.longform_thumbnail],
        ["longform_seo", status.categories.longform_seo],
        ["shortform_videos", status.categories.shortform_videos],
        ["shortform_thumbnails", status.categories.shortform_thumbnails],
        ["shortform_seo", status.categories.shortform_seo],
      ].filter((entry): entry is [string, ExportFileCategoryStatus] => Boolean(entry[1]))
    : [];

  return (
    <div className="absolute right-0 top-8 z-40 w-72 rounded-lg border border-neutral-700 bg-neutral-950 shadow-2xl shadow-black/50">
      <div className="flex items-center justify-between border-b border-neutral-800 px-3 py-2">
        <span className="text-xs font-semibold text-neutral-200">Exported files</span>
        <span className="text-xs font-mono text-sky-300 tabular-nums">
          {status ? `${status.exported}/${status.total}` : `0/${fallbackTotal}`}
        </span>
      </div>
      <div className="py-1">
        {rows.length > 0 ? (
          rows.map(([key, row]) => (
            <div key={key} className="px-3 py-2">
              <div className="flex items-center justify-between gap-3">
                <span className="text-xs font-medium text-neutral-300">{row.label}</span>
                <span className="text-xs font-mono text-neutral-200 tabular-nums">
                  {row.exported}/{row.total}
                </span>
              </div>
            </div>
          ))
        ) : (
          <div className="px-3 py-5 text-center text-xs text-neutral-500">
            Export folder status is unavailable.
          </div>
        )}
      </div>
      {status && (
        <div className="border-t border-neutral-800 px-3 py-2">
          <p className="truncate text-[11px] text-neutral-500" title={status.folder_path}>
            {status.folder_path}
          </p>
        </div>
      )}
    </div>
  );
}
