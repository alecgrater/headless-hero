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

export interface WhitespaceVideo {
  video_id: string;
  title: string;
  url: string;
  views: number;
  likes?: number | null;
  published_at?: string | null;
}

export interface WhitespaceResult {
  rank: number;
  score: number;
  query: string;
  channel_id: string;
  channel_name: string;
  channel_url: string;
  subscriber_count: number | null;
  total_videos: number;
  channel_total_views: number | null;
  video_views_total: number;
  max_views: number;
  avg_views: number;
  reason: string;
  videos: WhitespaceVideo[];
}

export interface WhitespaceFeed {
  version: number;
  generated_at: string;
  seed_generated_at?: string | null;
  source_queries: string[];
  results: WhitespaceResult[];
}
