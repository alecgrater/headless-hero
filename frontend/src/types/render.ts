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
