export interface GenerateVisualResponse {
  image_url: string;
  prompt_used: string;
  image_url_b?: string;
  frame_urls?: string[];
}

export interface GenerateBatchResponse {
  results: { scene_id: string; image_url?: string; image_url_b?: string; frame_urls?: string[]; prompt_used?: string; error?: string }[];
}

export interface GenerateTitleCardsResponse {
  generated_scene_ids: string[];
  image_urls: Record<string, string>;
}
