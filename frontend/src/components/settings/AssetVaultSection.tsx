import { Archive, Boxes, Loader2, RefreshCw, UserRound } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { assetUrl, getAssetVaultImages, type AssetVaultImage, type AssetVaultKind } from "../../api";

type FilterKind = "all" | AssetVaultKind;

const FILTERS: Array<{ id: FilterKind; label: string }> = [
  { id: "all", label: "All" },
  { id: "character", label: "Characters" },
  { id: "item", label: "Items" },
];

export default function AssetVaultSection() {
  const [assets, setAssets] = useState<AssetVaultImage[]>([]);
  const [filter, setFilter] = useState<FilterKind>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const visibleAssets = useMemo(
    () => assets.filter((asset) => filter === "all" || asset.kind === filter),
    [assets, filter],
  );

  useEffect(() => {
    void loadAssets();
  }, []);

  async function loadAssets() {
    setLoading(true);
    setError("");
    try {
      setAssets(await getAssetVaultImages());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load the asset vault.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="max-w-6xl px-8 py-8">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase text-neutral-500">Reusable cutouts</p>
          <h3 className="mt-2 text-lg font-semibold text-neutral-100">Asset Vault</h3>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-neutral-400">
            Cleaned popup crop cutouts are saved here automatically with descriptive filenames for later reuse.
          </p>
        </div>
        <button
          onClick={loadAssets}
          disabled={loading}
          className="inline-flex h-9 items-center gap-2 rounded-md border border-neutral-800 bg-neutral-900 px-3 text-sm font-medium text-neutral-300 transition-colors hover:border-neutral-700 hover:text-neutral-100 disabled:cursor-not-allowed disabled:text-neutral-600"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          Refresh
        </button>
      </div>

      <div className="mt-6 inline-flex rounded-md border border-neutral-800 bg-neutral-950 p-1">
        {FILTERS.map((option) => (
          <button
            key={option.id}
            onClick={() => setFilter(option.id)}
            className={`rounded px-3 py-1.5 text-xs font-medium transition-colors ${
              filter === option.id
                ? "bg-neutral-800 text-neutral-100"
                : "text-neutral-500 hover:text-neutral-200"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="mt-4 rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-200">
          {error}
        </div>
      )}

      {loading ? (
        <div className="mt-8 flex min-h-64 items-center justify-center rounded-md border border-neutral-800 bg-neutral-900/50 text-neutral-500">
          <Loader2 className="h-5 w-5 animate-spin" />
        </div>
      ) : visibleAssets.length > 0 ? (
        <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {visibleAssets.map((vaultAsset) => (
            <VaultCard key={vaultAsset.url} vaultAsset={vaultAsset} />
          ))}
        </div>
      ) : (
        <div className="mt-8 flex min-h-64 items-center justify-center rounded-md border border-dashed border-neutral-800 bg-neutral-900/40">
          <div className="max-w-sm text-center">
            <Archive className="mx-auto h-8 w-8 text-neutral-600" />
            <p className="mt-3 text-sm font-medium text-neutral-300">No saved cutouts yet</p>
            <p className="mt-1 text-xs leading-5 text-neutral-500">
              Run chroma in the Popup Crop Lab to populate the vault with reusable character and item PNGs.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

function VaultCard({ vaultAsset }: { vaultAsset: AssetVaultImage }) {
  const KindIcon = vaultAsset.kind === "character" ? UserRound : Boxes;
  const created = new Date(vaultAsset.created_at);
  const createdLabel = Number.isNaN(created.getTime())
    ? "Unknown date"
    : created.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });

  return (
    <div className="overflow-hidden rounded-md border border-neutral-800 bg-neutral-900/70">
      <div
        className="flex aspect-video items-center justify-center border-b border-neutral-800 bg-neutral-950"
        style={{
          backgroundImage:
            "linear-gradient(45deg, #262626 25%, transparent 25%), linear-gradient(-45deg, #262626 25%, transparent 25%), linear-gradient(45deg, transparent 75%, #262626 75%), linear-gradient(-45deg, transparent 75%, #262626 75%)",
          backgroundPosition: "0 0, 0 8px, 8px -8px, -8px 0",
          backgroundSize: "16px 16px",
        }}
      >
        <img src={assetUrl(vaultAsset.url)} alt={vaultAsset.name} className="h-full w-full object-contain p-3" />
      </div>
      <div className="p-3">
        <div className="flex items-center justify-between gap-2">
          <p className="min-w-0 truncate text-sm font-medium capitalize text-neutral-100">{vaultAsset.name}</p>
          <span className="inline-flex shrink-0 items-center gap-1 rounded border border-neutral-800 px-1.5 py-0.5 text-[10px] uppercase text-neutral-500">
            <KindIcon className="h-3 w-3" />
            {vaultAsset.kind}
          </span>
        </div>
        <p className="mt-2 truncate font-mono text-[10px] text-neutral-600">{vaultAsset.filename}</p>
        <p className="mt-1 text-xs text-neutral-500">{createdLabel}</p>
      </div>
    </div>
  );
}
