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

interface TikTokSEO {
  caption: string;
  hashtags: string[];
}

interface InstagramSEO {
  caption: string;
  hashtags: string[];
}

export interface SEOMetadata {
  youtube: YouTubeSEO;
  tiktok: TikTokSEO[];
  instagram: InstagramSEO;
}

export interface GenerateSEOResponse {
  metadata: SEOMetadata;
}

// --- Render Estimate ---

export interface RenderEstimateResponse {
  estimated_seconds: number;
}

// --- Short-Form ---

export interface ShortformSEOMetadata {
  youtube_shorts?: { title: string; description: string; tags: string[] };
  tiktok?: { caption: string; hashtags: string[] };
  instagram_reels?: { caption: string; hashtags: string[] };
  thumbnail_text?: string;
  hook_preview_text?: string;
}
