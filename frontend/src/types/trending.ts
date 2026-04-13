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
