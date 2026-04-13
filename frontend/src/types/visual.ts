export interface GenerateVisualResponse {
  image_url: string;
  prompt_used: string;
  image_url_b?: string;
  frame_urls?: string[];
}

export interface GenerateTitleCardsResponse {
  job_id: string;
}
