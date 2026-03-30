export interface GenerateAudioResponse {
  audio_url: string;
  duration_seconds: number;
}

export interface GenerateBatchAudioResponse {
  results: { scene_id: string; audio_url?: string; duration_seconds?: number; error?: string }[];
}

export interface VoiceInfo {
  voice_id: string;
  name: string;
  category: string;
}

export interface VoiceListResponse {
  voices: VoiceInfo[];
}
