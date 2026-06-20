import { AlertTriangle, CheckCircle2, Eye, Film, Loader2, RefreshCw, RotateCcw, Sparkles } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  analyzeBlinkDebugAsset,
  assetUrl,
  bumpAssetVersion,
  createBlinkFixtureAsset,
  getBlinkDebugAssets,
  renderBlinkFixturePreview,
} from "../../api";
import type {
  BlinkDebugAsset,
  BlinkDebugResult,
  BlinkFixtureRenderResult,
  BlinkFixtureResult,
} from "../../types/testLab";

const FIXTURE_SCRIPT_ID = "test-lab-blink-fixtures";
const BLINK_ACTION = "blink" as const;

export default function BlinkDebugLab() {
  const [assets, setAssets] = useState<BlinkDebugAsset[]>([]);
  const [selectedAssetId, setSelectedAssetId] = useState("");
  const [result, setResult] = useState<BlinkDebugResult | null>(null);
  const [fixtureResult, setFixtureResult] = useState<BlinkFixtureResult | null>(null);
  const [renderResult, setRenderResult] = useState<BlinkFixtureRenderResult | null>(null);
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
      const nextAssets = await getBlinkDebugAssets();
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
      const next = await analyzeBlinkDebugAsset(assetId, BLINK_ACTION);
      if (!next) {
        setError("The selected blink asset could not be analyzed.");
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
      const next = await createBlinkFixtureAsset();
      if (!next) {
        setError("The blink fixture assets could not be generated.");
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
      const next = await renderBlinkFixturePreview(selectedAssetId, BLINK_ACTION);
      if (!next) {
        setError("The saved blink fixture could not be rendered.");
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
          <p className="text-xs font-semibold uppercase text-neutral-500">Blink</p>
          <h2 className="mt-2 text-sm font-semibold text-neutral-100">Cached saved cutouts</h2>
          <p className="mt-1 text-xs leading-5 text-neutral-500">
            Reuse generated blink bases, character cutouts, and popup anchors without new provider calls.
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
              No cached Test Lab cutouts found yet. Run one blink or character-backed Test Lab generation once, then reuse it here.
            </div>
          ) : (
            <div className="space-y-2">
              {assets.map((asset) => (
                <AssetButton
                  key={asset.asset_id}
                  asset={asset}
                  active={selectedAssetId === asset.asset_id}
                  onClick={() => {
                    setSelectedAssetId(asset.asset_id);
                    setResult(null);
                  }}
                />
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
            <span className="inline-flex h-10 items-center rounded-md border border-neutral-800 bg-neutral-950 px-3 text-xs font-medium text-neutral-100">
              <span className="mr-1.5 text-neutral-500">Blink action:</span>
              Blink
            </span>
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
            <ImagePanel
              title="Cached base PNG"
              src={timestampedAssetPath(selectedAsset.asset_url, selectedAsset.created_at)}
              icon={<Eye className="h-4 w-4" />}
            />
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

function AssetButton({
  asset,
  active,
  onClick,
}: {
  asset: BlinkDebugAsset;
  active: boolean;
  onClick: () => void;
}) {
  const displayName = assetDisplayName(asset);
  return (
    <button
      onClick={onClick}
      className={`flex w-full gap-3 rounded-md border p-2 text-left transition-colors ${
        active
          ? "border-violet-500 bg-violet-500/15"
          : "border-neutral-800 bg-neutral-950/50 hover:border-neutral-700"
      }`}
    >
      <span className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded border border-neutral-800 bg-neutral-950">
        <img
          src={assetUrl(timestampedAssetPath(asset.asset_url, asset.created_at))}
          alt={displayName}
          className="h-full w-full object-contain"
          loading="lazy"
        />
      </span>
      <span className="min-w-0 flex-1 py-1">
        <span className="block truncate text-sm font-medium text-neutral-100">{displayName}</span>
        <span className="mt-1 block truncate text-xs text-neutral-500">{asset.filename}</span>
        <span className="mt-2 block truncate font-mono text-[10px] text-neutral-600">{asset.script_id}</span>
      </span>
    </button>
  );
}

function assetDisplayName(asset: BlinkDebugAsset): string {
  const sourceType = assetSourceType(asset);
  if (sourceType === "blink_base_cutout") {
    return `Blink base: ${asset.scene_id || shortAssetId(asset.script_id)}`;
  }
  if (sourceType === "popup_anchor_cutout") {
    return `Popup anchor: ${asset.scene_id || shortAssetId(asset.script_id)}`;
  }
  if (sourceType === "character_cutout") {
    return `Character cutout: ${shortAssetId(asset.script_id)}`;
  }
  if (asset.scene_id && asset.scene_id !== "character") {
    return `${asset.scene_id}: ${asset.filename}`;
  }
  return asset.filename;
}

function assetSourceType(asset: BlinkDebugAsset): string | undefined {
  if (typeof asset.source_metadata?.source_type === "string") {
    return asset.source_metadata.source_type;
  }
  const parts = asset.asset_id.split("/");
  if (parts.includes("blink_cutouts")) {
    return "blink_base_cutout";
  }
  if (parts.includes("popup_crops")) {
    return "popup_anchor_cutout";
  }
  if (parts.includes("character") && asset.filename === "cutout.png") {
    return "character_cutout";
  }
  return undefined;
}

function shortAssetId(scriptId: string): string {
  const normalized = scriptId.replace(/^test-lab-/, "");
  return normalized.length > 8 ? normalized.slice(0, 8) : normalized || "saved";
}

function timestampedAssetPath(path: string, createdAt: string): string {
  const timestamp = Date.parse(createdAt);
  if (!Number.isFinite(timestamp)) return path;
  const separator = path.includes("?") ? "&" : "?";
  return `${path}${separator}t=${timestamp}`;
}

function upsertAsset(assets: BlinkDebugAsset[], asset: BlinkDebugAsset): BlinkDebugAsset[] {
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
        className="flex h-[min(58vh,620px)] min-h-80 items-center justify-center p-4"
        style={{
          backgroundColor: "#171717",
          backgroundImage:
            "linear-gradient(45deg, #262626 25%, transparent 25%), linear-gradient(-45deg, #262626 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #262626 75%), linear-gradient(-45deg, transparent 75%, #262626 75%)",
          backgroundPosition: "0 0, 0 8px, 8px -8px, -8px 0",
          backgroundSize: "16px 16px",
        }}
      >
        <img src={assetUrl(src)} alt={title} className="max-h-full max-w-full object-contain" />
      </div>
    </div>
  );
}

function EmptyPanel({ label }: { label: string }) {
  return (
    <div className="flex h-[min(58vh,620px)] min-h-80 items-center justify-center rounded-md border border-dashed border-neutral-800 bg-neutral-950/40 p-4 text-xs text-neutral-600">
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
