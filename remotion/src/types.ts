/**
 * Input props types for Remotion compositions.
 * These mirror the Python Scene/SceneFX models from backend/models/script.py.
 */

// --- FX types ---

export interface ZoomPunchFX {
  trigger_frame: number;
  scale: number; // 1.04-1.07
}

export interface DriftFX {
  motion: "zoom_in" | "zoom_out" | "pan_left" | "pan_right" | "drift_diagonal";
  intensity: number; // 0.05-0.08
  anchor: "top-left" | "top-center" | "top-right" | "center-left" | "center" | "center-right" | "bottom-left" | "bottom-center" | "bottom-right";
}

export interface SceneFX {
  zoom_punch?: ZoomPunchFX | null;
  drift?: DriftFX | null;
}

export interface WordTimestamp {
  word: string;
  start_ms: number;
  end_ms: number;
}

export interface PhraseTimestamp {
  start_ms: number;
  end_ms: number;
}

export interface EliOverlay {
  enabled: boolean;
  corner?: "TL" | "TR" | "BL" | "BR" | null;
  frame_id: string;
}

export interface FrameDirective {
  prompt: string;
  source: "ai_generated" | "subtitle";
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

export type VisualTreatment = "full_frame" | "popup_sequence" | "flipflop";

export interface VisualCanvas {
  background_color: string;
}

export interface VisualLayer {
  id: string;
  type: "image";
  asset_kind: "full_frame" | "panel" | "cutout";
  image_url?: string;
  image_path?: string | null;
  prompt?: string;
  placement?: string;
  enter_at_seconds?: number;
  exit_at_seconds?: number | null;
  animation?: "none" | "pop_in";
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

export interface ChapterOverlay {
  level_number: number;
  descriptor: string;
}

// --- Scene / Composition types ---

export type Orientation = "horizontal" | "vertical";

export interface SceneInput {
  id: string;
  narration: string;
  orientation?: Orientation;    // defaults to "horizontal" for backward compat with FullVideo
  duration_seconds: number;
  is_title_card: boolean;
  // Asset paths (absolute filesystem paths)
  image_path?: string | null;
  frame_paths?: string[] | null;
  audio_path?: string | null;
  title_card_zoom_target?: { x: number; y: number; radius: number } | null;

  // FX (new system)
  fx?: SceneFX | null;

  // Eli character overlay
  eli_overlay?: EliOverlay | null;
  character_frames_base_url?: string | null;

  // Visual Beat System
  visual_beat?: "static" | "continuous" | "quick_cuts" | "aha_subtitle" | "montage";
  frame_directives?: FrameDirective[] | null;
  visual_treatment?: VisualTreatment;
  visual_layers?: VisualLayer[] | null;

  // Timing
  word_timestamps?: WordTimestamp[] | null;
  phrase_timestamps?: PhraseTimestamp[] | null;

  // Micro-timeline visual timing overrides
  frame_timings?: number[] | null;
  visual_in_seconds?: number;
  visual_out_seconds?: number;

  // Scene-boundary transitions
  transition_in?: "cut" | "fade_black" | "flash_white" | "wipe";
  transition_out?: "cut" | "fade_black" | "flash_white" | "wipe";

  // Multi-source media
  media_type?: "image" | "video";
  video_path?: string | null;
  video_playback_rate?: number | null;

  // Cinematic-chapters chapter title overlay
  chapter_overlay?: ChapterOverlay | null;
}

export interface SegmentInput {
  name: string;
  scenes: SceneInput[];
}

export interface SegmentTimerConfig {
  enabled: boolean;
}

export interface SubtitleHighlightConfig {
  enabled: boolean;
}

export interface FullVideoProps {
  segments: SegmentInput[];
  title: string;
  fps: number;
  width: number;
  height: number;
  video_fx?: VideoFX | null;
  chapter_map?: ChapterMapData | null;
  segment_timer?: SegmentTimerConfig | null;
  subtitle_highlight?: SubtitleHighlightConfig | null;
  visual_canvas?: VisualCanvas | null;
}

// --- Short-form types ---

export interface ShortFormVideoProps {
  scenes: SceneInput[];          // first scene has is_title_card=true; rest are narration
  stripped_title: string;         // long-form video title with leading digits stripped
  segment_name: string;           // this segment's name (rendered with pop-in flourish)
  part_indicator?: string;        // life-as-a only, e.g. Part 3/6
  fps: number;
  width: number;                  // 1080
  height: number;                 // 1920
  subtitle_highlight?: SubtitleHighlightConfig | null;
  visual_canvas?: VisualCanvas | null;
}
