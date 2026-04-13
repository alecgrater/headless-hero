export interface VideoIdea {
  title: string;
  segments_est: number;
  description: string;
  keywords: string[];
}

export interface GenerateIdeasResponse {
  ideas: VideoIdea[];
}
