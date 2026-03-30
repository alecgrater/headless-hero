export interface GenerateVisualRequest {
  script_id: string;
  scene_id: string;
  visual_prompt: string;
  width?: number;
  height?: number;
  is_animated?: boolean;
  visual_prompt_b?: string;
  frame_prompts?: string[];
  frame_seed?: number | null;
}

export interface GenerateVisualResponse {
  image_url: string;
  prompt_used: string;
  image_url_b?: string;
  frame_urls?: string[];
}

export interface BatchScene {
  scene_id: string;
  visual_prompt: string;
  is_animated?: boolean;
  visual_prompt_b?: string;
  frame_prompts?: string[];
  frame_seed?: number | null;
}

export interface GenerateBatchRequest {
  script_id: string;
  scenes: BatchScene[];
  width?: number;
  height?: number;
}

export interface BatchResultItem {
  scene_id: string;
  image_url?: string;
  image_url_b?: string;
  frame_urls?: string[];
  prompt_used?: string;
  error?: string;
}

export interface GenerateBatchResponse {
  results: BatchResultItem[];
}

export interface GenerateTitleCardsResponse {
  generated_scene_ids: string[];
  image_urls: Record<string, string>;
}
