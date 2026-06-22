import type { VisualLayer } from "./script";

export interface GenerateVisualResponse {
  image_url: string;
  prompt_used: string;
  image_url_b?: string;
  frame_urls?: string[];
  video_url?: string;
  visual_layers?: VisualLayer[];
  visual_source_metadata?: {
    source_type?: string;
    provider?: string;
    query?: string;
    reason?: string;
    license_note?: string;
    opt_in_setting?: string;
    fallback?: boolean;
  } | null;
}

export interface GenerateTitleCardsResponse {
  job_id: string;
}

export interface GenerateVisualBatchJobResponse {
  job_id: string;
}
