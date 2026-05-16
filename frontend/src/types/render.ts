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

export interface ExportAudioResponse {
  audio_url: string;
}

// --- Thumbnail ---

export interface ThumbnailConcept {
  idx: number;
  title_text: string;
  visual_description: string;
  image_url?: string;
  error?: string;
}

export interface GenerateThumbnailResponse {
  concepts: ThumbnailConcept[];
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

export interface GenerateSEOResponse {
  metadata: SEOMetadata;
}

// --- Render Estimate ---

export interface RenderEstimateResponse {
  estimated_seconds: number;
}

// --- Export Bundle ---

export interface ExportBundleResponse {
  folder_path: string;
  files: string[];
}

// --- Short-form export ---

export interface ShortIntro {
  segment_idx: number;
  display_text: string;
  audio_url: string;
  duration_seconds: number;
  word_timestamps: { word: string; start_ms: number; end_ms: number }[];
}

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
