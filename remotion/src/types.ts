/**
 * Input props types for Remotion compositions.
 * These mirror the Python Scene/SceneFX models from backend/models/script.py.
 */

export interface CameraFX {
  type: "ken_burns" | "zoom_punch" | "parallax" | "static";
  direction?: "in" | "out" | "left" | "right" | "up" | "down" | null;
  intensity?: "subtle" | "moderate" | "dramatic";
  easing?: "spring" | "linear" | "ease_in_out";
}

export interface TextEffect {
  type:
    | "lower_third"
    | "kinetic_caption"
    | "word_reveal"
    | "title_insert"
    | "source_citation";
  text?: string | null;
  words?: string[] | null;
  position?: string;
  enter_at?: number;
  duration?: number;
}

export interface TransitionFX {
  type:
    | "cut"
    | "crossfade"
    | "slide"
    | "zoom_punch"
    | "smash_cut"
    | "wipe"
    | "push";
  direction?: string | null;
  duration?: number;
}

export interface OverlayFX {
  type: "chapter_indicator" | "film_grain" | "letterbox" | "vignette";
  config?: Record<string, unknown> | null;
}

export interface StructuralFX {
  type: "cold_open" | "chapter_transition" | "recap" | "end_screen";
  config?: Record<string, unknown> | null;
}

export interface SceneFX {
  camera?: CameraFX | null;
  text_effects?: TextEffect[] | null;
  transition?: TransitionFX | null;
  overlays?: OverlayFX[] | null;
  structural?: StructuralFX | null;
}

export interface SceneInput {
  id: string;
  narration: string;
  visual_prompt: string;
  text_overlay: string;
  duration_seconds: number;
  is_title_card: boolean;
  media_type: "ai_generated" | "gameplay_clip" | "hardware_image";

  // Asset paths (absolute filesystem paths)
  image_path?: string | null;
  image_path_b?: string | null;
  frame_paths?: string[] | null;
  audio_path?: string | null;
  video_clip_path?: string | null;
  title_card_zoom_target?: { x: number; y: number; radius: number } | null;

  // FX
  fx?: SceneFX | null;

  // Legacy fields (used as fallback if fx is absent)
  ken_burns_effect?: string;
  ken_burns_intensity?: string;
  scene_transition?: string;
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
}

export interface ScenePreviewProps {
  scene: SceneInput;
  fps: number;
  width: number;
  height: number;
}
