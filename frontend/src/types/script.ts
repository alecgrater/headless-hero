import { SEOMetadata } from "./render";

// --- FX types ---

export interface ZoomPunchFX {
  trigger_frame: number;
  scale: number; // 1.04-1.07
}

export interface SceneFX {
  zoom_punch?: ZoomPunchFX | null;
}

export interface EliKeyframe {
  start_frame: number;
  end_frame: number;
  frame_id: string;
  transition: "cut" | "crossfade";
}

export interface EliOverlay {
  enabled: boolean;
  keyframes: EliKeyframe[];
}

export interface ChapterMarker {
  segment_index: number;
  label: string;
  frame_offset: number;
}

export interface VideoFX {
  chapter_markers: ChapterMarker[];
}

export interface FrameDirective {
  prompt: string;
  source: "ai_generated" | "real_photo" | "subtitle";
  search_query?: string;
  transition: "cut" | "crossfade" | "fade_black";
  reference_previous: boolean;
  contains_person?: boolean;
}

export interface WordTimestamp {
  word: string;
  start_ms: number;
  end_ms: number;
}

export interface Scene {
  id: string;
  narration: string;
  visual_prompt: string;
  duration_estimate_seconds: number;
  is_title_card: boolean;
  image_url?: string;
  audio_url?: string;
  audio_duration_seconds?: number;
  frame_urls?: string[];
  visual_beat?: "static" | "continuous" | "quick_cuts" | "aha_subtitle" | "montage";
  frame_directives?: FrameDirective[];
  contains_person?: boolean;
  fx?: SceneFX | null;
  eli_overlay?: EliOverlay | null;
  word_timestamps?: WordTimestamp[];
  title_card_zoom_target?: { x: number; y: number; radius: number };
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
  eli_position?: { x: number; y: number } | null;
  segment_timer_enabled?: boolean;
  seo_metadata?: SEOMetadata | null;
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
