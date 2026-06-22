import { useEffect, useMemo, useState } from "react";
import { Grid3X3, Images, Pencil, RefreshCw, SlidersHorizontal } from "lucide-react";

import {
  assetUrl,
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

type ReviewViewMode = "editor" | "gallery";

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

function viewButtonClass(active: boolean) {
  return `inline-flex h-9 items-center gap-2 rounded-md px-3 text-xs font-semibold transition-colors ${
    active
      ? "bg-violet-600 text-white shadow-lg shadow-violet-950/30"
      : "text-neutral-400 hover:bg-neutral-800 hover:text-neutral-100"
  }`;
}

export default function ImageReviewTab({ scriptId, content, onContentUpdated }: Props) {
  const [assets, setAssets] = useState<ImageReviewAsset[]>([]);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ReviewViewMode>("editor");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState(false);
  const [resetRevision, setResetRevision] = useState(0);
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
      setResetRevision((revision) => revision + 1);
      onContentUpdated(response.script);
      showToast("Restored original image.", "success");
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Failed to reset image");
    } finally {
      setResetting(false);
    }
  };

  const openAssetInEditor = (asset: ImageReviewAsset) => {
    setSelectedAssetId(asset.asset_id);
    setViewMode("editor");
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
        <div className="mb-3 flex shrink-0 flex-wrap items-center justify-between gap-3">
          <div className="inline-flex rounded-lg border border-neutral-800 bg-neutral-900/75 p-1">
            <button
              type="button"
              aria-label="Editor view"
              aria-pressed={viewMode === "editor"}
              onClick={() => setViewMode("editor")}
              className={viewButtonClass(viewMode === "editor")}
            >
              <SlidersHorizontal className="h-4 w-4" />
              Editor
            </button>
            <button
              type="button"
              aria-label="Gallery view"
              aria-pressed={viewMode === "gallery"}
              onClick={() => setViewMode("gallery")}
              className={viewButtonClass(viewMode === "gallery")}
            >
              <Grid3X3 className="h-4 w-4" />
              Gallery
            </button>
          </div>
          <div className="text-xs text-neutral-500">
            {selectedAsset ? `${selectedAsset.scene_id} · ${assetKindLabel(selectedAsset)}` : "No image selected"}
          </div>
        </div>

        {viewMode === "gallery" ? (
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-neutral-800 bg-neutral-950/40">
            <div className="flex shrink-0 items-center justify-between gap-4 border-b border-neutral-800 bg-neutral-900/70 px-4 py-3">
              <div className="min-w-0">
                <h3 className="text-sm font-semibold text-neutral-100">Browse generated images</h3>
                <p className="mt-0.5 text-xs text-neutral-500">
                  Select a tile to compare shots, then open the one that needs cleanup.
                </p>
              </div>
              <button
                type="button"
                onClick={() => selectedAsset && openAssetInEditor(selectedAsset)}
                disabled={!selectedAsset}
                className="inline-flex items-center gap-2 rounded-md border border-violet-500/50 bg-violet-500/15 px-3 py-2 text-xs font-semibold text-violet-100 transition-colors hover:bg-violet-500/25 disabled:opacity-50"
              >
                <Pencil className="h-3.5 w-3.5" />
                Edit selected
              </button>
            </div>
            <div className="min-h-0 flex-1 overflow-auto bg-[radial-gradient(circle_at_center,rgba(64,64,64,0.28)_1px,transparent_1px)] [background-size:18px_18px] p-4">
              <div className="grid grid-cols-[repeat(auto-fill,minmax(220px,1fr))] gap-3">
                {assets.map((asset) => {
                  const selected = selectedAsset?.asset_id === asset.asset_id;
                  const kindLabel = assetKindLabel(asset);
                  return (
                    <article
                      key={asset.asset_id}
                      className={`group overflow-hidden rounded-lg border bg-neutral-900/75 transition-colors ${
                        selected
                          ? "border-violet-400/80 ring-1 ring-violet-400/50"
                          : "border-neutral-800 hover:border-neutral-600"
                      }`}
                    >
                      <button
                        type="button"
                        onClick={() => setSelectedAssetId(asset.asset_id)}
                        onDoubleClick={() => openAssetInEditor(asset)}
                        className="block w-full text-left"
                      >
                        <div className="relative aspect-video overflow-hidden bg-neutral-900">
                          <img
                            src={assetUrl(asset.current_url)}
                            alt={`${asset.scene_id} ${kindLabel} preview`}
                            className="h-full w-full object-cover transition-transform duration-200 group-hover:scale-[1.02]"
                            loading="lazy"
                          />
                          <div className="absolute left-2 top-2 rounded-md bg-black/65 px-2 py-1 font-mono text-[10px] font-semibold text-neutral-100">
                            {asset.scene_id}
                          </div>
                          <div className={`absolute right-2 top-2 rounded-md border px-2 py-1 text-[10px] font-semibold ${assetStatusClass(asset.reviewed)}`}>
                            {asset.reviewed ? "Reviewed" : "Original"}
                          </div>
                        </div>
                        <div className="space-y-1 p-3">
                          <div className="flex items-center justify-between gap-2">
                            <p className="truncate text-xs font-semibold text-neutral-100">{kindLabel}</p>
                            {selected ? (
                              <span className="shrink-0 text-[10px] font-semibold uppercase tracking-wide text-violet-300">
                                Selected
                              </span>
                            ) : null}
                          </div>
                          <p className="truncate text-xs text-neutral-500">{asset.segment_name}</p>
                          <p className="line-clamp-2 min-h-8 text-xs leading-4 text-neutral-400">{asset.scene_label}</p>
                        </div>
                      </button>
                      <div className="border-t border-neutral-800 p-2">
                        <button
                          type="button"
                          onClick={() => openAssetInEditor(asset)}
                          className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-neutral-800 px-3 py-2 text-xs font-semibold text-neutral-100 transition-colors hover:bg-violet-600"
                          aria-label={`Open ${asset.scene_id} ${kindLabel} in editor`}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                          Open in editor
                        </button>
                      </div>
                    </article>
                  );
                })}
              </div>
            </div>
          </div>
        ) : selectedAsset ? (
          <ImageReviewEditor
            key={`${selectedAsset.asset_id}:${selectedAsset.current_url}:${resetRevision}`}
            scriptId={scriptId}
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
