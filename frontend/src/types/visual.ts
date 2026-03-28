export interface GenerateVisualRequest {
  script_id: string;
  scene_id: string;
  visual_prompt: string;
  brand_style?: string;
  width?: number;
  height?: number;
  is_animated?: boolean;
  visual_prompt_b?: string;
}

export interface GenerateVisualResponse {
  image_url: string;
  prompt_used: string;
  image_url_b?: string;
}

export interface BatchScene {
  scene_id: string;
  visual_prompt: string;
  is_animated?: boolean;
  visual_prompt_b?: string;
}

export interface GenerateBatchRequest {
  script_id: string;
  scenes: BatchScene[];
  brand_style?: string;
  width?: number;
  height?: number;
}

export interface BatchResultItem {
  scene_id: string;
  image_url?: string;
  image_url_b?: string;
  prompt_used?: string;
  error?: string;
}

export interface GenerateBatchResponse {
  results: BatchResultItem[];
}
