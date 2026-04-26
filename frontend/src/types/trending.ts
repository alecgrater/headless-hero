export interface TrendingTopic {
  id: string;
  title: string;
  source: string;
  score: number;
  score_breakdown: {
    search_velocity: number;
    competitor_view_rate: number;
    reddit_engagement: number;
    format_fit: number;
  };
  format_fit_rationale: string;
  fetched_at: string;
  status: "new" | "dismissed" | "used";
  is_breakout: boolean;
  is_first_mover: boolean;
  evidence_snippet: string;
}

export interface TrendingRefreshStatus {
  status: "pending" | "running" | "completed" | "failed";
  progress: number;
  sources: Record<string, string>;
  result_count: number;
  error: string | null;
}

export interface ContentProfile {
  script_count: number;
  common_topics: string[];
  narration_style: string;
  visual_approach: string;
  typical_keywords: string[];
  audience_profile: string;
  avg_segment_count: number;
  analyzed_at: string;
  is_stale: boolean;
}

export interface SmartIdea {
  category: string;
  title: string;
  description: string;
  segments_est: number;
  keywords: string[];
  trending_source: string;
  style_match_score: number | null;
  reasoning: string;
  angle: string;
  signals: string[];
}

export interface SmartIdeasResponse {
  ideas: SmartIdea[];
  categories: string[];
  profile_used: boolean;
  trending_topics_used: number;
  refresh_triggered: boolean;
  refresh_job_id: string | null;
  trending_age_hours: number | null;
}
