export interface GenerateAudioRequest {
  script_id: string;
  scene_id: string;
  narration: string;
  voice_id: string;
  model_id?: string;
}

export interface GenerateAudioResponse {
  audio_url: string;
  duration_seconds: number;
}

export interface BatchAudioScene {
  scene_id: string;
  narration: string;
}

export interface GenerateBatchAudioRequest {
  script_id: string;
  scenes: BatchAudioScene[];
  voice_id: string;
  model_id?: string;
}

export interface BatchAudioResultItem {
  scene_id: string;
  audio_url?: string;
  duration_seconds?: number;
  error?: string;
}

export interface GenerateBatchAudioResponse {
  results: BatchAudioResultItem[];
}

export interface VoiceInfo {
  voice_id: string;
  name: string;
  category: string;
}

export interface VoiceListResponse {
  voices: VoiceInfo[];
}

export interface CloneVoiceResponse {
  voice_id: string;
}
