import { useEffect, useMemo, useState } from "react";
import { Images, RefreshCw } from "lucide-react";

import {
  getImageReviewAssets,
  resetImageReviewAsset,
  saveImageReviewEdit,
} from "../../../api";
import type { ImageReviewAsset } from "../../../types/imageReview";
import type { ScriptContent } from "../../../types/script";
import { showToast } from "../../ToastContainer";
import ImageReviewEditor from "./ImageReviewEditor";

interface Props {
  scriptId: string;
  content: ScriptContent;
  onContentUpdated: (content: ScriptContent) => void;
}

function assetKindLabel(asset: ImageReviewAsset): string {
  if (asset.asset_kind === "frame" && asset.frame_index != null) return `Frame ${asset.frame_index + 1}`;
  if (asset.asset_kind === "layer") return asset.layer_id ? `Layer ${asset.layer_id}` : "Layer";
  return "Scene image";
}

function assetStatusClass(reviewed: boolean): string {
  return reviewed
    ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
    : "border-amber-500/30 bg-amber-500/10 text-amber-200";
}

export default function ImageReviewTab({ scriptId, content, onContentUpdated }: Props) {
  const [assets, setAssets] = useState<ImageReviewAsset[]>([]);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedAsset = useMemo(
    () => assets.find((asset) => asset.asset_id === selectedAssetId) ?? assets[0] ?? null,
    [assets, selectedAssetId],
  );

  const reviewedCount = assets.filter((asset) => asset.reviewed).length;

  const loadAssets = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await getImageReviewAssets(scriptId);
      setAssets(response.assets);
      setSelectedAssetId((current) =>
        current && response.assets.some((asset) => asset.asset_id === current)
          ? current
          : response.assets[0]?.asset_id ?? null,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load image review assets");
      setAssets([]);
      setSelectedAssetId(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadAssets();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scriptId, content]);

  const handleSave = async (dataUrl: string) => {
    if (!selectedAsset) return;
    setSaving(true);
    try {
      const response = await saveImageReviewEdit(scriptId, selectedAsset.asset_id, dataUrl);
      setAssets(response.assets);
      setSelectedAssetId(response.asset.asset_id);
      onContentUpdated(response.script);
      showToast("Saved edited image copy.", "success");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Failed to save image edit");
    } finally {
      setSaving(false);
    }
  };

  const handleReset = async () => {
    if (!selectedAsset) return;
    setResetting(true);
    try {
      const response = await resetImageReviewAsset(scriptId, selectedAsset.asset_id);
      setAssets(response.assets);
      setSelectedAssetId(response.asset.asset_id);
      onContentUpdated(response.script);
      showToast("Restored original image.", "success");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Failed to reset image");
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="flex min-h-0 flex-1 overflow-hidden">
      <aside className="flex w-[320px] shrink-0 flex-col border-r border-neutral-800/60 bg-neutral-950/50">
        <div className="border-b border-neutral-800 px-4 py-3">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <Images className="h-4 w-4 text-violet-300" />
                <h2 className="text-sm font-semibold text-neutral-100">Img Review</h2>
              </div>
              <p className="mt-1 text-xs text-neutral-500">
                {reviewedCount}/{assets.length} render-source images reviewed
              </p>
            </div>
            <button
              type="button"
              onClick={() => void loadAssets()}
              disabled={loading}
              className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-neutral-700 bg-neutral-800 text-neutral-300 transition-colors hover:bg-neutral-700 disabled:cursor-wait disabled:opacity-60"
              aria-label="Refresh image review assets"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
            </button>
          </div>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto p-3">
          {loading && assets.length === 0 ? (
            <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4 text-sm text-neutral-400">
              Loading generated images...
            </div>
          ) : error ? (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-4 text-sm text-red-200">
              {error}
            </div>
          ) : assets.length === 0 ? (
            <div className="rounded-lg border border-neutral-800 bg-neutral-900/50 p-4 text-sm text-neutral-400">
              No generated render-source images are available yet.
            </div>
          ) : (
            <div className="space-y-2">
              {assets.map((asset) => {
                const selected = selectedAsset?.asset_id === asset.asset_id;
                return (
                  <button
                    key={asset.asset_id}
                    type="button"
                    onClick={() => setSelectedAssetId(asset.asset_id)}
                    className={`w-full rounded-lg border p-3 text-left transition-colors ${
                      selected
                        ? "border-violet-500/60 bg-violet-500/10"
                        : "border-neutral-800 bg-neutral-900/45 hover:border-neutral-700 hover:bg-neutral-800/60"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="font-mono text-xs font-semibold text-neutral-100">{asset.scene_id}</p>
                        <p className="mt-1 truncate text-xs text-neutral-500">{asset.segment_name}</p>
                      </div>
                      <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[10px] font-semibold ${assetStatusClass(asset.reviewed)}`}>
                        {asset.reviewed ? "Reviewed" : "Original"}
                      </span>
                    </div>
                    <p className="mt-2 line-clamp-2 text-xs text-neutral-400">{asset.scene_label}</p>
                    <p className="mt-2 text-[11px] font-medium uppercase tracking-wide text-violet-300">
                      {assetKindLabel(asset)}
                    </p>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col overflow-hidden p-4">
        {selectedAsset ? (
          <ImageReviewEditor
            key={selectedAsset.asset_id + selectedAsset.current_url}
            asset={selectedAsset}
            saving={saving}
            resetting={resetting}
            onSave={handleSave}
            onReset={handleReset}
          />
        ) : (
          <div className="flex flex-1 items-center justify-center rounded-lg border border-neutral-800 bg-neutral-900/40 p-8 text-center text-sm text-neutral-500">
            Select a generated image to review.
          </div>
        )}
      </main>
    </div>
  );
}
