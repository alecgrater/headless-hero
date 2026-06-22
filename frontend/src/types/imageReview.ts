import type { ScriptContent } from "./script";

export type ImageReviewAssetKind = "scene" | "frame" | "layer";

export interface ImageReviewAsset {
  asset_id: string;
  scene_id: string;
  segment_index: number;
  segment_name: string;
  scene_index: number;
  scene_label: string;
  asset_kind: ImageReviewAssetKind;
  current_url: string;
  original_url: string;
  reviewed: boolean;
  width?: number | null;
  height?: number | null;
  layer_id?: string | null;
  frame_index?: number | null;
}

export interface ImageReviewListResponse {
  script_id: string;
  assets: ImageReviewAsset[];
}

export interface ImageReviewUpdateResponse {
  script_id: string;
  asset: ImageReviewAsset;
  assets: ImageReviewAsset[];
  script: ScriptContent;
}
