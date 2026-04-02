// --- New FX types (4 core effects) ---

export interface EmphasisWord {
  word: string;
  start_frame: number;
  end_frame: number;
  style: "scale_pop" | "color_flash" | "size_burst" | "shake" | "underline_draw";
}

export interface KineticCaptionsFX {
  words: EmphasisWord[];
}

export interface ZoomPunchFX {
  trigger_frame: number;
  scale: number; // 1.04-1.07
}

export interface SceneFX {
  kinetic_captions?: KineticCaptionsFX | null;
  zoom_punch?: ZoomPunchFX | null;
}

export interface ChapterMarker {
  segment_index: number;
  label: string;
  frame_offset: number;
}

export interface VideoFX {
  chapter_markers: ChapterMarker[];
}

// --- Legacy types (kept for backward compat) ---

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
  frame_prompts?: string[];
  frame_urls?: string[];
  frame_count?: number;
  frame_seed?: number | null;
  scene_transition?: "" | "crossfade" | "slide_left" | "slide_right" | "push_up";
  fx?: SceneFX | null;
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
  video_fx?: VideoFX | null;
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
}
