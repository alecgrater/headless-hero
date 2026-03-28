/** TypeScript interfaces for render, thumbnail, and SEO API responses. */

// --- Render ---

export interface PreviewSceneRequest {
  script_id: string;
  scene_id: string;
  width?: number;
  height?: number;
}

export interface PreviewSceneResponse {
  video_url: string;
}

export interface RenderFullRequest {
  script_id: string;
  width?: number;
  height?: number;
  fade_out?: number;
  speed?: number;
}

export interface RenderSegmentsRequest {
  script_id: string;
  width?: number;
  height?: number;
}

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

export interface ExportAudioRequest {
  script_id: string;
}

export interface ExportAudioResponse {
  audio_url: string;
}

// --- Thumbnail ---

export interface GenerateThumbnailRequest {
  script_id: string;
  brand_style?: string;
  bar_color?: string;
  count?: number;
}

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

export interface GenerateSEORequest {
  script_id: string;
}

export interface YouTubeSEO {
  title: string;
  description: string;
  tags: string[];
}

export interface TikTokSEO {
  caption: string;
  hashtags: string[];
}

export interface InstagramSEO {
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

// --- Auto-Edit ---

export interface AutoEditRequest {
  script_id: string;
  width?: number;
  height?: number;
  title?: string;
}

// --- Short-Form ---

export interface RenderShortformRequest {
  script_id: string;
  title?: string;
  speed?: number;
}

export interface ShortformSEOMetadata {
  youtube_shorts?: { title: string; description: string; tags: string[] };
  tiktok?: { caption: string; hashtags: string[] };
  instagram_reels?: { caption: string; hashtags: string[] };
  thumbnail_text?: string;
  hook_preview_text?: string;
}
