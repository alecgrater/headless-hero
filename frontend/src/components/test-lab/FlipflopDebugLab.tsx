import { AlertTriangle, CheckCircle2, Eye, Film, Loader2, RefreshCw, RotateCcw, Sparkles } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  analyzeFlipflopDebugAsset,
  assetUrl,
  bumpAssetVersion,
  createFlipflopFixtureAsset,
  getFlipflopDebugAssets,
  renderFlipflopFixturePreview,
} from "../../api";
import type {
  FlipflopDebugAction,
  FlipflopDebugAsset,
  FlipflopDebugResult,
  FlipflopFixtureRenderResult,
  FlipflopFixtureResult,
} from "../../types/testLab";

const ACTIONS: Array<{ value: FlipflopDebugAction; label: string }> = [
  { value: "blink", label: "Blink" },
  { value: "speaking_mouth", label: "Speaking mouth" },
  { value: "eye_glance", label: "Eye glance" },
  { value: "eyebrow_raise", label: "Eyebrow raise" },
];
const FIXTURE_SCRIPT_ID = "test-lab-flipflop-fixtures";

export default function FlipflopDebugLab() {
  const [assets, setAssets] = useState<FlipflopDebugAsset[]>([]);
  const [selectedAssetId, setSelectedAssetId] = useState("");
  const [action, setAction] = useState<FlipflopDebugAction>("blink");
  const [result, setResult] = useState<FlipflopDebugResult | null>(null);
  const [fixtureResult, setFixtureResult] = useState<FlipflopFixtureResult | null>(null);
  const [renderResult, setRenderResult] = useState<FlipflopFixtureRenderResult | null>(null);
  const [loadingAssets, setLoadingAssets] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [generatingFixture, setGeneratingFixture] = useState(false);
  const [renderingFixture, setRenderingFixture] = useState(false);
  const [error, setError] = useState("");

  const selectedAsset = useMemo(
    () => assets.find((asset) => asset.asset_id === selectedAssetId) ?? null,
    [assets, selectedAssetId],
  );
  const fixtureAssetExists = assets.some((asset) => asset.script_id === FIXTURE_SCRIPT_ID);

  const loadAssets = useCallback(async () => {
    setLoadingAssets(true);
    setError("");
    try {
      const nextAssets = await getFlipflopDebugAssets();
      setAssets(nextAssets);
      setSelectedAssetId((current) => (
        nextAssets.some((asset) => asset.asset_id === current) ? current : nextAssets[0]?.asset_id || ""
      ));
    } finally {
      setLoadingAssets(false);
    }
  }, []);

  useEffect(() => {
    loadAssets();
  }, [loadAssets]);

  async function runAnalysis(assetId = selectedAssetId) {
    if (!assetId || analyzing) return;
    setAnalyzing(true);
    setError("");
    try {
      const next = await analyzeFlipflopDebugAsset(assetId, action);
      if (!next) {
        setError("The selected flip-flop asset could not be analyzed.");
        return;
      }
      if (next.debug_url) bumpAssetVersion(next.debug_url);
      setResult(next);
    } finally {
      setAnalyzing(false);
    }
  }

  async function handleCreateFixture() {
    if (generatingFixture || fixtureAssetExists) return;
    setGeneratingFixture(true);
    setError("");
    try {
      const next = await createFlipflopFixtureAsset();
      if (!next) {
        setError("The flip-flop fixture assets could not be generated.");
        return;
      }
      bumpAssetVersion(next.asset.asset_url);
      setFixtureResult(next);
      setAssets((current) => upsertAsset(current, next.asset));
      setSelectedAssetId(next.asset.asset_id);
      setResult(null);
      setRenderResult(null);
    } finally {
      setGeneratingFixture(false);
    }
  }

  async function handleRenderFixture() {
    if (!selectedAssetId || renderingFixture) return;
    setRenderingFixture(true);
    setError("");
    try {
      const next = await renderFlipflopFixturePreview(selectedAssetId, action);
      if (!next) {
        setError("The saved flip-flop fixture could not be rendered.");
        return;
      }
      bumpAssetVersion(next.render_url);
      setRenderResult(next);
    } finally {
      setRenderingFixture(false);
    }
  }

  return (
    <div className="grid h-full min-h-0 gap-4 overflow-hidden lg:grid-cols-[320px_minmax(0,1fr)]">
      <aside className="min-h-0 overflow-hidden rounded-lg border border-neutral-800 bg-neutral-900/60">
        <div className="border-b border-neutral-800 p-4">
          <p className="text-xs font-semibold uppercase text-neutral-500">Flip-flop</p>
          <h2 className="mt-2 text-sm font-semibold text-neutral-100">Cached saved cutouts</h2>
          <p className="mt-1 text-xs leading-5 text-neutral-500">
            Reuse generated flip-flop bases, character cutouts, and popup anchors without new provider calls.
          </p>
          <div className="mt-3 grid gap-2">
            <button
              onClick={handleCreateFixture}
              disabled={generatingFixture || fixtureAssetExists}
              className="inline-flex items-center justify-center gap-2 rounded-md bg-violet-600 px-3 py-2 text-xs font-medium text-white transition-colors hover:bg-violet-500 disabled:cursor-not-allowed disabled:bg-neutral-800 disabled:text-neutral-500"
            >
              {generatingFixture ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              {fixtureAssetExists ? "Fixture Assets Already Generated" : "Generate Fixture Assets"}
            </button>
            <button
              onClick={loadAssets}
              disabled={loadingAssets}
              className="inline-flex items-center justify-center gap-2 rounded-md border border-neutral-800 px-3 py-2 text-xs font-medium text-neutral-300 transition-colors hover:border-neutral-700 hover:text-neutral-100 disabled:cursor-not-allowed disabled:text-neutral-600"
            >
              {loadingAssets ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              Refresh Assets
            </button>
          </div>
          {fixtureResult ? (
            <div className="mt-3 rounded-md border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-200">
              Fixture saved
              <span className="ml-2 text-emerald-300/80">
                {fixtureResult.used_external_api ? "Provider call used once" : "Reused existing fixture"}
              </span>
            </div>
          ) : null}
        </div>
        <div className="min-h-0 overflow-y-auto p-3">
          {assets.length === 0 && !loadingAssets ? (
            <div className="rounded-md border border-dashed border-neutral-800 bg-neutral-950/50 p-4 text-xs leading-5 text-neutral-500">
              No cached Test Lab cutouts found yet. Run one flip-flop or character-backed Test Lab generation once, then reuse it here.
            </div>
          ) : (
            <div className="space-y-2">
              {assets.map((asset) => (
                <button
                  key={asset.asset_id}
                  onClick={() => {
                    setSelectedAssetId(asset.asset_id);
                    setResult(null);
                  }}
                  className={`w-full rounded-md border p-3 text-left transition-colors ${
                    selectedAssetId === asset.asset_id
                      ? "border-violet-500 bg-violet-500/15"
                      : "border-neutral-800 bg-neutral-950/50 hover:border-neutral-700"
                  }`}
                >
                  <p className="truncate text-sm font-medium text-neutral-100">{asset.filename}</p>
                  <p className="mt-1 truncate text-xs text-neutral-500">{asset.scene_id}</p>
                  <p className="mt-2 truncate font-mono text-[10px] text-neutral-600">{asset.script_id}</p>
                </button>
              ))}
            </div>
          )}
        </div>
      </aside>

      <section className="min-h-0 overflow-y-auto rounded-lg border border-neutral-800 bg-neutral-900/60 p-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase text-neutral-500">Detector rerun</p>
            <h2 className="mt-2 text-sm font-semibold text-neutral-100">Overlay anchor proof</h2>
            <p className="mt-1 text-xs leading-5 text-neutral-500">
              Rerun the detector instantly, or render a real Remotion preview from the saved fixture.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <label className="block">
              <span className="sr-only">Flip-flop action</span>
              <select
                value={action}
                onChange={(event) => setAction(event.target.value as FlipflopDebugAction)}
                className="h-10 rounded-md border border-neutral-800 bg-neutral-950 px-3 text-xs font-medium text-neutral-100 outline-none transition-colors hover:border-neutral-700 focus:border-violet-500"
              >
                {ACTIONS.map((option) => (
                  <option key={option.value} value={option.value}>{option.label}</option>
                ))}
              </select>
            </label>
            <button
              onClick={() => runAnalysis()}
              disabled={!selectedAsset || analyzing}
              className="inline-flex h-10 items-center gap-2 rounded-md bg-violet-600 px-3 text-xs font-medium text-white transition-colors hover:bg-violet-500 disabled:cursor-not-allowed disabled:bg-neutral-800 disabled:text-neutral-500"
            >
              {analyzing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RotateCcw className="h-4 w-4" />}
              Rerun Detector
            </button>
            <button
              onClick={handleRenderFixture}
              disabled={!selectedAsset || renderingFixture}
              className="inline-flex h-10 items-center gap-2 rounded-md border border-violet-500/50 px-3 text-xs font-medium text-violet-100 transition-colors hover:bg-violet-500/15 disabled:cursor-not-allowed disabled:border-neutral-800 disabled:text-neutral-500"
            >
              {renderingFixture ? <Loader2 className="h-4 w-4 animate-spin" /> : <Film className="h-4 w-4" />}
              Rerender Fixture
            </button>
          </div>
        </div>

        {error && (
          <div className="mt-4 rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs leading-5 text-red-200">
            {error}
          </div>
        )}

        <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
          <StatusPill tone="emerald" label="External provider calls" value="None" />
          <StatusPill tone={result?.status === "failed" ? "red" : "neutral"} label="Detector" value={result?.status ?? "Not run"} />
          <StatusPill tone={renderResult ? "emerald" : "neutral"} label="Renderer" value={renderResult ? "Local only" : "Not run"} />
          {result?.registration_algorithm_version ? (
            <StatusPill tone="neutral" label="Version" value={result.registration_algorithm_version} />
          ) : null}
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          {selectedAsset ? (
            <ImagePanel title="Cached base PNG" src={selectedAsset.asset_url} icon={<Eye className="h-4 w-4" />} />
          ) : (
            <EmptyPanel label="Select a cached asset" />
          )}
          {result?.debug_url ? (
            <ImagePanel
              title="Detector overlay debug"
              src={result.debug_url}
              icon={result.status === "passed" ? <CheckCircle2 className="h-4 w-4 text-emerald-300" /> : <AlertTriangle className="h-4 w-4 text-red-300" />}
            />
          ) : (
            <EmptyPanel label="Rerun detector to create a debug overlay" />
          )}
        </div>

        {renderResult?.render_url ? (
          <div className="mt-4 overflow-hidden rounded-md border border-neutral-800 bg-neutral-950">
            <div className="flex items-center gap-2 border-b border-neutral-800 px-3 py-2 text-xs font-medium text-neutral-300">
              <Film className="h-4 w-4 text-violet-300" />
              Remotion preview
            </div>
            <video
              key={renderResult.render_url}
              src={assetUrl(renderResult.render_url)}
              controls
              className="aspect-video w-full bg-black"
            />
          </div>
        ) : null}

        <div className="mt-4 grid gap-4 xl:grid-cols-2">
          <MetadataPanel title="Selected Asset" value={selectedAsset ? selectedAsset.source_metadata : null} />
          <MetadataPanel title="Detected Anchor" value={result?.anchor ?? null} error={result?.error ?? null} />
        </div>
      </section>
    </div>
  );
}

function upsertAsset(assets: FlipflopDebugAsset[], asset: FlipflopDebugAsset): FlipflopDebugAsset[] {
  const withoutAsset = assets.filter((candidate) => candidate.asset_id !== asset.asset_id);
  return [asset, ...withoutAsset];
}

function StatusPill({ tone, label, value }: { tone: "emerald" | "red" | "neutral"; label: string; value: string }) {
  const classes = {
    emerald: "border-emerald-500/30 bg-emerald-500/10 text-emerald-200",
    red: "border-red-500/30 bg-red-500/10 text-red-200",
    neutral: "border-neutral-800 bg-neutral-950/70 text-neutral-300",
  };
  return (
    <span className={`inline-flex items-center gap-1.5 rounded border px-2 py-1 ${classes[tone]}`}>
      <span className="text-neutral-500">{label}:</span>
      <span className="font-medium capitalize">{value}</span>
    </span>
  );
}

function ImagePanel({ title, src, icon }: { title: string; src: string; icon: React.ReactNode }) {
  return (
    <div className="overflow-hidden rounded-md border border-neutral-800 bg-neutral-950">
      <div className="flex items-center gap-2 border-b border-neutral-800 px-3 py-2 text-xs font-medium text-neutral-300">
        {icon}
        {title}
      </div>
      <div
        className="flex aspect-square items-center justify-center"
        style={{
          backgroundColor: "#171717",
          backgroundImage:
            "linear-gradient(45deg, #262626 25%, transparent 25%), linear-gradient(-45deg, #262626 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #262626 75%), linear-gradient(-45deg, transparent 75%, #262626 75%)",
          backgroundPosition: "0 0, 0 8px, 8px -8px, -8px 0",
          backgroundSize: "16px 16px",
        }}
      >
        <img src={assetUrl(src)} alt={title} className="h-full w-full object-contain" />
      </div>
    </div>
  );
}

function EmptyPanel({ label }: { label: string }) {
  return (
    <div className="flex aspect-square items-center justify-center rounded-md border border-dashed border-neutral-800 bg-neutral-950/40 text-xs text-neutral-600">
      {label}
    </div>
  );
}

function MetadataPanel({ title, value, error }: { title: string; value: Record<string, unknown> | null; error?: string | null }) {
  return (
    <div className="rounded-md border border-neutral-800 bg-neutral-950/70">
      <div className="border-b border-neutral-800 px-3 py-2 text-xs font-medium text-neutral-300">{title}</div>
      {error ? (
        <div className="p-3 text-xs leading-5 text-red-200">{error}</div>
      ) : value ? (
        <pre className="max-h-80 overflow-y-auto whitespace-pre-wrap p-3 font-mono text-[11px] leading-5 text-neutral-400">
          {JSON.stringify(value, null, 2)}
        </pre>
      ) : (
        <div className="p-3 text-xs text-neutral-600">No metadata yet.</div>
      )}
    </div>
  );
}
