export interface GenerateAudioResponse {
  audio_url: string;
  duration_seconds: number;
}

export interface VoiceInfo {
  voice_id: string;
  name: string;
  category: string;
}

export interface VoiceListResponse {
  voices: VoiceInfo[];
}
