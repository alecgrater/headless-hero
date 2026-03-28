export interface KenBurnsConfig {
  effect: "none" | "zoom_in" | "zoom_out" | "pan_left" | "pan_right" | "pan_up" | "pan_down";
  intensity: "subtle" | "moderate" | "dramatic";
}

export interface TextOverlayConfig {
  position: "top" | "center" | "bottom" | "lower_third";
  style: "default" | "bold" | "subtitle" | "title_card";
  animation: "none" | "fade_in" | "slide_up" | "typewriter";
  show_at: number;
  duration: number;
}

export interface Scene {
  id: string;
  narration: string;
  visual_prompt: string;
  text_overlay: string;
  duration_estimate_seconds: number;
  is_title_card: boolean;
  is_animated?: boolean;
  visual_prompt_b?: string;
  image_url?: string;
  image_url_b?: string;
  audio_url?: string;
  audio_duration_seconds?: number;
  ken_burns?: KenBurnsConfig;
  text_overlay_config?: TextOverlayConfig;
  media_type?: "ai_generated" | "gameplay_clip" | "hardware_image";
  search_query?: string;
  video_clip_url?: string;
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
  format?: "youtube" | "shortform";
  target_duration_seconds?: number;
}

export interface GenerateScriptRequest {
  topic: string;
  description?: string;
  brand_id: string;
  segment_count?: number;
  animated_scene_count?: number;
}

export interface GenerateShortformScriptRequest {
  topic: string;
  description?: string;
  brand_id: string;
  platforms: string[];
  target_duration_seconds?: number;
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
  content_format?: "youtube" | "shortform";
}

export interface ScriptSummary {
  id: string;
  brand_id: string;
  topic_title: string;
  topic_description: string;
  created_at: string;
  segment_count: number;
  scene_count: number;
  image_count: number;
  audio_count: number;
  has_renders: boolean;
  thumbnail_url: string;
  status: "script" | "images" | "audio" | "exported";
  content_format?: "youtube" | "shortform";
}
