import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Clock, Film, Image, Music, Package, PlayCircle, Video, X } from "lucide-react";
import { assetUrl } from "../../api";
import type { ScriptCostBreakdownItem } from "../../api";
import type { TestLabAsset, TestLabLogEntry, TestLabRun } from "../../types/testLab";

interface TestLabRunPanelProps {
  activeRun: TestLabRun | null;
  runs: TestLabRun[];
  running: boolean;
  currentStep: string;
  progress?: number;
  onSelectRun: (run: TestLabRun) => void;
}

export default function TestLabRunPanel({
  activeRun,
  runs,
  running,
  currentStep,
  progress,
  onSelectRun,
}: TestLabRunPanelProps) {
  const history = runs.slice(0, 20);
  const cost = normalizeCost(activeRun);
  const [previewAsset, setPreviewAsset] = useState<TestLabAsset | null>(null);

  return (
    <div className="space-y-4">
      <section className="rounded-lg border border-neutral-800 bg-neutral-950/50 p-3">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase text-neutral-500">Run</p>
            <p className="mt-2 text-sm font-medium text-neutral-200">{currentStep}</p>
          </div>
          <StatusPill status={activeRun?.status ?? (running ? "running" : "pending")} />
        </div>
        {progress !== undefined && (
          <div className="mt-3 h-1.5 rounded-full bg-neutral-800">
            <div
              className="h-full rounded-full bg-violet-500 transition-all"
              style={{ width: `${Math.max(0, Math.min(100, progress * 100))}%` }}
            />
          </div>
        )}
        {activeRun?.error && (
          <p className="mt-3 rounded-md border border-red-500/30 bg-red-500/10 p-2 text-xs leading-5 text-red-200">
            {activeRun.error}
          </p>
        )}
      </section>

      <section className="rounded-lg border border-neutral-800 bg-neutral-950/50 p-3">
        <div className="mb-3 flex items-center gap-2">
          <PlayCircle className="h-4 w-4 text-violet-300" />
          <h3 className="text-xs font-semibold uppercase text-neutral-400">Preview</h3>
        </div>
        {activeRun?.render_url ? (
          <video
            key={activeRun.render_url}
            controls
            playsInline
            src={assetUrl(activeRun.render_url)}
            className="aspect-video w-full rounded-md border border-neutral-800 bg-black object-contain"
          />
        ) : (
          <EmptyState label="No rendered preview yet." />
        )}
      </section>

      <section className="rounded-lg border border-neutral-800 bg-neutral-950/50 p-3">
        <div className="mb-3 flex items-center gap-2">
          <Package className="h-4 w-4 text-sky-300" />
          <h3 className="text-xs font-semibold uppercase text-neutral-400">Generated assets</h3>
        </div>
        {activeRun?.assets?.length ? (
          <div className="grid grid-cols-2 gap-2">
            {activeRun.assets.map((asset, index) => (
              <AssetCard key={`${asset.kind}-${asset.url}-${index}`} asset={asset} onOpen={setPreviewAsset} />
            ))}
          </div>
        ) : (
          <EmptyState label="Generated files will appear here after a run starts." />
        )}
      </section>

      <CostBreakdownPanel totalCost={cost.totalCost} breakdown={cost.breakdown} />

      <section className="rounded-lg border border-neutral-800 bg-neutral-950/50 p-3">
        <div className="mb-3 flex items-center gap-2">
          <Clock className="h-4 w-4 text-emerald-300" />
          <h3 className="text-xs font-semibold uppercase text-neutral-400">Stage logs</h3>
        </div>
        {activeRun?.logs?.length ? (
          <div className="max-h-64 space-y-2 overflow-y-auto pr-1">
            {activeRun.logs.map((log, index) => (
              <LogRow key={`${log.stage}-${log.created_at ?? log.at ?? index}`} log={log} />
            ))}
          </div>
        ) : (
          <EmptyState label="No stage logs yet." />
        )}
      </section>

      <section className="rounded-lg border border-neutral-800 bg-neutral-950/50 p-3">
        <h3 className="text-xs font-semibold uppercase text-neutral-400">History</h3>
        <div className="mt-3 space-y-2">
          {history.length === 0 && <EmptyState label="No Test Lab runs yet." />}
          {history.map((run) => (
            <button
              key={run.run_id}
              type="button"
              onClick={() => onSelectRun(run)}
              className={`w-full rounded-md border p-2 text-left text-xs transition-colors ${
                activeRun?.run_id === run.run_id
                  ? "border-violet-500 bg-violet-500/15"
                  : "border-neutral-800 bg-neutral-950/70 hover:border-neutral-700"
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate font-medium text-neutral-200">{run.preset_id}</p>
                  <p className="mt-1 truncate text-neutral-500">{formatDate(run.created_at ?? run.started_at ?? run.updated_at)}</p>
                </div>
                <span className="shrink-0 text-neutral-500">{run.status}</span>
              </div>
            </button>
          ))}
        </div>
      </section>

      {previewAsset && (
        <AssetPreviewModal
          asset={previewAsset}
          onClose={() => setPreviewAsset(null)}
        />
      )}
    </div>
  );
}

function AssetCard({ asset, onOpen }: { asset: TestLabAsset; onOpen: (asset: TestLabAsset) => void }) {
  const source = asset.url || asset.path || "";
  const label = asset.label || assetKindLabel(asset.kind);
  const sourceUrl = source ? assetUrl(source) : "";

  return (
    <button
      type="button"
      onClick={() => source && onOpen(asset)}
      disabled={!source}
      className="group min-w-0 overflow-hidden rounded-md border border-neutral-800 bg-neutral-950/70 text-left transition-colors hover:border-neutral-700 disabled:cursor-not-allowed disabled:opacity-60"
      title={source ? `Preview ${label}` : `${label} is not available yet`}
    >
      <div className="flex aspect-video items-center justify-center bg-neutral-900">
        {asset.kind === "image" || asset.kind === "treatment_asset" ? (
          source ? (
            <img src={sourceUrl} alt={label} className="h-full w-full object-cover" />
          ) : (
            <AssetIcon asset={asset} />
          )
        ) : asset.kind === "video" || asset.kind === "render" ? (
          source ? (
            <video src={sourceUrl} muted playsInline className="h-full w-full object-cover" />
          ) : (
            <AssetIcon asset={asset} />
          )
        ) : (
          <AssetIcon asset={asset} />
        )}
      </div>
      <div className="p-2">
        <p className="truncate text-xs font-medium text-neutral-200 group-hover:text-neutral-100">{label}</p>
        <p className="mt-1 text-[11px] text-neutral-500">{assetKindLabel(asset.kind)}</p>
      </div>
    </button>
  );
}

function AssetPreviewModal({ asset, onClose }: { asset: TestLabAsset; onClose: () => void }) {
  const source = asset.url || asset.path || "";
  const sourceUrl = source ? assetUrl(source) : "";
  const label = asset.label || assetKindLabel(asset.kind);

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm" onClick={onClose}>
      <div
        className="flex max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-lg border border-neutral-700 bg-neutral-950 shadow-2xl shadow-black/70"
        role="dialog"
        aria-modal="true"
        aria-labelledby="test-lab-asset-preview-title"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between gap-3 border-b border-neutral-800 px-4 py-3">
          <div className="min-w-0">
            <h3 id="test-lab-asset-preview-title" className="truncate text-sm font-semibold text-neutral-100">
              {label}
            </h3>
            <p className="mt-0.5 text-xs text-neutral-500">{assetKindLabel(asset.kind)}</p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md border border-neutral-800 text-neutral-400 transition-colors hover:border-neutral-700 hover:bg-neutral-900 hover:text-neutral-100"
            aria-label="Close asset preview"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex min-h-0 flex-1 items-center justify-center bg-neutral-950 p-4">
          {asset.kind === "image" || asset.kind === "treatment_asset" ? (
            <img src={sourceUrl} alt={label} className="max-h-[78vh] max-w-full rounded-md object-contain" />
          ) : asset.kind === "video" || asset.kind === "render" ? (
            <video
              key={sourceUrl}
              controls
              autoPlay
              playsInline
              src={sourceUrl}
              className="max-h-[78vh] w-full rounded-md bg-black object-contain"
            />
          ) : asset.kind === "audio" ? (
            <div className="w-full max-w-2xl rounded-lg border border-neutral-800 bg-neutral-900 p-5">
              <div className="mb-4 flex justify-center">
                <Music className="h-10 w-10 text-neutral-500" />
              </div>
              <audio key={sourceUrl} controls autoPlay src={sourceUrl} className="w-full" />
            </div>
          ) : (
            <div className="flex h-64 w-full items-center justify-center rounded-md border border-neutral-800 bg-neutral-900">
              <AssetIcon asset={asset} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function AssetIcon({ asset }: { asset: TestLabAsset }) {
  const className = "h-5 w-5 text-neutral-500";
  if (asset.kind === "video") return <Video className={className} />;
  if (asset.kind === "render") return <Film className={className} />;
  if (asset.kind === "audio") return <Music className={className} />;
  if (asset.kind === "image") return <Image className={className} />;
  return <Package className={className} />;
}

function assetKindLabel(kind: TestLabAsset["kind"]) {
  if (kind === "video") return "Video asset";
  if (kind === "render") return "Render";
  if (kind === "treatment_asset") return "Animation asset";
  if (kind === "audio") return "Audio";
  if (kind === "image") return "Image";
  return "Asset";
}

function normalizeCost(run: TestLabRun | null): { totalCost: number; breakdown: ScriptCostBreakdownItem[] } {
  if (!run) return { totalCost: 0, breakdown: [] };
  if (Array.isArray(run.cost_breakdown)) {
    return {
      totalCost: run.total_cost ?? run.cost_total ?? sumCosts(run.cost_breakdown),
      breakdown: run.cost_breakdown,
    };
  }

  const raw = run.cost_breakdown as Record<string, unknown> | undefined;
  const rawBreakdown = raw?.breakdown;
  const breakdown = Array.isArray(rawBreakdown) ? rawBreakdown.filter(isCostItem) : [];
  const rawTotal = typeof raw?.total_cost === "number" ? raw.total_cost : undefined;

  return {
    totalCost: run.total_cost ?? run.cost_total ?? rawTotal ?? sumCosts(breakdown),
    breakdown,
  };
}

function isCostItem(item: unknown): item is ScriptCostBreakdownItem {
  if (!item || typeof item !== "object") return false;
  const record = item as Record<string, unknown>;
  return typeof record.task === "string" && typeof record.total_cost === "number";
}

function sumCosts(items: ScriptCostBreakdownItem[]) {
  return items.reduce((total, item) => total + item.total_cost, 0);
}

function formatCost(cost: number) {
  if (cost === 0) return "$0.00";
  if (cost < 0.01) return `$${cost.toFixed(4)}`;
  return `$${cost.toFixed(2)}`;
}

function formatCostMetrics(item: ScriptCostBreakdownItem) {
  const parts: string[] = [];
  if (item.call_count > 0) parts.push(`${item.call_count} call${item.call_count !== 1 ? "s" : ""}`);
  if (item.images > 0) parts.push(`${item.images} image${item.images !== 1 ? "s" : ""}`);
  if (item.characters > 0) parts.push(`${item.characters.toLocaleString()} chars`);
  if (item.input_tokens + item.output_tokens > 0) {
    parts.push(`${(item.input_tokens + item.output_tokens).toLocaleString()} tok`);
  }
  return parts.join(" · ");
}

function CostBreakdownPanel({ totalCost, breakdown }: { totalCost: number; breakdown: ScriptCostBreakdownItem[] }) {
  return (
    <section className="overflow-hidden rounded-lg border border-neutral-800 bg-neutral-950/50">
      <div className="flex items-center justify-between border-b border-neutral-800 px-3 py-2">
        <span className="text-xs font-semibold uppercase text-neutral-400">Cost breakdown</span>
        <span className="text-xs font-mono text-emerald-300">{formatCost(totalCost)}</span>
      </div>
      <div className="max-h-64 overflow-y-auto py-1">
        {breakdown.length > 0 ? (
          breakdown.map((item) => (
            <div key={`${item.task}-${item.service}-${item.operation}-${item.model}`} className="px-3 py-2 transition-colors hover:bg-neutral-900">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-xs font-medium text-neutral-100">{item.task}</p>
                  <p className="mt-0.5 truncate text-[11px] text-neutral-500">
                    {[item.service, item.model].filter(Boolean).join(" · ")}
                  </p>
                  <p className="mt-1 text-[11px] text-neutral-500">{formatCostMetrics(item)}</p>
                </div>
                <span className="shrink-0 text-xs font-mono text-emerald-300">{formatCost(item.total_cost)}</span>
              </div>
            </div>
          ))
        ) : (
          <EmptyState label="No tracked API usage yet." />
        )}
      </div>
    </section>
  );
}

function LogRow({ log }: { log: TestLabLogEntry }) {
  return (
    <div className="rounded-md border border-neutral-800 bg-neutral-950/70 p-2">
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          {log.status === "completed" ? (
            <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-300" />
          ) : log.status === "failed" || log.level === "error" ? (
            <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-red-300" />
          ) : (
            <Clock className="h-3.5 w-3.5 shrink-0 text-neutral-500" />
          )}
          <p className="truncate text-xs font-medium text-neutral-200">{log.stage || "stage"}</p>
        </div>
        <span className="shrink-0 text-[11px] text-neutral-500">{log.status}</span>
      </div>
      <p className="mt-1 text-xs leading-5 text-neutral-500">{log.message}</p>
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const className =
    status === "completed"
      ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
      : status === "failed" || status === "cancelled"
        ? "border-red-500/40 bg-red-500/10 text-red-300"
        : status === "running" || status === "queued"
          ? "border-violet-500/40 bg-violet-500/10 text-violet-300"
          : "border-neutral-800 bg-neutral-900 text-neutral-400";

  return (
    <span className={`rounded-md border px-2 py-1 text-xs ${className}`}>
      {status}
    </span>
  );
}

function EmptyState({ label }: { label: string }) {
  return (
    <p className="rounded-md border border-neutral-800 bg-neutral-950/70 p-3 text-center text-xs text-neutral-500">
      {label}
    </p>
  );
}

function formatDate(value?: string | null) {
  if (!value) return "Unknown time";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
