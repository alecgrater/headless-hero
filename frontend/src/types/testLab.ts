import type { SceneFX, SubtitleStyle, VisualLayer, VisualMode } from "./script";
import type { MainCharacter, ScriptCostBreakdownItem } from "../api";

export interface TestLabMainCharacter extends MainCharacter {
  reference_image_url?: string | null;
}

export interface TestLabPreset {
  id: string;
  title: string;
  description?: string;
  format_id: string;
  segment_name: string;
  short_name?: string;
  narration: string;
  tts_narration?: string;
  visual_prompt: string;
  background_color?: string;
  visual_mode?: VisualMode;
  duration_estimate_seconds: number;
  caption_text?: string;
  caption_emphasis?: string;
  stat_value?: string;
  stat_label?: string;
  dossier_layout?: "anchor" | "network";
  dossier_title?: string;
  contains_person?: boolean;
  visual_beat?: string;
  frame_directives?: Array<Record<string, unknown>>;
  main_character: TestLabMainCharacter | null;
  tags?: string[];
}

export interface TestLabSceneTextDefaults {
  narration: string;
  visual_prompt: string;
  caption_text?: string;
  caption_emphasis?: string;
  stat_value?: string;
  stat_label?: string;
  dossier_layout?: "anchor" | "network";
  dossier_title?: string;
}

export interface TestLabScenes {
  presets: TestLabPreset[];
  visual_treatment_defaults?: Partial<Record<VisualMode, TestLabSceneTextDefaults>>;
  default_main_character: TestLabMainCharacter | null;
  voice_summary?: TestLabVoiceSummary;
  subtitle_summary?: TestLabSubtitleSummary;
}

export interface TestLabStages {
  audio: boolean;
  visual: boolean;
  treatment_assets: boolean;
  fx: boolean;
  render: boolean;
}

export interface TestLabVoiceSummary {
  voice_id: string;
  voice_name: string;
  model_id: string;
  model_label: string;
  delivery_preset: string | null;
  visible_settings: Array<{ label: string; value: string }>;
}

export interface TestLabSubtitleSummary {
  coverage_label: string;
  enabled_style_labels: string[];
}

export interface TestLabSettings {
  stages: TestLabStages;
  eli_enabled: boolean;
  style_preset_enabled: boolean;
  visual_mode: VisualMode;
  visual_layers: VisualLayer[];
  frame_directives?: Array<Record<string, unknown>>;
  fx?: SceneFX | null;
  title?: string;
  segment_name?: string;
  short_name?: string;
  narration?: string;
  tts_narration?: string;
  visual_prompt?: string;
  duration_estimate_seconds?: number;
  caption_text?: string;
  caption_emphasis?: string;
  stat_value?: string;
  stat_label?: string;
  dossier_layout?: "anchor" | "network";
  dossier_title?: string;
  contains_person?: boolean;
  visual_beat?: string;
  transition_in?: "cut" | "fade_black" | "flash_white" | "wipe";
  visual_canvas?: { background_color: string };
  segment_timer_enabled: boolean;
  subtitle_style: SubtitleStyle;
  main_character?: MainCharacter | null;
  advanced_script?: Record<string, unknown> | null;
}

export interface TestLabAsset {
  kind: "image" | "video" | "audio" | "treatment_asset" | "render";
  label: string;
  url: string;
  path?: string;
  created_at?: string;
}

export interface TestLabLogEntry {
  at?: string;
  created_at?: string;
  level?: "debug" | "info" | "warning" | "error";
  stage: string;
  status: "pending" | "queued" | "running" | "completed" | "failed" | "cancelled" | string;
  message: string;
}

export interface TestLabRun {
  run_id: string;
  script_id: string;
  preset_id: string;
  status: "pending" | "queued" | "running" | "completed" | "failed" | "cancelled";
  settings: Partial<TestLabSettings>;
  assets: TestLabAsset[];
  logs: TestLabLogEntry[];
  render_url: string;
  cost_total?: number;
  total_cost?: number;
  cost_breakdown: ScriptCostBreakdownItem[] | Record<string, unknown>;
  error?: string;
  started_at?: string;
  completed_at?: string | null;
  created_at?: string;
  updated_at?: string;
}

export interface PopupCropPreviewCrop {
  role: "anchor" | "item";
  label: string;
  url: string;
  raw_url: string;
  box: number[];
  trim_box: number[];
  warnings?: string[];
}

export interface PopupCropPreviewResult {
  run_id: string;
  anchor_prompt_used: string;
  item_prompt_used: string;
  anchor_source_url: string;
  sheet_url: string;
  crops: PopupCropPreviewCrop[];
}

export interface PopupCropAnchorResult {
  run_id: string;
  anchor_prompt_used: string;
  anchor_source_url: string;
  anchor_cutout_url?: string | null;
  warnings?: string[];
}

export interface PopupCropSheetResult {
  run_id: string;
  item_prompt_used: string;
  sheet_url: string;
}

export interface PopupCropChromaResult {
  run_id: string;
  crops: PopupCropPreviewCrop[];
}
