import type { SceneFX, VisualLayer, VisualTreatment } from "./script";
import type { MainCharacter, ScriptCostBreakdownItem } from "../api";

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
  media_source?: "ai" | "ai_video";
  duration_estimate_seconds: number;
  contains_person?: boolean;
  visual_beat?: string;
  frame_directives?: Array<Record<string, unknown>>;
  main_character: MainCharacter | null;
  tags?: string[];
}

export interface TestLabStages {
  character: boolean;
  audio: boolean;
  visual: boolean;
  treatment_assets: boolean;
  fx: boolean;
  eli: boolean;
  render: boolean;
}

export interface TestLabSettings {
  stages: TestLabStages;
  eli_enabled: boolean;
  style_preset_enabled: boolean;
  media_source: "ai" | "ai_video";
  visual_treatment: VisualTreatment;
  visual_layers: VisualLayer[];
  fx?: SceneFX | null;
  title?: string;
  segment_name?: string;
  short_name?: string;
  narration?: string;
  tts_narration?: string;
  visual_prompt?: string;
  duration_estimate_seconds?: number;
  contains_person?: boolean;
  visual_beat?: string;
  transition_in?: "cut" | "fade_black" | "flash_white" | "wipe";
  visual_canvas?: { background_color: string };
  segment_timer_enabled: boolean;
  subtitle_highlight_enabled: boolean;
  main_character?: MainCharacter | null;
  voice_id?: string;
  voice_model_id?: string;
  voice_settings?: Record<string, unknown> | null;
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
