export interface VideoIdea {
  title: string;
  segments_est: number;
  description: string;
  keywords: string[];
}

export interface GenerateIdeasRequest {
  niche: string;
  count?: number;
  brand_id?: string;
  exclude_titles?: string[];
}

export interface GenerateIdeasResponse {
  ideas: VideoIdea[];
}
