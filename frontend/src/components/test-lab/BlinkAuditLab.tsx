import { AlertTriangle, CheckCircle2, Loader2, RefreshCw, ScanFace } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { assetUrl, getBlinkAuditReports, runBlinkAudit } from "../../api";
import type { FullFrameBlinkAuditReport, FullFrameBlinkCandidate } from "../../types/testLab";

export default function BlinkAuditLab() {
  const [reports, setReports] = useState<FullFrameBlinkAuditReport[]>([]);
  const [activeReport, setActiveReport] = useState<FullFrameBlinkAuditReport | null>(null);
  const [running, setRunning] = useState(false);
  const [eligibleOnly, setEligibleOnly] = useState(false);

  async function refreshReports() {
    const next = await getBlinkAuditReports();
    setReports(next);
    setActiveReport((current) => current ?? next[0] ?? null);
  }

  useEffect(() => {
    refreshReports();
  }, []);

  async function handleRun() {
    setRunning(true);
    try {
      const report = await runBlinkAudit();
      if (!report) return;
      setActiveReport(report);
      setReports((current) => [report, ...current.filter((item) => item.id !== report.id)]);
    } finally {
      setRunning(false);
    }
  }

  const eligibleCount = useMemo(
    () => activeReport?.candidates.filter((candidate) => candidate.detection.eligible).length ?? 0,
    [activeReport],
  );
  const visibleCandidates = useMemo(
    () => activeReport?.candidates.filter((candidate) => !eligibleOnly || candidate.detection.eligible) ?? [],
    [activeReport, eligibleOnly],
  );

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <div className="flex items-center justify-between gap-4 rounded-lg border border-neutral-800 bg-neutral-900/60 p-4">
        <div>
          <p className="text-xs font-semibold uppercase text-neutral-500">Blink Audit</p>
          <h2 className="mt-2 text-sm font-semibold text-neutral-100">Full-frame Burger King scenes</h2>
          <p className="mt-1 text-xs leading-5 text-neutral-500">
            Checks real generated scene images for safe in-place blink anchors.
          </p>
        </div>
        <button
          onClick={handleRun}
          disabled={running}
          className="inline-flex items-center gap-2 rounded-md bg-violet-600 px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-violet-500 disabled:cursor-not-allowed disabled:bg-neutral-800 disabled:text-neutral-500"
        >
          {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <ScanFace className="h-4 w-4" />}
          Run Blink Audit
        </button>
      </div>

      <div className="grid min-h-0 flex-1 gap-4 overflow-hidden lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="min-h-0 overflow-y-auto rounded-lg border border-neutral-800 bg-neutral-900/60 p-3">
          <button
            onClick={refreshReports}
            className="mb-3 inline-flex w-full items-center justify-center gap-2 rounded-md border border-neutral-800 px-3 py-2 text-xs font-medium text-neutral-300 transition-colors hover:border-neutral-700 hover:text-neutral-100"
          >
            <RefreshCw className="h-4 w-4" />
            Refresh Reports
          </button>
          <div className="space-y-2">
            {reports.map((report) => (
              <button
                key={report.id}
                onClick={() => setActiveReport(report)}
                className={`w-full rounded-md border p-3 text-left transition-colors ${
                  activeReport?.id === report.id
                    ? "border-violet-500 bg-violet-500/15"
                    : "border-neutral-800 bg-neutral-950/50 hover:border-neutral-700"
                }`}
              >
                <p className="text-xs font-medium text-neutral-100">{report.title}</p>
                <p className="mt-1 text-xs text-neutral-500">{report.candidates.length} scenes</p>
              </button>
            ))}
          </div>
        </aside>

        <section className="min-h-0 overflow-y-auto rounded-lg border border-neutral-800 bg-neutral-900/60 p-4">
          {activeReport ? (
            <>
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold text-neutral-100">{activeReport.title}</h3>
                  <p className="mt-1 text-xs text-neutral-500">
                    {eligibleCount}/{activeReport.candidates.length} eligible
                    {eligibleOnly ? ` · showing ${visibleCandidates.length}` : ""}
                  </p>
                </div>
                <label className="inline-flex items-center gap-2 rounded-md border border-neutral-800 bg-neutral-950/50 px-3 py-2 text-xs font-medium text-neutral-300">
                  <input
                    type="checkbox"
                    checked={eligibleOnly}
                    onChange={(event) => setEligibleOnly(event.target.checked)}
                    className="h-4 w-4 rounded border-neutral-700 bg-neutral-950 text-violet-500"
                  />
                  Eligible only
                </label>
              </div>
              {visibleCandidates.length > 0 ? (
                <div className="grid gap-3 xl:grid-cols-2">
                  {visibleCandidates.map((candidate) => (
                    <BlinkAuditCard key={candidate.scene_id} candidate={candidate} />
                  ))}
                </div>
              ) : (
                <div className="rounded-md border border-dashed border-neutral-800 bg-neutral-950/50 p-6 text-sm text-neutral-500">
                  No scenes match the current filter.
                </div>
              )}
            </>
          ) : (
            <div className="rounded-md border border-dashed border-neutral-800 bg-neutral-950/50 p-6 text-sm text-neutral-500">
              Run a Blink Audit to inspect full-frame scene eligibility.
            </div>
          )}
        </section>
      </div>
    </div>
  );
}

function BlinkAuditCard({ candidate }: { candidate: FullFrameBlinkCandidate }) {
  return (
    <div className="overflow-hidden rounded-lg border border-neutral-800 bg-neutral-950/50">
      <div className="grid grid-cols-2 border-b border-neutral-800">
        <PreviewPane candidate={candidate} blink={false} />
        <PreviewPane candidate={candidate} blink />
      </div>
      <div className="space-y-2 p-3">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm font-medium text-neutral-100">{candidate.scene_id}</p>
          <span className={`inline-flex items-center gap-1 rounded-full px-2 py-1 text-xs font-medium ${
            candidate.detection.eligible ? "bg-emerald-500/15 text-emerald-300" : "bg-amber-500/15 text-amber-300"
          }`}>
            {candidate.detection.eligible ? <CheckCircle2 className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3" />}
            {candidate.detection.eligible ? "Eligible" : "Rejected"}
          </span>
        </div>
        <p className="line-clamp-2 text-xs leading-5 text-neutral-500">{candidate.scene_label}</p>
        {!candidate.detection.eligible ? (
          <p className="text-xs text-amber-300">{candidate.detection.reason}</p>
        ) : (
          <p className="text-xs text-emerald-300">
            {candidate.blink_enabled ? "50% gate: blink enabled" : "50% gate: blink skipped"}
          </p>
        )}
      </div>
    </div>
  );
}

function PreviewPane({ candidate, blink }: { candidate: FullFrameBlinkCandidate; blink: boolean }) {
  return (
    <div className="relative aspect-video overflow-hidden bg-neutral-950">
      <img src={assetUrl(candidate.image_url)} alt="" className="h-full w-full object-cover" />
      {blink && candidate.detection.eligible ? <BlinkAnchorOverlay anchor={candidate.detection.anchor} /> : null}
      <div className="absolute left-2 top-2 rounded bg-black/65 px-2 py-1 text-[10px] font-medium uppercase text-neutral-200">
        {blink ? "Blink" : "Still"}
      </div>
    </div>
  );
}

function BlinkAnchorOverlay({ anchor }: { anchor?: Record<string, unknown> | null }) {
  const left = pointFromAnchor(anchor, "eye_left");
  const right = pointFromAnchor(anchor, "eye_right");
  const skinFill = typeof anchor?.skin_fill === "string" ? anchor.skin_fill : "#D9A374";
  if (!left || !right) return null;
  return (
    <svg className="absolute inset-0 h-full w-full" viewBox="0 0 100 100" preserveAspectRatio="none">
      {[left, right].map((eye, index) => {
        const width = Math.max((eye.width ?? 0.028) * 130, 3.4);
        const height = Math.max((eye.height ?? 0.018) * 160, 2.3);
        const x = eye.x * 100;
        const y = eye.y * 100;
        return (
          <g key={index}>
            <rect
              x={x - width / 2}
              y={y - height / 2}
              width={width}
              height={height}
              rx={height / 2}
              fill={skinFill}
            />
            <path
              d={`M${x - width * 0.36} ${y} Q${x} ${y - height * 0.22} ${x + width * 0.36} ${y}`}
              fill="none"
              stroke="#2A1712"
              strokeWidth="0.8"
              strokeLinecap="round"
            />
          </g>
        );
      })}
    </svg>
  );
}

function pointFromAnchor(anchor: Record<string, unknown> | null | undefined, key: string) {
  const raw = anchor?.[key];
  if (!raw || typeof raw !== "object") return null;
  const point = raw as Record<string, unknown>;
  if (typeof point.x !== "number" || typeof point.y !== "number") return null;
  return {
    x: point.x,
    y: point.y,
    width: typeof point.width === "number" ? point.width : undefined,
    height: typeof point.height === "number" ? point.height : undefined,
  };
}
