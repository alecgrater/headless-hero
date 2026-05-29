import type { SEOMetadata, ShortFormSEOMetadata } from "./render";

// --- FX types ---

export interface ZoomPunchFX {
  trigger_word?: string;
  trigger_frame: number;
  scale: number; // 1.04-1.07
}

export interface DriftFX {
  motion: "zoom_in" | "zoom_out" | "pan_left" | "pan_right" | "drift_diagonal";
  intensity: number; // 0.05-0.08
  anchor: string; // 9-point grid
}

export interface SceneFX {
  zoom_punch?: ZoomPunchFX | null;
  drift?: DriftFX | null;
}

export interface EliOverlay {
  enabled: boolean;
  corner?: "TL" | "TR" | "BL" | "BR" | null;
  frame_id: string;
}

export interface ChapterMarker {
  segment_index: number;
  label: string;
  frame_offset: number;
}

export interface VideoFX {
  chapter_markers: ChapterMarker[];
}

export type VisualMode = "video" | "full_frame" | "multi_frame" | "continuous" | "popup_sequence" | "flipflop" | "comparison_board" | "captions";
export type SubtitleStyle = "auto" | "clean" | "kinetic" | "burst" | "none";

export interface VisualCanvas {
  background_color: string;
}

export interface VisualLayer {
  id: string;
  type: "image";
  asset_kind: "full_frame" | "panel" | "cutout";
  image_url?: string;
  prompt?: string;
  placement?: string;
  enter_at_seconds?: number;
  exit_at_seconds?: number | null;
  animation?: "none" | "pop_in";
}

export interface FrameDirective {
  prompt: string;
  source: "ai_generated" | "subtitle";
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
  tts_narration?: string;
  visual_prompt: string;
  duration_estimate_seconds: number;
  is_title_card: boolean;
  image_url?: string;
  audio_url?: string;
  audio_duration_seconds?: number;
  frame_urls?: string[];
  visual_beat?: "static" | "continuous" | "multi_frame" | "quick_cuts" | "aha_subtitle" | "montage" | "captions" | "comparison_board";
  frame_directives?: FrameDirective[];
  contains_person?: boolean;
  visual_mode?: VisualMode;
  visual_layers?: VisualLayer[];
  caption_text?: string;
  caption_emphasis?: string;
  subtitle_style?: SubtitleStyle;
  fx?: SceneFX | null;
  eli_overlay?: EliOverlay | null;
  word_timestamps?: WordTimestamp[];
  title_card_zoom_target?: { x: number; y: number; radius: number };
  frame_timings?: number[] | null;
  visual_in_seconds?: number;
  visual_out_seconds?: number;
  video_url?: string;
  original_visual_prompt?: string;
  visual_source_metadata?: {
    source_type?: string;
    provider?: string;
    query?: string;
    reason?: string;
    license_note?: string;
    opt_in_setting?: string;
    fallback?: boolean;
  } | null;
}

export interface Segment {
  name: string;
  scenes: Scene[];
}

export interface LevelMeta {
  number: number;
  descriptor: string;
  image_prompt: string;
}

export interface ScriptContent {
  title: string;
  segments: Segment[];
  intro_hook: string;
  outro_cta: string;
  video_fx?: VideoFX | null;
  visual_canvas?: VisualCanvas;
  segment_timer_enabled?: boolean;
  subtitle_highlight_enabled?: boolean;
  seo_metadata?: SEOMetadata | null;
  short_form_seo_metadata?: ShortFormSEOMetadata | null;
  hook_score?: HookScore | null;
  script_rating?: ScriptRating | null;
  // AI video media routing
  ai_video_enabled?: boolean;
  // Short-form export
  hook_scene_count?: number | null;  // Leading scenes in segment 0 that are hook teasers; skipped from short #1
  // Script format
  format_id?: string;
  cinematic_thumbnail_prompt?: string | null;
  levels?: LevelMeta[] | null;
}

export interface ScriptRead {
  id: string;
  brand_id: string;
  topic_title: string;
  topic_description: string;
  script: ScriptContent;
  created_at: string;
}

export interface UploadTracking {
  longform_youtube: boolean;
  shortform_youtube: boolean;
  shortform_instagram: boolean;
  shortform_tiktok: boolean;
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
  format_id: string;
  status: "script" | "images" | "audio" | "exported";
  hook_score_overall?: number | null;
  script_rating_overall?: number | null;
  upload_tracking: UploadTracking;
}

// --- Script rating types ---

export interface ScriptRatingCriterion {
  score: number;
  note?: string;
}

export interface ScriptRatingCategory {
  average: number;
  explanation: string;
  criteria: Record<string, ScriptRatingCriterion>;
}

export interface ScriptRating {
  viewer_retention: ScriptRatingCategory;
  narrative_quality: ScriptRatingCategory;
  script_craft: ScriptRatingCategory;
  audience_fit: ScriptRatingCategory;
  seo_alignment: ScriptRatingCategory;
  overall: number;
  model?: string;
  version?: string;
}

// --- Hook score types ---

export interface HookScoreDimension {
  score: number;
  reasoning: string;
}

export interface HookScore {
  promise: HookScoreDimension;
  tension: HookScoreDimension;
  payoff_hint: HookScoreDimension;
  overall: number;
  suggestions: string[];
}

export interface RefinedHookResult {
  hook_score: HookScore;
  refined_hook: { intro_hook: string; opening_narration: string };
  original_hook: { intro_hook: string; opening_narration: string };
}

// --- Cold open A/B testing ---

export interface ColdOpenScores {
  tension: number;
  specificity: number;
  drop_rate_risk: number;
  overall: number;
  reasoning: string;
}

export interface ColdOpenVariant {
  id: string;
  style: string;
  intro_hook: string;
  opening_narration: string;
  scores: ColdOpenScores;
}

export interface ColdOpenResult {
  variants: ColdOpenVariant[];
  winner_id: string;
  score_labels?: {
    tension?: string;
    specificity?: string;
    drop_rate_risk?: string;
  };
  heading?: string;
  description?: string;
}
