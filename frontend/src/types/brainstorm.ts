export interface BrainstormRecommendation {
  prompt: string;
  title: string;
  reasoning: string;
  confidence: number;
  signals: string[];
}

export interface BrainstormResponse {
  recommendations: BrainstormRecommendation[];
  stats: {
    script_count: number;
    topic_count: number;
  };
}
