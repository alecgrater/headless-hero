export interface Scene {
  id: string;
  narration: string;
  visual_prompt: string;
  text_overlay: string;
  duration_estimate_seconds: number;
  is_title_card: boolean;
  image_url?: string;
  audio_url?: string;
  audio_duration_seconds?: number;
}

export interface Segment {
  name: string;
  scenes: Scene[];
}

export interface ScriptContent {
  title: string;
  segments: Segment[];
  intro_hook: string;
  outro_cta: string;
}

export interface GenerateScriptRequest {
  topic: string;
  description?: string;
  brand_id: string;
  segment_count?: number;
}

export interface GenerateScriptResponse {
  id: string;
  script: ScriptContent;
}

export interface ScriptRead {
  id: string;
  brand_id: string;
  topic_title: string;
  topic_description: string;
  script: ScriptContent;
  created_at: string;
}
