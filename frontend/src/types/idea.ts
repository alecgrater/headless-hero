export interface VideoIdea {
  title: string;
  segments_est: number;
  description: string;
  keywords: string[];
  cold_open_text?: string;
  format_id?: string;
  closing_image?: string;
}

export interface GenerateIdeasResponse {
  ideas: VideoIdea[];
}

export type IdeaStatus = "idea" | "in_progress" | "scripted" | "published";
export type IdeaSource = "manual" | "for_you" | "trending";
export type ColdOpenStatus = "pending" | "generating" | "ready" | "refining" | "scored" | "failed";

export interface Idea {
  id: string;
  text: string;
  description: string;
  category: string;
  rank: number;
  status: IdeaStatus;
  source: IdeaSource;
  cold_open_status: ColdOpenStatus;
  cold_open_variants_json: string;
  selected_hook_json: string;
  hook_score: number | null;
  hook_score_json: string;
  created_at: string;
}
