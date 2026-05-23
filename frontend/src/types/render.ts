/** TypeScript interfaces for render, thumbnail, and SEO API responses. */

// --- Render ---

export interface RenderJobResponse {
  job_id: string;
}

export interface RenderStatusResponse {
  job_id: string;
  status: "pending" | "running" | "completed" | "failed";
  progress: number;
  current_step: string;
  output_urls: string[];
  error?: string;
  estimated_seconds?: number;
  elapsed_seconds?: number;
}

export interface ExportProgressStatus {
  label: string;
  progress: number;
}

// --- Thumbnail ---

export type ThumbnailLabelStyle = "time_periods" | "levels";

export interface ThumbnailConcept {
  idx: number;
  title_text: string;
  visual_description: string;
  image_url?: string;
  error?: string;
}

export interface GenerateThumbnailResponse {
  concepts: ThumbnailConcept[];
  label_style?: ThumbnailLabelStyle | null;
}

// --- SEO ---

interface YouTubeSEO {
  title: string;
  description: string;
  tags: string[];
}

export interface SEOMetadata {
  youtube: YouTubeSEO;
}

export interface ShortFormSEO {
  index: number;
  title: string;
  description: string;
  hashtags: string[];
  tags: string[];
}

export interface ShortFormSEOMetadata {
  shorts: ShortFormSEO[];
}

export interface GenerateSEOResponse {
  metadata: SEOMetadata;
}

export interface GenerateShortFormSEOResponse {
  metadata: ShortFormSEOMetadata;
}

// --- Render Estimate ---

export interface RenderEstimateResponse {
  estimated_seconds: number;
}

export interface RenderedLongformResponse {
  rendered: boolean;
  path?: string | null;
  url?: string | null;
}

// --- Export Bundle ---

export interface ExportBundleResponse {
  folder_path: string;
  files: string[];
}

// --- Short-form export ---

export interface ShortFormJobStatus {
  job_id: string;
  status: "pending" | "running" | "completed" | "failed";
  progress: number;
  current_step: string;
  output_urls: string[];
  error: string | null;
  estimated_seconds: number | null;
  elapsed_seconds: number | null;
}
