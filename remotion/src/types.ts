/**
 * Input props types for Remotion compositions.
 * These mirror the Python Scene/SceneFX models from backend/models/script.py.
 */

// --- New FX types (4 core effects) ---

export interface EmphasisWord {
  word: string;
  start_frame: number;
  end_frame: number;
  style:
    | "scale_pop"
    | "color_flash"
    | "size_burst"
    | "shake"
    | "underline_draw"
    | "glow_pulse"
    | "typewriter"
    | "slide_up"
    | "bounce_in"
    | "rotate_in"
    | "glitch"
    | "gradient_sweep";
  category?: string; // stat | key_noun | emotional | action_verb | contrast | keyword
  font_size?: number; // 48-120, default 64
  position?: string; // bottom_center | bottom_left | bottom_right | center | top_center
  word_index?: number; // 0-based index into narration word list
  intensity?: number; // 1 (supporting), 2 (important), 3 (peak moment)
  reason?: string; // why this word matters
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

export interface WordTimestamp {
  word: string;
  start_ms: number;
  end_ms: number;
}

export interface EliKeyframe {
  start_frame: number;
  end_frame: number;
  frame_id: string;
  transition: "cut" | "crossfade";
  reason: string;
}

export interface EliPosition {
  x: number;
  y: number;
}

export interface EliOverlay {
  enabled: boolean;
  keyframes: EliKeyframe[];
  position?: EliPosition | null;
}

export interface FrameDirective {
  prompt: string;
  source: "ai_generated" | "real_photo" | "subtitle";
  transition: "cut" | "crossfade" | "fade_black";
  reference_previous: boolean;
  search_query?: string;
}

export interface ChapterMarker {
  segment_index: number;
  label: string;
  frame_offset: number; // global frame where this chapter starts
}

export interface VideoFX {
  chapter_markers: ChapterMarker[];
}

export interface ChapterCircle {
  x: number;
  y: number;
  radius: number;
  label: string;
}

export interface ChapterMapData {
  image_path: string | null;
  circles: ChapterCircle[];
}

// --- Scene / Composition types ---

export interface SceneInput {
  id: string;
  narration: string;
  visual_prompt: string;
  text_overlay: string;
  duration_seconds: number;
  is_title_card: boolean;
  // Asset paths (absolute filesystem paths)
  image_path?: string | null;
  frame_paths?: string[] | null;
  audio_path?: string | null;
  title_card_zoom_target?: { x: number; y: number; radius: number } | null;

  // FX (new system)
  fx?: SceneFX | null;

  // Visual Beat System
  visual_beat?: "static" | "continuous" | "quick_cuts" | "aha_subtitle" | "montage";
  frame_directives?: FrameDirective[] | null;

  // Eli character overlay
  eli_overlay?: EliOverlay | null;
  word_timestamps?: WordTimestamp[] | null;
  character_frames_base_url?: string | null;
}

export interface SegmentInput {
  name: string;
  scenes: SceneInput[];
}

export interface FullVideoProps {
  segments: SegmentInput[];
  title: string;
  fps: number;
  width: number;
  height: number;
  video_fx?: VideoFX | null;
  chapter_map?: ChapterMapData | null;
}
